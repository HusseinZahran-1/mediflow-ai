import base64
import io

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.enums import UserRole, VisitStatus
from app.core.permissions import require_permission
from app.models import User, Visit
from app.schemas import VisitClosureCreate, VisitCreate, VisitDispositionCreate, VisitRead, VisitUpdate
from app.services.visit_service import assign_doctor, assign_room, close_visit, create_visit, get_visit_or_404, set_visit_disposition


router = APIRouter(prefix="/visits", tags=["Visits"])


@router.post("", response_model=VisitRead, status_code=201)
def create(data: VisitCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("visit:create"))):
    return create_visit(db, data, user.id)


@router.get("/active", response_model=list[VisitRead])
def active_visits(
    department_id: int | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("visit:read")),
):
    terminal = [VisitStatus.COMPLETED, VisitStatus.DISCHARGED, VisitStatus.ADMITTED, VisitStatus.TRANSFERRED, VisitStatus.CANCELLED, VisitStatus.LEFT_WITHOUT_BEING_SEEN]
    stmt = select(Visit).where(Visit.status.not_in(terminal))
    if department_id:
        stmt = stmt.where(Visit.department_id == department_id)
    return list(db.scalars(stmt.order_by(Visit.arrival_time).limit(limit)))


@router.get("/{visit_id}", response_model=VisitRead)
def get_visit(visit_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("visit:read"))):
    return get_visit_or_404(db, visit_id)


@router.post("/{visit_id}/closure", response_model=VisitRead)
def closure(
    visit_id: int,
    data: VisitClosureCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("visit:close")),
):
    return close_visit(db, visit_id, data, user)


@router.post("/{visit_id}/disposition", response_model=VisitRead)
def disposition(
    visit_id: int,
    data: VisitDispositionCreate,
    doctor_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("visit:clinical")),
):
    return set_visit_disposition(db, visit_id, data, user, doctor_id)


@router.patch("/{visit_id}", response_model=VisitRead)
def patch_visit(visit_id: int, data: VisitUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("visit:clinical"))):
    visit = get_visit_or_404(db, visit_id, for_update=True)
    if data.status is not None:
        raise HTTPException(status_code=422, detail="Use the dedicated triage, queue, consultation, or diagnostic workflow endpoint to change status")
    try:
        if data.assigned_doctor_id is not None:
            if user.role != UserRole.ADMIN and (not user.doctor or data.assigned_doctor_id != user.doctor.id):
                raise HTTPException(status_code=403, detail="Doctors may only assign visits to themselves")
            assign_doctor(
                db,
                visit,
                data.assigned_doctor_id,
                user.id,
                actor_role=user.role,
                allow_reassignment=user.role == UserRole.ADMIN,
                commit=False,
            )
        if data.assigned_room_id is not None:
            if user.role != UserRole.ADMIN and (not user.doctor or visit.assigned_doctor_id != user.doctor.id):
                raise HTTPException(status_code=403, detail="Visit is assigned to another doctor")
            assign_room(db, visit, data.assigned_room_id, user.id, commit=False)
        db.commit()
        db.refresh(visit)
    except Exception:
        db.rollback()
        raise
    return visit


@router.post("/{visit_id}/assign-doctor", response_model=VisitRead)
def set_doctor(visit_id: int, doctor_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("visit:clinical"))):
    if user.role != UserRole.ADMIN and (not user.doctor or doctor_id != user.doctor.id):
        raise HTTPException(status_code=403, detail="Doctors may only assign visits to themselves")
    return assign_doctor(
        db,
        get_visit_or_404(db, visit_id, for_update=True),
        doctor_id,
        user.id,
        actor_role=user.role,
        allow_reassignment=user.role == UserRole.ADMIN,
    )


@router.post("/{visit_id}/assign-room", response_model=VisitRead)
def set_room(visit_id: int, room_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("visit:clinical"))):
    visit = get_visit_or_404(db, visit_id, for_update=True)
    if user.role != UserRole.ADMIN and (not user.doctor or visit.assigned_doctor_id != user.doctor.id):
        raise HTTPException(status_code=403, detail="Visit is assigned to another doctor")
    return assign_room(db, visit, room_id, user.id)


@router.get("/{visit_id}/ticket")
def ticket(visit_id: int, request: Request, db: Session = Depends(get_db), _: User = Depends(require_permission("visit:read"))):
    visit = get_visit_or_404(db, visit_id)
    public_url = f"{str(request.base_url).rstrip('/')}{settings.API_V1_PREFIX}/visits/public/{visit.public_token}"
    image = qrcode.make(public_url)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return {
        "hospital": settings.HOSPITAL_NAME,
        "ticket_code": visit.ticket_code,
        "priority": visit.final_priority.value if visit.final_priority else "PENDING TRIAGE",
        "department": visit.department.name,
        "room": visit.assigned_room.room_number if visit.assigned_room else None,
        "registered_at": visit.arrival_time,
        "qr_png_base64": base64.b64encode(output.getvalue()).decode(),
        "public_status_url": public_url,
        "instructions": "Keep this ticket and watch the waiting-room display.",
    }


@router.get("/public/{public_token}")
def public_status(public_token: str, db: Session = Depends(get_db)):
    visit = db.scalar(select(Visit).where(Visit.public_token == public_token))
    if not visit:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"ticket_code": visit.ticket_code, "department": visit.department.name, "status": visit.status, "room": visit.assigned_room.room_number if visit.assigned_room else None}
