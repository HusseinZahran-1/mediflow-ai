from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models import AIPrediction, User
from app.schemas import AIPredictRequest, AIPredictionRead, AIReview, OCRResponse
from app.services.ai_service import create_prediction
from app.services.visit_service import get_visit_or_404


router = APIRouter(prefix="/ai", tags=["AI Decision Support"])

ALLOWED_OCR_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_OCR_BYTES = 5 * 1024 * 1024


@router.post("/triage/predict", response_model=AIPredictionRead)
def predict(data: AIPredictRequest, db: Session = Depends(get_db), _: User = Depends(require_permission("ai:predict"))):
    visit = get_visit_or_404(db, data.visit_id)
    features = data.model_dump(exclude={"visit_id"}, mode="json")
    return create_prediction(db, visit, features)


@router.get("/predictions/{visit_id}", response_model=list[AIPredictionRead])
def predictions(visit_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("visit:read"))):
    get_visit_or_404(db, visit_id)
    return list(db.scalars(select(AIPrediction).where(AIPrediction.visit_id == visit_id).order_by(AIPrediction.created_at.desc())))


@router.post("/predictions/{prediction_id}/review", response_model=AIPredictionRead)
def review(prediction_id: int, data: AIReview, db: Session = Depends(get_db), user: User = Depends(require_permission("ai:review"))):
    prediction = db.get(AIPrediction, prediction_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="AI prediction not found")
    prediction.accepted_by_user = data.accepted
    prediction.reviewed_by = user.id
    db.commit()
    db.refresh(prediction)
    return prediction


@router.post("/ocr/extract", response_model=OCRResponse)
async def extract_document_text(
    image: UploadFile = File(...),
    _: User = Depends(require_permission("ocr:extract")),
):
    if image.content_type not in ALLOWED_OCR_TYPES:
        raise HTTPException(status_code=422, detail="Only JPEG, PNG, and WebP images are accepted")
    content = await image.read(MAX_OCR_BYTES + 1)
    if len(content) > MAX_OCR_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 5 MB limit")
    try:
        candidate = Image.open(BytesIO(content))
        candidate.verify()
        candidate = Image.open(BytesIO(content)).convert("RGB")
        if candidate.width * candidate.height > 20_000_000:
            raise HTTPException(status_code=413, detail="Image dimensions are too large")
        candidate.thumbnail((2400, 2400))
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=422, detail="The uploaded file is not a valid image") from exc
    import pytesseract

    try:
        text = pytesseract.image_to_string(candidate, config="--psm 6").strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise HTTPException(status_code=503, detail="OCR service is not installed on this server") from exc
    return OCRResponse(raw_text=text)
