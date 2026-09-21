from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models import Department, User
from app.schemas import DepartmentCreate, DepartmentRead, DepartmentUpdate


router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("", response_model=list[DepartmentRead])
def list_departments(db: Session = Depends(get_db), _: User = Depends(require_permission("department:read"))):
    return list(db.scalars(select(Department).order_by(Department.name)))


@router.post("", response_model=DepartmentRead, status_code=201)
def create_department(data: DepartmentCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("admin:manage_users"))):
    conflict = db.scalar(select(Department.id).where(or_(
        Department.name == data.name, Department.code == data.code, Department.ticket_prefix == data.ticket_prefix,
    )))
    if conflict is not None:
        raise HTTPException(status_code=409, detail="Department name, code, or ticket prefix already exists")
    department = Department(**data.model_dump())
    db.add(department)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Department name, code, or ticket prefix already exists") from exc
    db.refresh(department)
    return department


@router.get("/{department_id}", response_model=DepartmentRead)
def get_department(department_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("department:read"))):
    department = db.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    return department


@router.patch("/{department_id}", response_model=DepartmentRead)
def patch_department(department_id: int, data: DepartmentUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("admin:manage_users"))):
    department = db.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    changes = data.model_dump(exclude_unset=True)
    if changes:
        checks = []
        if "name" in changes:
            checks.append(Department.name == changes["name"])
        if "code" in changes:
            checks.append(Department.code == changes["code"])
        if "ticket_prefix" in changes:
            checks.append(Department.ticket_prefix == changes["ticket_prefix"])
        if checks and db.scalar(select(Department.id).where(Department.id != department.id, or_(*checks))) is not None:
            raise HTTPException(status_code=409, detail="Department name, code, or ticket prefix already exists")
    for key, value in changes.items():
        setattr(department, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Department name, code, or ticket prefix already exists") from exc
    db.refresh(department)
    return department
