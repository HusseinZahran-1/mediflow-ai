from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.enums import OrderStatus, Priority, VisitStatus
from app.core.permissions import require_permission
from app.models import LabOrder, Prescription, RadiologyOrder, User, Visit
from app.schemas import (
    ConsultationCreate,
    ConsultationRead,
    LabOrderCreate,
    LabOrderRead,
    LabOrderUpdate,
    PrescriptionCancelCreate,
    PrescriptionCreate,
    PrescriptionRead,
    RadiologyOrderCreate,
    RadiologyOrderRead,
    RadiologyOrderUpdate,
)
from app.services.clinical_service import (
    cancel_prescription_by_doctor,
    change_prescription_status,
    complete_consultation,
    create_lab_order,
    create_prescription,
    create_radiology_order,
    doctor_for_user,
    list_visit_prescriptions_for_doctor,
    start_consultation,
    update_diagnostic_order,
    update_consultation,
)
from app.services.visit_service import get_visit_or_404


router = APIRouter(tags=["Clinical Workflow"])


@router.post("/visits/{visit_id}/start-consultation", response_model=ConsultationRead)
def start(visit_id: int, doctor_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db), user: User = Depends(require_permission("consultation:create"))):
    return start_consultation(db, visit_id, user, doctor_id)


@router.patch("/visits/{visit_id}/consultation", response_model=ConsultationRead)
def update(visit_id: int, data: ConsultationCreate, doctor_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db), user: User = Depends(require_permission("consultation:create"))):
    return update_consultation(db, visit_id, data, user, doctor_id)


@router.get("/visits/{visit_id}/consultation", response_model=ConsultationRead)
def consultation(visit_id: int, doctor_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db), user: User = Depends(require_permission("consultation:create"))):
    doctor = doctor_for_user(user, db, doctor_id)
    visit = get_visit_or_404(db, visit_id)
    if visit.department_id != doctor.department_id or visit.assigned_doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Consultation belongs to another doctor")
    if not visit.consultation:
        raise HTTPException(status_code=404, detail="Consultation has not started")
    return visit.consultation


@router.post("/visits/{visit_id}/complete-consultation", response_model=ConsultationRead)
def finish(visit_id: int, doctor_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db), user: User = Depends(require_permission("consultation:create"))):
    return complete_consultation(db, visit_id, user, doctor_id)


@router.post("/visits/{visit_id}/lab-orders", response_model=LabOrderRead, status_code=201)
def add_lab(visit_id: int, data: LabOrderCreate, doctor_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db), user: User = Depends(require_permission("lab:create"))):
    return create_lab_order(db, visit_id, data, user, doctor_id)


@router.get("/lab-orders", response_model=list[LabOrderRead])
def labs(worklist: bool = False, db: Session = Depends(get_db), _: User = Depends(require_permission("lab:read"))):
    if not worklist:
        return list(db.scalars(select(LabOrder).order_by(LabOrder.requested_at.desc()).limit(500)))
    priority_order = case(
        (LabOrder.priority == Priority.CRITICAL, 0),
        (LabOrder.priority == Priority.URGENT, 1),
        else_=2,
    )
    rows = db.execute(
        select(LabOrder, Visit.ticket_code)
        .join(Visit, Visit.id == LabOrder.visit_id)
        .where(LabOrder.status.in_([OrderStatus.REQUESTED, OrderStatus.RECEIVED, OrderStatus.PROCESSING]))
        .order_by(priority_order, LabOrder.requested_at.asc())
        .limit(500)
    ).all()
    result = []
    for order, ticket_code in rows:
        order.ticket_code = ticket_code
        result.append(order)
    return result


@router.get("/lab-orders/{order_id}", response_model=LabOrderRead)
def lab(order_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("lab:read"))):
    order = db.get(LabOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Lab order not found")
    return order


@router.patch("/lab-orders/{order_id}", response_model=LabOrderRead)
def update_lab(order_id: int, data: LabOrderUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("lab:update"))):
    visit_id = db.scalar(select(LabOrder.visit_id).where(LabOrder.id == order_id))
    if visit_id is None:
        raise HTTPException(status_code=404, detail="Lab order not found")
    try:
        visit = get_visit_or_404(db, visit_id, for_update=True)
        order = db.scalar(
            select(LabOrder)
            .where(LabOrder.id == order_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not order:
            raise HTTPException(status_code=404, detail="Lab order not found")
        update_diagnostic_order(db, order, visit, data, user)
        return order
    except Exception:
        db.rollback()
        raise


@router.post("/visits/{visit_id}/radiology-orders", response_model=RadiologyOrderRead, status_code=201)
def add_radiology(visit_id: int, data: RadiologyOrderCreate, doctor_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db), user: User = Depends(require_permission("radiology:create"))):
    return create_radiology_order(db, visit_id, data, user, doctor_id)


@router.get("/radiology-orders", response_model=list[RadiologyOrderRead])
def radiology_orders(worklist: bool = False, db: Session = Depends(get_db), _: User = Depends(require_permission("radiology:read"))):
    if not worklist:
        return list(db.scalars(select(RadiologyOrder).order_by(RadiologyOrder.requested_at.desc()).limit(500)))
    priority_order = case(
        (RadiologyOrder.priority == Priority.CRITICAL, 0),
        (RadiologyOrder.priority == Priority.URGENT, 1),
        else_=2,
    )
    rows = db.execute(
        select(RadiologyOrder, Visit.ticket_code)
        .join(Visit, Visit.id == RadiologyOrder.visit_id)
        .where(RadiologyOrder.status.in_([OrderStatus.REQUESTED, OrderStatus.RECEIVED, OrderStatus.PROCESSING]))
        .order_by(priority_order, RadiologyOrder.requested_at.asc())
        .limit(500)
    ).all()
    result = []
    for order, ticket_code in rows:
        order.ticket_code = ticket_code
        result.append(order)
    return result


@router.patch("/radiology-orders/{order_id}", response_model=RadiologyOrderRead)
def update_radiology(order_id: int, data: RadiologyOrderUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("radiology:update"))):
    visit_id = db.scalar(select(RadiologyOrder.visit_id).where(RadiologyOrder.id == order_id))
    if visit_id is None:
        raise HTTPException(status_code=404, detail="Radiology order not found")
    try:
        visit = get_visit_or_404(db, visit_id, for_update=True)
        order = db.scalar(
            select(RadiologyOrder)
            .where(RadiologyOrder.id == order_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not order:
            raise HTTPException(status_code=404, detail="Radiology order not found")
        update_diagnostic_order(db, order, visit, data, user)
        return order
    except Exception:
        db.rollback()
        raise


@router.post("/visits/{visit_id}/prescriptions", response_model=PrescriptionRead, status_code=201)
def add_prescription(visit_id: int, data: PrescriptionCreate, doctor_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db), user: User = Depends(require_permission("prescription:create"))):
    return create_prescription(db, visit_id, data, user, doctor_id)


@router.get("/visits/{visit_id}/prescriptions", response_model=list[PrescriptionRead])
def visit_prescriptions(
    visit_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("prescription:create")),
    doctor_id: int | None = Query(default=None, ge=1),
):
    return list_visit_prescriptions_for_doctor(db, visit_id, user, doctor_id)


@router.get("/prescriptions", response_model=list[PrescriptionRead])
def list_prescriptions(worklist: bool = False, db: Session = Depends(get_db), _: User = Depends(require_permission("prescription:read"))):
    if not worklist:
        stmt = select(Prescription).options(selectinload(Prescription.items)).order_by(Prescription.created_at.desc()).limit(500)
        return list(db.scalars(stmt))
    priority_order = case(
        (Visit.final_priority == Priority.CRITICAL, 0),
        (Visit.final_priority == Priority.URGENT, 1),
        else_=2,
    )
    rows = db.execute(
        select(Prescription, Visit.ticket_code, Visit.final_priority)
        .options(selectinload(Prescription.items))
        .join(Visit, Visit.id == Prescription.visit_id)
        .where(Prescription.status == "ACTIVE", Visit.status == VisitStatus.COMPLETED)
        .order_by(priority_order, Prescription.created_at.asc())
        .limit(500)
    ).all()
    result = []
    for prescription, ticket_code, priority in rows:
        prescription.ticket_code = ticket_code
        prescription.priority = priority
        result.append(prescription)
    return result


@router.get("/prescriptions/{prescription_id}", response_model=PrescriptionRead)
def get_prescription(prescription_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("prescription:read"))):
    prescription = db.scalar(select(Prescription).options(selectinload(Prescription.items)).where(Prescription.id == prescription_id))
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return prescription


@router.post("/prescriptions/{prescription_id}/cancel-by-doctor", response_model=PrescriptionRead)
def cancel_by_doctor(
    prescription_id: int,
    data: PrescriptionCancelCreate,
    doctor_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("prescription:create")),
):
    visit_id = db.scalar(select(Prescription.visit_id).where(Prescription.id == prescription_id))
    if visit_id is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    try:
        visit = get_visit_or_404(db, visit_id, for_update=True)
        prescription = db.scalar(
            select(Prescription)
            .options(selectinload(Prescription.items))
            .where(Prescription.id == prescription_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found")
        return cancel_prescription_by_doctor(db, prescription, visit, data, user, doctor_id)
    except Exception:
        db.rollback()
        raise


@router.patch("/prescriptions/{prescription_id}", response_model=PrescriptionRead)
def update_prescription_status(prescription_id: int, data: dict, db: Session = Depends(get_db), user: User = Depends(require_permission("prescription:update"))):
    visit_id = db.scalar(select(Prescription.visit_id).where(Prescription.id == prescription_id))
    if visit_id is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    status = str(data.get("status", "")).upper()
    if status not in {"ACTIVE", "DISPENSED", "CANCELLED"}:
        raise HTTPException(status_code=422, detail="Status must be ACTIVE, DISPENSED, or CANCELLED")
    try:
        visit = get_visit_or_404(db, visit_id, for_update=True)
        prescription = db.scalar(
            select(Prescription)
            .options(selectinload(Prescription.items))
            .where(Prescription.id == prescription_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found")
        return change_prescription_status(db, prescription, visit, status, user)
    except Exception:
        db.rollback()
        raise
