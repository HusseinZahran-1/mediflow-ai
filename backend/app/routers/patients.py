from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models import InsurancePolicy, User, Visit
from app.schemas import (
    InsuranceCreate,
    InsuranceRead,
    InsuranceUpdate,
    PatientCreate,
    PatientPage,
    PatientRead,
    PatientUpdate,
    VisitRead,
)
from app.services.patient_service import add_insurance, create_patient, get_patient_or_404, list_patients, merge_patients, update_patient


router = APIRouter(tags=["Patients"])


@router.post("/patients", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create(data: PatientCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission("patient:create"))):
    return create_patient(db, data, user.id, request.client.host if request.client else None)


@router.get("/patients", response_model=PatientPage)
def list_all(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("patient:read")),
):
    items, total = list_patients(db, page, page_size, q)
    return PatientPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/patients/search", response_model=PatientPage)
def search_patients(q: str = Query(min_length=1), db: Session = Depends(get_db), _: User = Depends(require_permission("patient:read"))):
    items, total = list_patients(db, 1, 50, q)
    return PatientPage(items=items, total=total, page=1, page_size=50)


@router.get("/patients/{patient_id}", response_model=PatientRead)
def get_one(patient_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("patient:read"))):
    return get_patient_or_404(db, patient_id)


@router.patch("/patients/{patient_id}", response_model=PatientRead)
def patch_patient(patient_id: int, data: PatientUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("patient:update"))):
    return update_patient(db, get_patient_or_404(db, patient_id), data, user.id)


@router.post("/patients/{patient_id}/insurance", response_model=InsuranceRead, status_code=201)
def create_insurance(patient_id: int, data: InsuranceCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("insurance:manage"))):
    return add_insurance(db, patient_id, data, user.id)


@router.get("/patients/{patient_id}/insurance", response_model=list[InsuranceRead])
def list_insurance(patient_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("patient:read"))):
    get_patient_or_404(db, patient_id)
    return list(db.scalars(select(InsurancePolicy).where(InsurancePolicy.patient_id == patient_id).order_by(InsurancePolicy.created_at.desc())))


@router.patch("/insurance/{insurance_id}", response_model=InsuranceRead)
def patch_insurance(insurance_id: int, data: InsuranceUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("insurance:manage"))):
    policy = db.get(InsurancePolicy, insurance_id)
    if not policy:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Insurance policy not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(policy, key, value)
    db.commit()
    db.refresh(policy)
    return policy


@router.get("/patients/{patient_id}/visits", response_model=list[VisitRead])
def patient_visits(patient_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("visit:read"))):
    get_patient_or_404(db, patient_id)
    return list(db.scalars(select(Visit).where(Visit.patient_id == patient_id).order_by(Visit.created_at.desc())))


@router.post("/patients/{source_id}/merge/{target_id}", response_model=PatientRead)
def merge_patient_records(source_id: int, target_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("admin:manage_users"))):
    return merge_patients(db, source_id, target_id, user.id)
