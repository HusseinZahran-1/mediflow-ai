from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import VisitStatus
from app.models import Triage, User, Visit
from app.schemas import TriageCreate, TriageFinalize
from app.services.ai_service import create_prediction
from app.services.audit import audit
from app.services.visit_service import get_visit_or_404, priority_score, transition_visit


def _prediction_features(visit: Visit, data: TriageCreate) -> dict:
    return {
        "age": visit.patient.age,
        "gender": visit.patient.gender,
        "temperature": data.temperature,
        "heart_rate": data.heart_rate,
        "respiratory_rate": data.respiratory_rate,
        "systolic_bp": data.systolic_bp,
        "diastolic_bp": data.diastolic_bp,
        "oxygen_saturation": data.oxygen_saturation,
        "pain_level": data.pain_level,
        "arrival_method": visit.arrival_method.value,
        "chief_complaint": data.chief_complaint,
        # INTENTIONAL EDUCATIONAL LEAKAGE: the demo model receives the nurse's own priority.
        "human_priority_leak": data.human_priority.value,
        "medical_history": data.chronic_diseases,
        "consciousness_level": data.consciousness_level,
        "severe_bleeding": data.severe_bleeding,
        "difficulty_breathing": data.difficulty_breathing,
        "chest_pain": data.chest_pain,
        "seizure": data.seizure,
        "loss_of_consciousness": data.loss_of_consciousness,
        "severe_allergy": data.severe_allergy,
        "pregnancy": data.pregnancy,
        "recent_surgery": data.recent_surgery,
    }


def create_triage(db: Session, visit_id: int, data: TriageCreate, user: User) -> Triage:
    visit = get_visit_or_404(db, visit_id, for_update=True)
    if db.scalar(select(Triage.id).where(Triage.visit_id == visit.id)) is not None:
        raise HTTPException(status_code=409, detail="Triage already exists for this visit")
    if visit.status == VisitStatus.WAITING_FOR_TRIAGE:
        transition_visit(db, visit, VisitStatus.IN_TRIAGE, user.id, commit=False)
    if visit.status != VisitStatus.IN_TRIAGE:
        raise HTTPException(status_code=409, detail="Visit is not ready for triage")
    triage = Triage(visit_id=visit.id, **data.model_dump())
    visit.human_priority = data.human_priority
    db.add(triage)
    db.flush()
    prediction = create_prediction(db, visit, _prediction_features(visit, data), commit=False)
    triage.ai_priority = prediction.prediction
    triage.ai_confidence = prediction.confidence
    audit(db, user_id=user.id, action="TRIAGE_CREATED", entity_type="Triage", entity_id=triage.id, new_data={"visit_id": visit.id, "human_priority": data.human_priority.value, "ai_priority": prediction.prediction.value})
    db.commit()
    db.refresh(triage)
    return triage


def update_triage(db: Session, visit_id: int, data: TriageCreate, user: User) -> Triage:
    visit = get_visit_or_404(db, visit_id, for_update=True)
    triage = db.scalar(
        select(Triage)
        .where(Triage.visit_id == visit.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not triage:
        raise HTTPException(status_code=404, detail="Triage not found")
    if visit.status != VisitStatus.IN_TRIAGE:
        raise HTTPException(status_code=409, detail="Visit is no longer in triage")
    if triage.finalized_at:
        raise HTTPException(status_code=409, detail="Finalized triage cannot be edited")
    for key, value in data.model_dump().items():
        setattr(triage, key, value)
    visit.human_priority = data.human_priority
    prediction = create_prediction(db, visit, _prediction_features(visit, data), commit=False)
    triage.ai_priority = prediction.prediction
    triage.ai_confidence = prediction.confidence
    audit(db, user_id=user.id, action="TRIAGE_UPDATED", entity_type="Triage", entity_id=triage.id, new_data={"visit_id": visit.id, "human_priority": data.human_priority.value, "ai_priority": prediction.prediction.value})
    db.commit()
    db.refresh(triage)
    return triage


def finalize_triage(db: Session, visit_id: int, data: TriageFinalize, user: User) -> Triage:
    visit = get_visit_or_404(db, visit_id, for_update=True)
    triage = db.scalar(
        select(Triage)
        .where(Triage.visit_id == visit.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not triage:
        raise HTTPException(status_code=404, detail="Triage not found")
    if visit.status != VisitStatus.IN_TRIAGE:
        raise HTTPException(status_code=409, detail="Visit is no longer in triage")
    if triage.finalized_at:
        raise HTTPException(status_code=409, detail="Triage has already been finalized")
    if triage.ai_priority and data.final_priority != triage.ai_priority and not data.disagreement_reason:
        raise HTTPException(status_code=422, detail="A disagreement reason is required when overriding the AI recommendation")
    triage.final_priority = data.final_priority
    triage.disagreement_reason = data.disagreement_reason
    triage.finalized_by = user.id
    triage.finalized_at = datetime.now(UTC)
    visit.final_priority = data.final_priority
    visit.priority_score = priority_score(data.final_priority)
    transition_visit(db, visit, VisitStatus.TRIAGE_COMPLETED, user.id, commit=False)
    transition_visit(db, visit, VisitStatus.WAITING_FOR_DOCTOR, user.id, commit=False)
    audit(db, user_id=user.id, action="TRIAGE_FINALIZED", entity_type="Triage", entity_id=triage.id, new_data={"final_priority": data.final_priority.value, "disagreement_reason": data.disagreement_reason})
    db.commit()
    db.refresh(triage)
    return triage
