from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import VisitStatus
from app.core.permissions import require_permission
from app.core.security import decode_token
from app.models import User
from app.schemas import CallRequest, DisplayItem, QueueItem, VisitRead
from app.services.clinical_service import complete_consultation, doctor_for_user
from app.services.queue_service import get_display_queue, get_queue
from app.services.visit_service import assign_doctor, assign_room, get_visit_or_404, transition_visit
from app.websocket.manager import manager


router = APIRouter(tags=["Queue & Realtime"])


@router.get("/queue", response_model=list[QueueItem])
def queue(department_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(require_permission("queue:read"))):
    return get_queue(db, department_id)


@router.get("/queue/{department_id}", response_model=list[QueueItem])
def department_queue(department_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("queue:read"))):
    return get_queue(db, department_id)


@router.get("/display/queue", response_model=list[DisplayItem])
def display_queue(department_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(require_permission("display:read"))):
    return get_display_queue(db, department_id)


@router.post("/queue/{visit_id}/call", response_model=VisitRead)
async def call(visit_id: int, data: CallRequest, doctor_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db), user: User = Depends(require_permission("queue:call"))):
    doctor = doctor_for_user(user, db, doctor_id)
    visit = get_visit_or_404(db, visit_id, for_update=True)
    if visit.status != VisitStatus.WAITING_FOR_DOCTOR:
        raise HTTPException(status_code=409, detail="Visit is not waiting for a doctor")
    if visit.final_priority is None:
        raise HTTPException(status_code=409, detail="Triage must be finalized before the patient can be called")
    if visit.department_id != doctor.department_id:
        raise HTTPException(status_code=403, detail="Visit belongs to another department")
    if visit.assigned_doctor_id and visit.assigned_doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Visit is assigned to another doctor")
    try:
        assign_doctor(
            db,
            visit,
            doctor.id,
            user.id,
            actor_role=user.role,
            allow_reassignment=False,
            commit=False,
        )
        assign_room(db, visit, data.room_id, user.id, commit=False)
        transition_visit(db, visit, VisitStatus.CALLED, user.id, commit=False)
        db.commit()
        db.refresh(visit)
    except Exception:
        db.rollback()
        raise
    await manager.broadcast({"event": "PATIENT_CALLED", "ticket": visit.ticket_code, "room": visit.assigned_room.room_number, "priority": visit.final_priority.value})
    return visit


@router.post("/queue/{visit_id}/recall", response_model=VisitRead)
async def recall(visit_id: int, doctor_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db), user: User = Depends(require_permission("queue:call"))):
    doctor = doctor_for_user(user, db, doctor_id)
    visit = get_visit_or_404(db, visit_id)
    if visit.status != VisitStatus.CALLED or not visit.assigned_room:
        raise HTTPException(status_code=409, detail="Only a called patient can be recalled")
    if visit.assigned_doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Visit is assigned to another doctor")
    await manager.broadcast({"event": "PATIENT_RECALLED", "ticket": visit.ticket_code, "room": visit.assigned_room.room_number, "priority": visit.final_priority.value})
    return visit


@router.post("/queue/{visit_id}/skip", response_model=VisitRead)
def skip(visit_id: int, doctor_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db), user: User = Depends(require_permission("queue:call"))):
    doctor = doctor_for_user(user, db, doctor_id)
    visit = get_visit_or_404(db, visit_id, for_update=True)
    if visit.assigned_doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Visit is assigned to another doctor")
    if visit.status == VisitStatus.CALLED:
        return transition_visit(db, visit, VisitStatus.WAITING_FOR_DOCTOR, user.id)
    raise HTTPException(status_code=409, detail="Only a called patient can be skipped")


@router.post("/queue/{visit_id}/complete", response_model=VisitRead)
def complete(visit_id: int, doctor_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db), user: User = Depends(require_permission("visit:clinical"))):
    complete_consultation(db, visit_id, user, doctor_id)
    return get_visit_or_404(db, visit_id)


@router.websocket("/ws/display")
async def display_websocket(websocket: WebSocket):
    token = websocket.query_params.get("token")
    try:
        payload = decode_token(token or "", "access")
        if payload.get("role") not in {"DISPLAY", "ADMIN"}:
            await websocket.close(code=1008)
            return
    except HTTPException:
        await websocket.close(code=1008)
        return
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
