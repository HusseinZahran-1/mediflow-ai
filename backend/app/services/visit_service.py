from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.enums import OrderStatus, Priority, RoomStatus, UserRole, VisitStatus
from app.models import Consultation, Department, Doctor, LabOrder, Patient, Prescription, RadiologyOrder, Room, User, Visit
from app.schemas import VisitClosureCreate, VisitCreate, VisitDispositionCreate
from app.services.audit import audit


TERMINAL_STATUSES = {
    VisitStatus.COMPLETED,
    VisitStatus.DISCHARGED,
    VisitStatus.ADMITTED,
    VisitStatus.TRANSFERRED,
    VisitStatus.CANCELLED,
    VisitStatus.LEFT_WITHOUT_BEING_SEEN,
}

ROOM_ASSIGNABLE_STATUSES = {
    VisitStatus.WAITING_FOR_DOCTOR,
    VisitStatus.CALLED,
    VisitStatus.WITH_DOCTOR,
}

ALLOWED_TRANSITIONS: dict[VisitStatus, set[VisitStatus]] = {
    VisitStatus.REGISTERED: {VisitStatus.WAITING_FOR_TRIAGE, VisitStatus.CANCELLED},
    VisitStatus.WAITING_FOR_TRIAGE: {VisitStatus.IN_TRIAGE, VisitStatus.CANCELLED, VisitStatus.LEFT_WITHOUT_BEING_SEEN},
    VisitStatus.IN_TRIAGE: {VisitStatus.TRIAGE_COMPLETED, VisitStatus.CANCELLED, VisitStatus.LEFT_WITHOUT_BEING_SEEN},
    VisitStatus.TRIAGE_COMPLETED: {VisitStatus.WAITING_FOR_DOCTOR},
    VisitStatus.WAITING_FOR_DOCTOR: {VisitStatus.CALLED, VisitStatus.CANCELLED, VisitStatus.LEFT_WITHOUT_BEING_SEEN},
    VisitStatus.CALLED: {VisitStatus.WITH_DOCTOR, VisitStatus.WAITING_FOR_DOCTOR, VisitStatus.CANCELLED, VisitStatus.LEFT_WITHOUT_BEING_SEEN},
    VisitStatus.WITH_DOCTOR: {VisitStatus.WAITING_FOR_LAB, VisitStatus.WAITING_FOR_RADIOLOGY, VisitStatus.UNDER_TREATMENT, VisitStatus.COMPLETED, VisitStatus.ADMITTED, VisitStatus.TRANSFERRED},
    VisitStatus.WAITING_FOR_LAB: {VisitStatus.WAITING_FOR_RADIOLOGY, VisitStatus.RESULTS_READY, VisitStatus.WITH_DOCTOR},
    VisitStatus.WAITING_FOR_RADIOLOGY: {VisitStatus.WAITING_FOR_LAB, VisitStatus.RESULTS_READY, VisitStatus.WITH_DOCTOR},
    VisitStatus.RESULTS_READY: {VisitStatus.WAITING_FOR_DOCTOR, VisitStatus.UNDER_TREATMENT},
    VisitStatus.UNDER_TREATMENT: {VisitStatus.COMPLETED, VisitStatus.DISCHARGED, VisitStatus.ADMITTED, VisitStatus.TRANSFERRED},
    VisitStatus.COMPLETED: {VisitStatus.DISCHARGED},
}


CLOSURE_ROLE_RULES: dict[UserRole, dict[VisitStatus, set[VisitStatus]]] = {
    UserRole.RECEPTIONIST: {
        VisitStatus.CANCELLED: {VisitStatus.WAITING_FOR_TRIAGE},
    },
    UserRole.TRIAGE_NURSE: {
        VisitStatus.CANCELLED: {VisitStatus.WAITING_FOR_TRIAGE, VisitStatus.IN_TRIAGE},
        VisitStatus.LEFT_WITHOUT_BEING_SEEN: {VisitStatus.WAITING_FOR_TRIAGE, VisitStatus.IN_TRIAGE},
    },
    UserRole.DOCTOR: {
        VisitStatus.CANCELLED: {VisitStatus.WAITING_FOR_DOCTOR, VisitStatus.CALLED},
        VisitStatus.LEFT_WITHOUT_BEING_SEEN: {VisitStatus.WAITING_FOR_DOCTOR, VisitStatus.CALLED},
    },
}


def get_visit_or_404(db: Session, visit_id: int, *, for_update: bool = False) -> Visit:
    if for_update:
        visit = db.scalar(
            select(Visit)
            .where(Visit.id == visit_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    else:
        visit = db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    return visit


def _get_active_prescriptions_for_update(db: Session, visit_id: int) -> list[Prescription]:
    return list(db.scalars(
        select(Prescription).where(
            Prescription.visit_id == visit_id,
            Prescription.status == "ACTIVE",
        ).with_for_update()
    ))


def _cancel_active_prescriptions(
    db: Session,
    prescriptions: list[Prescription],
    user_id: int,
    *,
    reason: str,
    source: str,
) -> int:
    for prescription in prescriptions:
        prescription.status = "CANCELLED"
        audit(
            db,
            user_id=user_id,
            action="PRESCRIPTION_UPDATED",
            entity_type="Prescription",
            entity_id=prescription.id,
            old_data={"status": "ACTIVE"},
            new_data={"status": "CANCELLED", "reason": reason, "source": source},
        )
    return len(prescriptions)


def close_visit(db: Session, visit_id: int, data: VisitClosureCreate, user: User) -> Visit:
    """Close an eligible visit with optimistic-state validation and a locked transition."""
    try:
        visit = get_visit_or_404(db, visit_id, for_update=True)
        if visit.status != data.expected_status:
            raise HTTPException(
                status_code=409,
                detail=f"Visit status changed: expected {data.expected_status.value}, found {visit.status.value}",
            )

        if user.role == UserRole.ADMIN:
            if data.status not in ALLOWED_TRANSITIONS.get(visit.status, set()):
                raise HTTPException(
                    status_code=409,
                    detail=f"Invalid visit transition: {visit.status.value} -> {data.status.value}",
                )
        else:
            role_rules = CLOSURE_ROLE_RULES.get(user.role)
            if not role_rules or data.status not in role_rules:
                raise HTTPException(status_code=403, detail="This role cannot perform the requested closure")
            if visit.status not in role_rules[data.status]:
                raise HTTPException(status_code=409, detail=f"This role cannot close a visit from {visit.status.value}")
            if user.role == UserRole.DOCTOR:
                doctor = user.doctor
                if not doctor or visit.department_id != doctor.department_id:
                    raise HTTPException(status_code=403, detail="Visit belongs to another department")
                if visit.assigned_doctor_id and visit.assigned_doctor_id != doctor.id:
                    raise HTTPException(status_code=403, detail="Visit is assigned to another doctor")

        active_prescriptions = _get_active_prescriptions_for_update(db, visit.id)
        cancelled_prescriptions = _cancel_active_prescriptions(
            db,
            active_prescriptions,
            user.id,
            reason=data.reason,
            source="VISIT_CLOSURE",
        )
        previous_status = visit.status
        transition_visit(db, visit, data.status, user.id, commit=False)
        audit(
            db,
            user_id=user.id,
            action="VISIT_CLOSED",
            entity_type="Visit",
            entity_id=visit.id,
            old_data={"status": previous_status.value},
            new_data={
                "status": data.status.value,
                "reason": data.reason,
                "cancelled_prescriptions": cancelled_prescriptions,
            },
        )
        db.commit()
        db.refresh(visit)
        return visit
    except Exception:
        db.rollback()
        raise


def set_visit_disposition(db: Session, visit_id: int, data: VisitDispositionCreate, user: User, doctor_id: int | None = None) -> Visit:
    """Admit or transfer an active visit using the selected doctor context."""
    if user.role == UserRole.ADMIN:
        if doctor_id is None:
            raise HTTPException(status_code=403, detail="Admin must select a doctor for the Doctor Workspace")
        doctor = db.get(Doctor, doctor_id)
        if not doctor or not doctor.user or not doctor.user.is_active:
            raise HTTPException(status_code=404, detail="Active doctor not found")
    elif user.role == UserRole.DOCTOR:
        doctor = user.doctor
        if not doctor:
            raise HTTPException(status_code=403, detail="A doctor profile is required")
    else:
        raise HTTPException(status_code=403, detail="Only doctors can record a disposition")

    try:
        visit = get_visit_or_404(db, visit_id, for_update=True)
        if visit.status != VisitStatus.WITH_DOCTOR:
            raise HTTPException(status_code=409, detail="Disposition requires a visit that is with the doctor")
        if visit.department_id != doctor.department_id:
            raise HTTPException(status_code=403, detail="Visit belongs to another department")
        if visit.assigned_doctor_id != doctor.id:
            raise HTTPException(status_code=403, detail="Visit is not assigned to this doctor")

        consultation = db.scalar(select(Consultation).where(Consultation.visit_id == visit.id))
        if not consultation:
            raise HTTPException(status_code=409, detail="A consultation is required before disposition")
        if consultation.doctor_id != doctor.id:
            raise HTTPException(status_code=403, detail="Consultation belongs to another doctor")
        if not ((consultation.diagnosis or "").strip() or (consultation.clinical_notes or "").strip()):
            raise HTTPException(status_code=409, detail="Diagnosis or clinical notes are required before disposition")

        pending_orders = int(db.scalar(
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
        if pending_orders:
            raise HTTPException(status_code=409, detail="Complete or cancel all diagnostic orders before disposition")

        active_prescriptions = _get_active_prescriptions_for_update(db, visit.id)
        cancelled_prescriptions = _cancel_active_prescriptions(
            db,
            active_prescriptions,
            user.id,
            reason=data.reason,
            source="VISIT_DISPOSITION",
        )
        consultation.completed_at = datetime.now(UTC)
        previous_status = visit.status
        transition_visit(db, visit, data.status, user.id, commit=False)
        audit(
            db,
            user_id=user.id,
            action="VISIT_DISPOSITION_RECORDED",
            entity_type="Visit",
            entity_id=visit.id,
            old_data={"status": previous_status.value},
            new_data={
                "status": data.status.value,
                "reason": data.reason,
                "destination": data.destination,
                "cancelled_prescriptions": cancelled_prescriptions,
            },
        )
        db.commit()
        db.refresh(visit)
        return visit
    except Exception:
        db.rollback()
        raise


def create_visit(db: Session, data: VisitCreate, user_id: int) -> Visit:
    patient = db.scalar(
        select(Patient)
        .where(Patient.id == data.patient_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    active_visit = db.scalar(
        select(Visit)
        .where(
            Visit.patient_id == patient.id,
            Visit.status.notin_(TERMINAL_STATUSES),
        )
        .order_by(Visit.arrival_time.desc())
    )
    if active_visit:
        raise HTTPException(
            status_code=409,
            detail=f"Patient already has active visit {active_visit.ticket_code}",
        )
    department = db.get(Department, data.department_id)
    if not department or not department.is_active:
        raise HTTPException(status_code=404, detail="Active department not found")
    if db.bind and db.bind.dialect.name == "postgresql":
        lock_key = int(f"{date.today():%Y%m%d}{data.department_id}")
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    last_sequence = db.scalar(
        select(func.max(Visit.ticket_sequence)).where(
            Visit.department_id == data.department_id,
            Visit.ticket_date == date.today(),
        )
    ) or 0
    sequence = int(last_sequence) + 1
    visit = Visit(
        **data.model_dump(),
        ticket_sequence=sequence,
        ticket_date=date.today(),
        ticket_code=f"{department.ticket_prefix.upper()}{sequence:03d}",
        status=VisitStatus.WAITING_FOR_TRIAGE,
    )
    db.add(visit)
    db.flush()
    audit(db, user_id=user_id, action="VISIT_CREATED", entity_type="Visit", entity_id=visit.id, new_data={"ticket_code": visit.ticket_code, "patient_id": visit.patient_id})
    db.commit()
    db.refresh(visit)
    return visit


def transition_visit(
    db: Session,
    visit: Visit,
    new_status: VisitStatus,
    user_id: int,
    *,
    commit: bool = True,
) -> Visit:
    if visit.status == new_status:
        return visit
    allowed = ALLOWED_TRANSITIONS.get(visit.status, set())
    if new_status not in allowed:
        raise HTTPException(status_code=409, detail=f"Invalid visit transition: {visit.status.value} -> {new_status.value}")
    old = visit.status
    visit.status = new_status
    releases_room = new_status in {VisitStatus.WAITING_FOR_LAB, VisitStatus.WAITING_FOR_RADIOLOGY, *TERMINAL_STATUSES}
    releases_room = releases_room or (old == VisitStatus.CALLED and new_status == VisitStatus.WAITING_FOR_DOCTOR)
    if releases_room:
        if visit.assigned_room:
            other_occupants = int(db.scalar(
                select(func.count()).select_from(Visit).where(
                    Visit.assigned_room_id == visit.assigned_room_id,
                    Visit.id != visit.id,
                    Visit.status.notin_(TERMINAL_STATUSES),
                )
            ) or 0)
            if other_occupants == 0:
                visit.assigned_room.status = RoomStatus.AVAILABLE
        visit.assigned_room_id = None
    if new_status == VisitStatus.WITH_DOCTOR and not visit.started_at:
        visit.started_at = datetime.now(UTC)
    if new_status in TERMINAL_STATUSES and not visit.completed_at:
        visit.completed_at = datetime.now(UTC)
    audit(db, user_id=user_id, action="VISIT_STATUS_CHANGED", entity_type="Visit", entity_id=visit.id, old_data={"status": old.value}, new_data={"status": new_status.value})
    db.flush()
    if commit:
        db.commit()
        db.refresh(visit)
    return visit


def assign_doctor(
    db: Session,
    visit: Visit,
    doctor_id: int,
    user_id: int,
    *,
    actor_role: UserRole,
    allow_reassignment: bool = False,
    commit: bool = True,
) -> Visit:
    doctor = db.get(Doctor, doctor_id)
    if not doctor or doctor.department_id != visit.department_id:
        raise HTTPException(status_code=422, detail="Doctor must belong to the visit department")
    consultation = visit.consultation
    if consultation and consultation.doctor_id != doctor_id:
        raise HTTPException(status_code=409, detail="Doctor assignment must match the existing consultation")
    previous_doctor_id = visit.assigned_doctor_id
    if previous_doctor_id == doctor_id:
        if commit:
            db.commit()
            db.refresh(visit)
        return visit
    if previous_doctor_id is not None and (
        actor_role != UserRole.ADMIN or not allow_reassignment
    ):
        raise HTTPException(status_code=403, detail="Visit is already assigned to another doctor")
    visit.assigned_doctor_id = doctor_id
    audit(
        db,
        user_id=user_id,
        action="DOCTOR_ASSIGNED",
        entity_type="Visit",
        entity_id=visit.id,
        old_data={"doctor_id": previous_doctor_id},
        new_data={"doctor_id": doctor_id, "reassigned": previous_doctor_id is not None},
    )
    db.flush()
    if commit:
        db.commit()
        db.refresh(visit)
    return visit


def assign_room(
    db: Session,
    visit: Visit,
    room_id: int,
    user_id: int,
    *,
    commit: bool = True,
) -> Visit:
    if visit.status not in ROOM_ASSIGNABLE_STATUSES:
        raise HTTPException(status_code=409, detail=f"A room cannot be assigned while the visit is {visit.status.value}")
    room = db.scalar(select(Room).where(Room.id == room_id).with_for_update())
    if not room or room.department_id != visit.department_id:
        raise HTTPException(status_code=422, detail="Room is unavailable or belongs to another department")
    is_current_room = visit.assigned_room_id == room_id
    occupied_by_other = int(db.scalar(
        select(func.count()).select_from(Visit).where(
            Visit.assigned_room_id == room_id,
            Visit.id != visit.id,
            Visit.status.notin_(TERMINAL_STATUSES),
        )
    ) or 0)
    if (room.status != RoomStatus.AVAILABLE and not is_current_room) or occupied_by_other:
        raise HTTPException(status_code=409, detail="Room is already occupied")
    if visit.assigned_room and visit.assigned_room_id != room_id:
        visit.assigned_room.status = RoomStatus.AVAILABLE
    visit.assigned_room_id = room_id
    room.status = RoomStatus.OCCUPIED
    audit(db, user_id=user_id, action="ROOM_ASSIGNED", entity_type="Visit", entity_id=visit.id, new_data={"room_id": room_id})
    db.flush()
    if commit:
        db.commit()
        db.refresh(visit)
    return visit


def priority_score(priority: Priority) -> float:
    return {Priority.CRITICAL: 300.0, Priority.URGENT: 200.0, Priority.NORMAL: 100.0}[priority]
