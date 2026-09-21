from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models import User
from app.schemas import TriageCreate, TriageFinalize, TriageRead
from app.services.triage_service import create_triage, finalize_triage, update_triage
from app.services.visit_service import get_visit_or_404


router = APIRouter(prefix="/visits/{visit_id}/triage", tags=["Triage"])


@router.post("", response_model=TriageRead, status_code=201)
def create(visit_id: int, data: TriageCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("triage:create"))):
    return create_triage(db, visit_id, data, user)


@router.get("", response_model=TriageRead)
def get(visit_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("visit:read"))):
    triage = get_visit_or_404(db, visit_id).triage
    if not triage:
        raise HTTPException(status_code=404, detail="Triage not found")
    return triage


@router.patch("", response_model=TriageRead)
def update(visit_id: int, data: TriageCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("triage:create"))):
    return update_triage(db, visit_id, data, user)


@router.post("/finalize", response_model=TriageRead)
def finalize(visit_id: int, data: TriageFinalize, db: Session = Depends(get_db), user: User = Depends(require_permission("triage:finalize"))):
    return finalize_triage(db, visit_id, data, user)
