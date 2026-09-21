from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import VisitStatus
from app.models import InsurancePolicy, Patient, Visit
from app.schemas import InsuranceCreate, PatientCreate, PatientUpdate
from app.services.audit import audit


def _generate_mrn(db: Session) -> str:
    year = date.today().year
    # Serialize MRN allocation in PostgreSQL so concurrent registrations cannot
    # select the same next sequence. SQLite tests remain unaffected.
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 9_100_000 + year})
    prefix = f"MRN-{year}-"
    last = db.scalar(
        select(Patient.medical_record_number)
        .where(Patient.medical_record_number.like(f"{prefix}%"))
        .order_by(Patient.medical_record_number.desc())
        .limit(1)
    )
    sequence = int(last.rsplit("-", 1)[-1]) + 1 if last else 1
    return f"{prefix}{sequence:06d}"


def create_patient(db: Session, data: PatientCreate, user_id: int, ip_address: str | None = None) -> Patient:
    if db.scalar(select(Patient).where(Patient.identity_number == data.identity_number)):
        raise HTTPException(status_code=409, detail="Identity number is already registered")
    if data.military_number and db.scalar(select(Patient).where(Patient.military_number == data.military_number)):
        raise HTTPException(status_code=409, detail="Military number is already registered")
    try:
        patient = Patient(medical_record_number=_generate_mrn(db), **data.model_dump())
        db.add(patient)
        db.flush()
        audit(db, user_id=user_id, action="PATIENT_CREATED", entity_type="Patient", entity_id=patient.id, new_data={"medical_record_number": patient.medical_record_number}, ip_address=ip_address)
        db.commit()
        db.refresh(patient)
        return patient
    except IntegrityError as exc:
        # Database uniqueness is the final guard against concurrent duplicate registrations.
        db.rollback()
        raise HTTPException(status_code=409, detail="Patient identity or military number is already registered") from exc


def list_patients(db: Session, page: int, page_size: int, query: str | None = None) -> tuple[list[Patient], int]:
    stmt = select(Patient).where(Patient.is_active.is_(True))
    if query:
        term = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                Patient.full_name.ilike(term),
                Patient.identity_number.ilike(term),
                Patient.medical_record_number.ilike(term),
                Patient.phone_number.ilike(term),
            )
        )
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    items = list(db.scalars(stmt.order_by(Patient.created_at.desc()).offset((page - 1) * page_size).limit(page_size)))
    return items, total


def get_patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def merge_patients(db: Session, source_id: int, target_id: int, user_id: int) -> Patient:
    if source_id == target_id:
        raise HTTPException(status_code=422, detail="Source and target patients must be different")
    source = get_patient_or_404(db, source_id)
    target = get_patient_or_404(db, target_id)
    if not source.is_active or source.merged_into_id:
        raise HTTPException(status_code=409, detail="Source patient has already been merged")
    if not target.is_active or target.merged_into_id:
        raise HTTPException(status_code=409, detail="Target patient is not an active patient record")

    active_filter = Visit.status.notin_([
        VisitStatus.COMPLETED, VisitStatus.DISCHARGED, VisitStatus.ADMITTED, VisitStatus.TRANSFERRED,
        VisitStatus.CANCELLED, VisitStatus.LEFT_WITHOUT_BEING_SEEN,
    ])
    source_has_active = db.scalar(select(Visit.id).where(Visit.patient_id == source.id, active_filter).limit(1)) is not None
    target_has_active = db.scalar(select(Visit.id).where(Visit.patient_id == target.id, active_filter).limit(1)) is not None
    if source_has_active and target_has_active:
        raise HTTPException(
            status_code=409,
            detail="Cannot merge patient records while both records have active visits",
        )

    db.execute(update(InsurancePolicy).where(InsurancePolicy.patient_id == source.id).values(patient_id=target.id))
    db.execute(update(Visit).where(Visit.patient_id == source.id).values(patient_id=target.id))
    old_identity = source.identity_number
    source.is_active = False
    source.merged_into_id = target.id
    source.identity_number = f"MERGED-{source.id}-{source.medical_record_number}"
    source.military_number = None
    audit(
        db,
        user_id=user_id,
        action="PATIENT_RECORD_MERGED",
        entity_type="Patient",
        entity_id=source.id,
        old_data={"identity_number": old_identity},
        new_data={"merged_into_id": target.id},
    )
    db.commit()
    db.refresh(target)
    return target


def update_patient(db: Session, patient: Patient, data: PatientUpdate, user_id: int) -> Patient:
    changes = data.model_dump(exclude_unset=True)
    if "identity_number" in changes:
        duplicate_identity = db.scalar(select(Patient.id).where(
            Patient.identity_number == changes["identity_number"],
            Patient.id != patient.id,
        ))
        if duplicate_identity is not None:
            raise HTTPException(status_code=409, detail="Identity number is already registered")

    resulting_military = changes.get("is_military", patient.is_military)
    resulting_number = changes.get("military_number", patient.military_number)
    if resulting_military and not resulting_number:
        raise HTTPException(status_code=422, detail="military_number is required for military patients")
    if not resulting_military:
        changes["military_number"] = None
        resulting_number = None
    if resulting_number:
        duplicate_military = db.scalar(select(Patient.id).where(
            Patient.military_number == resulting_number,
            Patient.id != patient.id,
        ))
        if duplicate_military is not None:
            raise HTTPException(status_code=409, detail="Military number is already registered")

    old = {key: getattr(patient, key) for key in changes}
    for key, value in changes.items():
        setattr(patient, key, value)
    audit(db, user_id=user_id, action="PATIENT_UPDATED", entity_type="Patient", entity_id=patient.id, old_data=old, new_data=changes)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Patient identity or military number is already registered") from exc
    db.refresh(patient)
    return patient


def add_insurance(db: Session, patient_id: int, data: InsuranceCreate, user_id: int) -> InsurancePolicy:
    get_patient_or_404(db, patient_id)
    policy = InsurancePolicy(patient_id=patient_id, **data.model_dump())
    db.add(policy)
    db.flush()
    audit(db, user_id=user_id, action="INSURANCE_CREATED", entity_type="InsurancePolicy", entity_id=policy.id, new_data={"patient_id": patient_id, "company_name": policy.company_name})
    db.commit()
    db.refresh(policy)
    return policy
