from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import OrderStatus, UserRole, VisitStatus
from app.models import Consultation, Doctor, LabOrder, Prescription, PrescriptionItem, RadiologyOrder, User, Visit
from app.schemas import (
    ConsultationCreate,
    LabOrderCreate,
    LabOrderUpdate,
    PrescriptionCancelCreate,
    PrescriptionCreate,
    RadiologyOrderCreate,
    RadiologyOrderUpdate,
)
from app.services.audit import audit
from app.services.visit_service import get_visit_or_404, transition_visit


def doctor_for_user(user: User, db: Session | None = None, doctor_id: int | None = None) -> Doctor:
    """Resolve the clinical doctor context.

    Normal DOCTOR users always act as their own profile. ADMIN may select a doctor
    explicitly; this is used by the academic demo workspace so one administrator
    can demonstrate the complete patient flow without sharing multiple sessions.
    """
    if user.role == UserRole.ADMIN:
        if db is None or doctor_id is None:
            raise HTTPException(status_code=422, detail="Admin must select a doctor for the Doctor Workspace")
        doctor = db.get(Doctor, doctor_id)
        if not doctor or not doctor.user or not doctor.user.is_active:
            raise HTTPException(status_code=404, detail="Active doctor not found")
        return doctor
    if not user.doctor:
        raise HTTPException(status_code=403, detail="A doctor profile is required")
    if doctor_id is not None and doctor_id != user.doctor.id:
        raise HTTPException(status_code=403, detail="Doctors may only act as themselves")
    return user.doctor


def _normalized_text(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().split())


def _normalized_prescription_items(items) -> list[tuple[str, str, str, str, str]]:
    return sorted(
        (
            _normalized_text(item.medication_name),
            _normalized_text(item.dosage),
            _normalized_text(item.frequency),
            _normalized_text(item.duration),
            _normalized_text(item.instructions),
        )
        for item in items
    )


def start_consultation(db: Session, visit_id: int, user: User, doctor_id: int | None = None) -> Consultation:
    doctor = doctor_for_user(user, db, doctor_id)
    visit = get_visit_or_404(db, visit_id, for_update=True)
    if visit.status not in {VisitStatus.CALLED, VisitStatus.WITH_DOCTOR}:
        raise HTTPException(status_code=409, detail="Patient must be called before consultation")
    if visit.department_id != doctor.department_id:
        raise HTTPException(status_code=403, detail="Visit belongs to another department")
    if visit.assigned_doctor_id and visit.assigned_doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Visit is assigned to another doctor")
    visit.assigned_doctor_id = doctor.id
    if visit.status == VisitStatus.CALLED:
        transition_visit(db, visit, VisitStatus.WITH_DOCTOR, user.id, commit=False)
    consultation = visit.consultation
    if not consultation:
        consultation = Consultation(visit_id=visit.id, doctor_id=doctor.id)
        db.add(consultation)
        db.flush()
    db.commit()
    db.refresh(consultation)
    return consultation


def update_consultation(db: Session, visit_id: int, data: ConsultationCreate, user: User, doctor_id: int | None = None) -> Consultation:
    doctor = doctor_for_user(user, db, doctor_id)
    visit = get_visit_or_404(db, visit_id, for_update=True)
    if not visit.consultation:
        raise HTTPException(status_code=404, detail="Consultation has not started")
    if visit.consultation.doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Consultation belongs to another doctor")
    if visit.consultation.completed_at:
        raise HTTPException(status_code=409, detail="A completed consultation cannot be edited")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(visit.consultation, key, value)
    audit(db, user_id=user.id, action="CONSULTATION_UPDATED", entity_type="Consultation", entity_id=visit.consultation.id)
    db.commit()
    db.refresh(visit.consultation)
    return visit.consultation


def complete_consultation(db: Session, visit_id: int, user: User, doctor_id: int | None = None) -> Consultation:
    doctor = doctor_for_user(user, db, doctor_id)
    visit = get_visit_or_404(db, visit_id, for_update=True)
    consultation = visit.consultation
    if not consultation or consultation.doctor_id != doctor.id:
        raise HTTPException(status_code=404, detail="Consultation not found")
    if not ((consultation.diagnosis or "").strip() or (consultation.clinical_notes or "").strip()):
        raise HTTPException(status_code=422, detail="Diagnosis or clinical notes are required")
    if visit.status != VisitStatus.WITH_DOCTOR:
        raise HTTPException(status_code=409, detail="Patient must return to the doctor before the consultation can be completed")
    outstanding = int(db.scalar(
        select(func.count()).select_from(LabOrder).where(
            LabOrder.visit_id == visit.id,
            LabOrder.status.notin_([OrderStatus.COMPLETED, OrderStatus.CANCELLED]),
        )
    ) or 0) + int(db.scalar(
        select(func.count()).select_from(RadiologyOrder).where(
            RadiologyOrder.visit_id == visit.id,
            RadiologyOrder.status.notin_([OrderStatus.COMPLETED, OrderStatus.CANCELLED]),
        )
    ) or 0)
    if outstanding:
        raise HTTPException(status_code=409, detail="Complete all laboratory and radiology orders before closing the consultation")
    consultation.completed_at = datetime.now(UTC)
    transition_visit(db, visit, VisitStatus.UNDER_TREATMENT, user.id, commit=False)
    transition_visit(db, visit, VisitStatus.COMPLETED, user.id, commit=False)
    active_prescriptions = int(db.scalar(
        select(func.count()).select_from(Prescription).where(
            Prescription.visit_id == visit.id,
            Prescription.status == "ACTIVE",
        )
    ) or 0)
    dispensed_prescriptions = int(db.scalar(
        select(func.count()).select_from(Prescription).where(
            Prescription.visit_id == visit.id,
            Prescription.status == "DISPENSED",
        )
    ) or 0)
    if active_prescriptions == 0 and dispensed_prescriptions > 0:
        transition_visit(db, visit, VisitStatus.DISCHARGED, user.id, commit=False)
    db.commit()
    db.refresh(consultation)
    return consultation


def create_lab_order(db: Session, visit_id: int, data: LabOrderCreate, user: User, doctor_id: int | None = None) -> LabOrder:
    doctor = doctor_for_user(user, db, doctor_id)
    visit = get_visit_or_404(db, visit_id, for_update=True)
    _validate_doctor_workflow(visit, doctor)
    open_orders = db.scalars(
        select(LabOrder).where(
            LabOrder.visit_id == visit.id,
            LabOrder.doctor_id == doctor.id,
            LabOrder.status.notin_([OrderStatus.COMPLETED, OrderStatus.CANCELLED]),
        )
    )
    if any(_normalized_text(order.test_name) == _normalized_text(data.test_name) for order in open_orders):
        raise HTTPException(status_code=409, detail="An active laboratory order already exists for this test")
    order = LabOrder(visit_id=visit.id, doctor_id=doctor.id, **data.model_dump())
    db.add(order)
    db.flush()
    audit(db, user_id=user.id, action="LAB_ORDER_CREATED", entity_type="LabOrder", entity_id=order.id, new_data={"visit_id": visit.id, "test_name": data.test_name})
    if visit.status != VisitStatus.WAITING_FOR_LAB:
        transition_visit(db, visit, VisitStatus.WAITING_FOR_LAB, user.id, commit=False)
    db.commit()
    db.refresh(order)
    return order


def create_radiology_order(db: Session, visit_id: int, data: RadiologyOrderCreate, user: User, doctor_id: int | None = None) -> RadiologyOrder:
    doctor = doctor_for_user(user, db, doctor_id)
    visit = get_visit_or_404(db, visit_id, for_update=True)
    _validate_doctor_workflow(visit, doctor)
    open_orders = db.scalars(
        select(RadiologyOrder).where(
            RadiologyOrder.visit_id == visit.id,
            RadiologyOrder.doctor_id == doctor.id,
            RadiologyOrder.status.notin_([OrderStatus.COMPLETED, OrderStatus.CANCELLED]),
        )
    )
    if any(
        _normalized_text(order.scan_type) == _normalized_text(data.scan_type)
        and _normalized_text(order.body_area) == _normalized_text(data.body_area)
        for order in open_orders
    ):
        raise HTTPException(status_code=409, detail="An active radiology order already exists for this scan")
    order = RadiologyOrder(visit_id=visit.id, doctor_id=doctor.id, **data.model_dump())
    db.add(order)
    db.flush()
    audit(db, user_id=user.id, action="RADIOLOGY_ORDER_CREATED", entity_type="RadiologyOrder", entity_id=order.id, new_data={"visit_id": visit.id, "scan_type": data.scan_type})
    if visit.status != VisitStatus.WAITING_FOR_RADIOLOGY:
        transition_visit(db, visit, VisitStatus.WAITING_FOR_RADIOLOGY, user.id, commit=False)
    db.commit()
    db.refresh(order)
    return order


def create_prescription(db: Session, visit_id: int, data: PrescriptionCreate, user: User, doctor_id: int | None = None) -> Prescription:
    doctor = doctor_for_user(user, db, doctor_id)
    visit = get_visit_or_404(db, visit_id, for_update=True)
    _validate_doctor_workflow(visit, doctor)
    active_prescriptions = db.scalars(
        select(Prescription)
        .options(selectinload(Prescription.items))
        .where(
            Prescription.visit_id == visit.id,
            Prescription.doctor_id == doctor.id,
            Prescription.status == "ACTIVE",
        )
    )
    normalized_items = _normalized_prescription_items(data.items)
    if any(
        _normalized_prescription_items(prescription.items) == normalized_items
        for prescription in active_prescriptions
    ):
        raise HTTPException(status_code=409, detail="An identical active prescription already exists")
    prescription = Prescription(visit_id=visit.id, doctor_id=doctor.id, status=data.status)
    prescription.items = [PrescriptionItem(**item.model_dump()) for item in data.items]
    db.add(prescription)
    db.flush()
    audit(db, user_id=user.id, action="PRESCRIPTION_CREATED", entity_type="Prescription", entity_id=prescription.id, new_data={"visit_id": visit.id, "items": len(data.items)})
    db.commit()
    db.refresh(prescription)
    return prescription


def list_visit_prescriptions_for_doctor(db: Session, visit_id: int, user: User, doctor_id: int | None = None) -> list[Prescription]:
    doctor = doctor_for_user(user, db, doctor_id)
    visit = get_visit_or_404(db, visit_id)
    if visit.department_id != doctor.department_id or visit.assigned_doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Visit is not assigned to this doctor")
    if visit.consultation and visit.consultation.doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Consultation belongs to another doctor")
    return list(db.scalars(
        select(Prescription)
        .options(selectinload(Prescription.items))
        .where(Prescription.visit_id == visit.id)
        .order_by(Prescription.created_at.desc())
    ))


DOCTOR_PRESCRIPTION_CANCEL_BLOCKED_STATUSES = {
    VisitStatus.DISCHARGED,
    VisitStatus.ADMITTED,
    VisitStatus.TRANSFERRED,
    VisitStatus.CANCELLED,
    VisitStatus.LEFT_WITHOUT_BEING_SEEN,
}


def cancel_prescription_by_doctor(
    db: Session,
    prescription: Prescription,
    visit: Visit,
    data: PrescriptionCancelCreate,
    user: User,
    doctor_id: int | None = None,
) -> Prescription:
    doctor = doctor_for_user(user, db, doctor_id)
    if prescription.visit_id != visit.id:
        raise HTTPException(status_code=409, detail="Prescription does not belong to the locked visit")
    if visit.department_id != doctor.department_id or visit.assigned_doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Visit is not assigned to this doctor")
    consultation = visit.consultation
    if not consultation or consultation.doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Consultation belongs to another doctor")
    if prescription.doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Prescription belongs to another doctor")
    if visit.status in DOCTOR_PRESCRIPTION_CANCEL_BLOCKED_STATUSES:
        raise HTTPException(status_code=409, detail="Prescription cannot be changed after terminal disposition")
    if prescription.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Only an active prescription can be cancelled by its doctor")
    prescription.status = "CANCELLED"
    audit(
        db,
        user_id=user.id,
        action="PRESCRIPTION_CANCELLED_BY_DOCTOR",
        entity_type="Prescription",
        entity_id=prescription.id,
        old_data={"status": "ACTIVE"},
        new_data={"status": "CANCELLED", "reason": data.reason},
    )
    db.commit()
    db.refresh(prescription)
    return prescription


def _validate_doctor_workflow(
    visit,
    doctor: Doctor,
    allowed_statuses: set[VisitStatus] | None = None,
) -> None:
    allowed = allowed_statuses or {VisitStatus.WITH_DOCTOR, VisitStatus.WAITING_FOR_LAB, VisitStatus.WAITING_FOR_RADIOLOGY}
    if visit.department_id != doctor.department_id:
        raise HTTPException(status_code=403, detail="Visit belongs to another department")
    if visit.assigned_doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Visit is assigned to another doctor")
    if not visit.consultation or visit.consultation.doctor_id != doctor.id:
        raise HTTPException(status_code=409, detail="Start this patient's consultation before creating clinical orders")
    if visit.status not in allowed:
        raise HTTPException(status_code=409, detail=f"Clinical orders are not allowed while the visit is {visit.status.value}")


ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.REQUESTED: {OrderStatus.RECEIVED, OrderStatus.PROCESSING, OrderStatus.COMPLETED, OrderStatus.CANCELLED},
    OrderStatus.RECEIVED: {OrderStatus.PROCESSING, OrderStatus.COMPLETED, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.COMPLETED, OrderStatus.CANCELLED},
    OrderStatus.COMPLETED: set(),
    OrderStatus.CANCELLED: set(),
}


def update_diagnostic_order(
    db: Session,
    order: LabOrder | RadiologyOrder,
    visit: Visit,
    data: LabOrderUpdate | RadiologyOrderUpdate,
    user: User,
) -> None:
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        db.commit()
        db.refresh(order)
        return
    if "status" in changes and changes["status"] is None:
        raise HTTPException(status_code=422, detail="Diagnostic order status cannot be null")
    requested_status = changes.get("status", order.status)
    if requested_status != order.status and requested_status not in ORDER_TRANSITIONS[order.status]:
        raise HTTPException(status_code=409, detail=f"Invalid order transition: {order.status.value} -> {requested_status.value}")
    if order.status in {OrderStatus.COMPLETED, OrderStatus.CANCELLED} and changes:
        raise HTTPException(status_code=409, detail="A terminal diagnostic order cannot be changed")
    if requested_status == OrderStatus.COMPLETED:
        result = changes.get("result", getattr(order, "result", None))
        report = changes.get("report", getattr(order, "report", None))
        if isinstance(order, LabOrder) and not result:
            raise HTTPException(status_code=422, detail="A verified laboratory result is required")
        if isinstance(order, RadiologyOrder) and not report:
            raise HTTPException(status_code=422, detail="A verified radiology report is required")
    for key, value in changes.items():
        setattr(order, key, value)
    finish_diagnostic_order(db, order, visit, user)


def finish_diagnostic_order(db: Session, order, visit: Visit, user: User) -> None:
    """Record completion while the locked visit serializes final-result routing."""
    audit(
        db,
        user_id=user.id,
        action="DIAGNOSTIC_ORDER_UPDATED",
        entity_type=type(order).__name__,
        entity_id=order.id,
        new_data={"status": order.status.value},
    )
    if order.status == OrderStatus.COMPLETED:
        order.completed_at = datetime.now(UTC)
    elif order.status != OrderStatus.CANCELLED:
        db.commit()
        db.refresh(order)
        return

    db.flush()
    pending_lab = int(db.scalar(
        select(func.count()).select_from(LabOrder).where(
            LabOrder.visit_id == visit.id,
            LabOrder.status.notin_([OrderStatus.COMPLETED, OrderStatus.CANCELLED]),
        )
    ) or 0)
    pending_radiology = int(db.scalar(
        select(func.count()).select_from(RadiologyOrder).where(
            RadiologyOrder.visit_id == visit.id,
            RadiologyOrder.status.notin_([OrderStatus.COMPLETED, OrderStatus.CANCELLED]),
        )
    ) or 0)
    if pending_lab + pending_radiology == 0 and visit.status in {VisitStatus.WAITING_FOR_LAB, VisitStatus.WAITING_FOR_RADIOLOGY}:
        transition_visit(db, visit, VisitStatus.RESULTS_READY, user.id, commit=False)
        transition_visit(db, visit, VisitStatus.WAITING_FOR_DOCTOR, user.id, commit=False)
    elif pending_lab > 0 and pending_radiology == 0 and visit.status != VisitStatus.WAITING_FOR_LAB:
        transition_visit(db, visit, VisitStatus.WAITING_FOR_LAB, user.id, commit=False)
    elif pending_radiology > 0 and pending_lab == 0 and visit.status != VisitStatus.WAITING_FOR_RADIOLOGY:
        transition_visit(db, visit, VisitStatus.WAITING_FOR_RADIOLOGY, user.id, commit=False)
    db.commit()
    db.refresh(order)


PRESCRIPTION_TRANSITIONS: dict[str, set[str]] = {
    "ACTIVE": {"DISPENSED", "CANCELLED"},
    "DISPENSED": set(),
    "CANCELLED": set(),
}


def change_prescription_status(
    db: Session,
    prescription: Prescription,
    visit: Visit,
    new_status: str,
    user: User,
) -> Prescription:
    current_status = prescription.status
    if new_status == current_status:
        db.commit()
        db.refresh(prescription)
        return prescription
    if new_status not in PRESCRIPTION_TRANSITIONS.get(current_status, set()):
        raise HTTPException(status_code=409, detail=f"Invalid prescription transition: {current_status} -> {new_status}")
    if new_status == "DISPENSED" and visit.status != VisitStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="The consultation must be completed before dispensing")
    prescription.status = new_status
    finish_prescription_workflow(db, prescription, visit, user)
    return prescription


def finish_prescription_workflow(db: Session, prescription: Prescription, visit: Visit, user: User) -> None:
    """Count active prescriptions behind the visit lock so the final dispense discharges once."""
    if prescription.status == "DISPENSED" and visit.status != VisitStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="The consultation must be completed before dispensing")
    db.flush()
    remaining = int(db.scalar(
        select(func.count()).select_from(Prescription).where(
            Prescription.visit_id == visit.id,
            Prescription.status == "ACTIVE",
        )
    ) or 0)
    audit(db, user_id=user.id, action="PRESCRIPTION_UPDATED", entity_type="Prescription", entity_id=prescription.id, new_data={"status": prescription.status})
    if prescription.status == "DISPENSED" and remaining == 0 and visit.status == VisitStatus.COMPLETED:
        transition_visit(db, visit, VisitStatus.DISCHARGED, user.id)
    else:
        db.commit()
    db.refresh(prescription)
