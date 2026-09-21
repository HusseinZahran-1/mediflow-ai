from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.enums import Priority, VisitStatus
from app.core.permissions import require_permission
from app.models import AuditLog, Department, Doctor, Patient, Room, User, Visit
from app.schemas import AuditRead, CompletedVisitItem, CompletedVisitPage, DashboardMetrics, RoomCreate, RoomRead, UserCreate, UserRead
from app.services.auth_service import create_user


router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/users", response_model=list[UserRead])
def users(db: Session = Depends(get_db), _: User = Depends(require_permission("admin:manage_users"))):
    return list(db.scalars(select(User).order_by(User.full_name)))


@router.post("/users", response_model=UserRead, status_code=201)
def add_user(data: UserCreate, db: Session = Depends(get_db), actor: User = Depends(require_permission("admin:manage_users"))):
    return create_user(db, data, actor.id)


@router.post("/rooms", response_model=RoomRead, status_code=201)
def add_room(data: RoomCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("admin:manage_users"))):
    if not db.get(Department, data.department_id):
        raise HTTPException(status_code=404, detail="Department not found")
    if db.scalar(select(Room.id).where(Room.department_id == data.department_id, Room.room_number == data.room_number)) is not None:
        raise HTTPException(status_code=409, detail="Room number already exists in this department")
    room = Room(**data.model_dump())
    db.add(room)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Room number already exists in this department") from exc
    db.refresh(room)
    return room


@router.get("/rooms", response_model=list[RoomRead])
def rooms(department_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(require_permission("queue:read"))):
    stmt = select(Room)
    if department_id:
        stmt = stmt.where(Room.department_id == department_id)
    return list(db.scalars(stmt.order_by(Room.room_number)))


@router.get("/doctors")
def doctors(db: Session = Depends(get_db), _: User = Depends(require_permission("admin:manage_users"))):
    rows = list(db.scalars(
        select(Doctor)
        .options(selectinload(Doctor.user), selectinload(Doctor.department))
        .order_by(Doctor.id)
    ))
    return [
        {
            "id": doctor.id,
            "user_id": doctor.user_id,
            "full_name": doctor.user.full_name,
            "email": doctor.user.email,
            "is_active": doctor.user.is_active,
            "department_id": doctor.department_id,
            "department": doctor.department.name,
            "specialization": doctor.specialization,
            "medical_license_number": doctor.medical_license_number,
        }
        for doctor in rows
    ]


@router.post("/doctors", status_code=201)
def add_doctor(
    user_id: int,
    department_id: int,
    specialization: str,
    medical_license_number: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("admin:manage_users")),
):
    user = db.get(User, user_id)
    if not user or user.role.value != "DOCTOR":
        raise HTTPException(status_code=422, detail="A DOCTOR user is required")
    if not db.get(Department, department_id):
        raise HTTPException(status_code=404, detail="Department not found")
    if user.doctor:
        raise HTTPException(status_code=409, detail="This user already has a doctor profile")
    specialization = specialization.strip()
    medical_license_number = medical_license_number.strip()
    if not specialization or not medical_license_number:
        raise HTTPException(status_code=422, detail="Specialization and medical license number are required")
    if db.scalar(select(Doctor.id).where(Doctor.medical_license_number == medical_license_number)) is not None:
        raise HTTPException(status_code=409, detail="Medical license number is already registered")
    doctor = Doctor(user_id=user_id, department_id=department_id, specialization=specialization, medical_license_number=medical_license_number)
    db.add(doctor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Doctor profile or medical license already exists") from exc
    db.refresh(doctor)
    return {"id": doctor.id, "user_id": doctor.user_id, "department_id": doctor.department_id, "specialization": doctor.specialization, "medical_license_number": doctor.medical_license_number}


FINALIZED_VISIT_STATUSES = (
    VisitStatus.COMPLETED,
    VisitStatus.DISCHARGED,
    VisitStatus.ADMITTED,
    VisitStatus.TRANSFERRED,
    VisitStatus.CANCELLED,
    VisitStatus.LEFT_WITHOUT_BEING_SEEN,
)


@router.get("/completed-visits", response_model=CompletedVisitPage)
def completed_visits(
    search: str | None = Query(default=None, max_length=120),
    status: VisitStatus | None = None,
    department_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("admin:completed_visits")),
):
    if status is not None and status not in FINALIZED_VISIT_STATUSES:
        raise HTTPException(status_code=422, detail="Only finalized visit statuses can be requested")

    filters = [Visit.status.in_(FINALIZED_VISIT_STATUSES)]
    if status is not None:
        filters.append(Visit.status == status)
    if department_id is not None:
        filters.append(Visit.department_id == department_id)
    normalized_search = (search or "").strip()
    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(or_(
            Visit.ticket_code.ilike(pattern),
            Patient.full_name.ilike(pattern),
            Patient.medical_record_number.ilike(pattern),
            Patient.identity_number.ilike(pattern),
            Patient.phone_number.ilike(pattern),
        ))

    total = int(db.scalar(
        select(func.count(Visit.id))
        .join(Patient, Visit.patient_id == Patient.id)
        .where(*filters)
    ) or 0)

    visits = list(db.scalars(
        select(Visit)
        .join(Patient, Visit.patient_id == Patient.id)
        .options(
            selectinload(Visit.patient),
            selectinload(Visit.department),
            selectinload(Visit.assigned_doctor).selectinload(Doctor.user),
            selectinload(Visit.consultation),
        )
        .where(*filters)
        .order_by(Visit.completed_at.desc(), Visit.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ))

    items: list[CompletedVisitItem] = []
    for visit in visits:
        duration_minutes = None
        if visit.completed_at and visit.arrival_time:
            completed_at = visit.completed_at
            arrival_time = visit.arrival_time
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=UTC)
            if arrival_time.tzinfo is None:
                arrival_time = arrival_time.replace(tzinfo=UTC)
            duration_minutes = max(0, int((completed_at - arrival_time).total_seconds() // 60))
        consultation = visit.consultation
        doctor_name = visit.assigned_doctor.user.full_name if visit.assigned_doctor and visit.assigned_doctor.user else None
        items.append(CompletedVisitItem(
            visit_id=visit.id,
            patient_id=visit.patient_id,
            medical_record_number=visit.patient.medical_record_number,
            patient_name=visit.patient.full_name,
            phone_number=visit.patient.phone_number,
            gender=visit.patient.gender,
            age=visit.patient.age,
            identity_number=visit.patient.identity_number,
            ticket_code=visit.ticket_code,
            department_id=visit.department_id,
            department_name=visit.department.name,
            assigned_doctor_id=visit.assigned_doctor_id,
            doctor_name=doctor_name,
            priority=visit.final_priority,
            status=visit.status,
            arrival_time=visit.arrival_time,
            started_at=visit.started_at,
            completed_at=visit.completed_at,
            duration_minutes=duration_minutes,
            diagnosis=consultation.diagnosis if consultation else None,
            clinical_notes=consultation.clinical_notes if consultation else None,
            treatment_plan=consultation.treatment_plan if consultation else None,
        ))

    return CompletedVisitPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/audit-logs", response_model=list[AuditRead])
def audit_logs(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), _: User = Depends(require_permission("audit:read"))):
    return list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)))


@router.get("/metrics", response_model=DashboardMetrics)
def metrics(db: Session = Depends(get_db), _: User = Depends(require_permission("queue:read"))):
    today = date.today()
    visits_today = list(db.scalars(select(Visit).where(func.date(Visit.arrival_time) == today)))
    waiting_statuses = {VisitStatus.WAITING_FOR_TRIAGE, VisitStatus.IN_TRIAGE, VisitStatus.TRIAGE_COMPLETED, VisitStatus.WAITING_FOR_DOCTOR, VisitStatus.CALLED}
    waiting = [v for v in visits_today if v.status in waiting_statuses]
    now = datetime.now(UTC)
    waits = []
    for visit in waiting:
        arrival = visit.arrival_time if visit.arrival_time.tzinfo else visit.arrival_time.replace(tzinfo=UTC)
        waits.append(max(0, int((now - arrival).total_seconds() // 60)))
    by_department = db.execute(
        select(Department.name, func.count(Visit.id)).join(Visit, Visit.department_id == Department.id).where(func.date(Visit.arrival_time) == today).group_by(Department.name)
    ).all()
    return DashboardMetrics(
        patients_today=len(visits_today),
        waiting=len(waiting),
        critical=sum(v.final_priority == Priority.CRITICAL for v in waiting),
        urgent=sum(v.final_priority == Priority.URGENT for v in waiting),
        normal=sum(v.final_priority == Priority.NORMAL for v in waiting),
        completed=sum(v.status in {VisitStatus.COMPLETED, VisitStatus.DISCHARGED} for v in visits_today),
        average_wait_minutes=round(sum(waits) / len(waits), 1) if waits else 0,
        longest_wait_minutes=max(waits, default=0),
        by_department=[{"department": name, "patients": count} for name, count in by_department],
    )

