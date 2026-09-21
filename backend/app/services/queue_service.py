from datetime import UTC, datetime

from sqlalchemy import case, select
from sqlalchemy.orm import Session, joinedload

from app.core.enums import Priority, VisitStatus
from app.models import Department, Room, Visit
from app.schemas import DisplayItem, QueueItem


ACTIVE_QUEUE_STATUSES = [VisitStatus.WAITING_FOR_DOCTOR, VisitStatus.CALLED, VisitStatus.WITH_DOCTOR]
DISPLAY_QUEUE_STATUSES = [
    VisitStatus.WAITING_FOR_TRIAGE,
    VisitStatus.IN_TRIAGE,
    VisitStatus.TRIAGE_COMPLETED,
    VisitStatus.WAITING_FOR_DOCTOR,
    VisitStatus.CALLED,
]


def get_queue(db: Session, department_id: int | None = None, doctor_id: int | None = None) -> list[QueueItem]:
    priority_order = case(
        (Visit.final_priority == Priority.CRITICAL, 0),
        (Visit.final_priority == Priority.URGENT, 1),
        else_=2,
    )
    stmt = (
        select(Visit)
        .options(joinedload(Visit.patient), joinedload(Visit.department), joinedload(Visit.assigned_room))
        .where(Visit.status.in_(ACTIVE_QUEUE_STATUSES))
    )
    if department_id:
        stmt = stmt.where(Visit.department_id == department_id)
    if doctor_id:
        stmt = stmt.where((Visit.assigned_doctor_id.is_(None)) | (Visit.assigned_doctor_id == doctor_id))
    visits = list(db.scalars(stmt.order_by(priority_order, Visit.arrival_time.asc())))
    now = datetime.now(UTC)
    items: list[QueueItem] = []
    for v in visits:
        arrival = v.arrival_time if v.arrival_time.tzinfo else v.arrival_time.replace(tzinfo=UTC)
        items.append(QueueItem(
            visit_id=v.id,
            ticket_code=v.ticket_code,
            patient_name=v.patient.full_name,
            department_id=v.department_id,
            department=v.department.name,
            priority=v.final_priority or Priority.NORMAL,
            status=v.status,
            arrival_time=v.arrival_time,
            wait_minutes=max(0, int((now - arrival).total_seconds() // 60)),
            room=v.assigned_room.room_number if v.assigned_room else None,
        ))
    return items


def get_display_queue(db: Session, department_id: int | None = None) -> list[DisplayItem]:
    priority_order = case(
        (Visit.final_priority == Priority.CRITICAL, 0),
        (Visit.final_priority == Priority.URGENT, 1),
        (Visit.final_priority == Priority.NORMAL, 2),
        else_=3,
    )
    stmt = (
        select(Visit)
        .options(joinedload(Visit.department), joinedload(Visit.assigned_room))
        .where(Visit.status.in_(DISPLAY_QUEUE_STATUSES))
    )
    if department_id:
        stmt = stmt.where(Visit.department_id == department_id)
    visits = list(db.scalars(stmt.order_by(priority_order, Visit.arrival_time.asc())))
    return [
        DisplayItem(
            ticket_code=visit.ticket_code,
            department=visit.department.name,
            priority=visit.final_priority,
            status=visit.status,
            room=visit.assigned_room.room_number if visit.assigned_room else None,
        )
        for visit in visits
    ]
