from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models import User
from app.schemas import QueueItem
from app.services.clinical_service import doctor_for_user
from app.services.queue_service import get_queue


router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("/me/queue", response_model=list[QueueItem])
def my_queue(doctor_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db), user: User = Depends(require_permission("queue:read"))):
    doctor = doctor_for_user(user, db, doctor_id)
    return get_queue(db, doctor.department_id, doctor.id)
