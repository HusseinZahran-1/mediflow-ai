from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import joblib
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import Priority
from app.models import AIPrediction, Visit

logger = logging.getLogger(__name__)


class TriageDecisionSupport:
    def __init__(self) -> None:
        self.pipeline: Any | None = None
        self.model_name = "clinical-rule-engine"
        self.model_version = "1.0.0"
        self.critical_threshold: float | None = None
        self.educational_leakage = False
        self.model_features = [
            "age", "temperature", "heart_rate", "respiratory_rate", "systolic_bp",
            "diastolic_bp", "oxygen_saturation", "pain_level", "gender",
            "arrival_method", "chief_complaint",
        ]
        model_path = Path(settings.AI_MODEL_PATH)
        if not model_path.is_absolute():
            model_path = (Path(__file__).resolve().parents[2] / model_path).resolve()
        if model_path.exists():
            try:
                self.pipeline = joblib.load(model_path)
                self.model_name = "trained-triage-pipeline-hybrid"
                metrics_path = model_path.with_suffix(".metrics.json")
                if metrics_path.exists():
                    report = json.loads(metrics_path.read_text(encoding="utf-8"))
                    self.model_version = str(report.get("model_version", "2.0.0"))
                    self.model_features = list(report.get("features") or self.model_features)
                    leakage = report.get("educational_leakage") or {}
                    self.educational_leakage = bool(leakage.get("enabled"))
                    self.model_name = str(report.get("selected_model") or report.get("best_model") or self.model_name)
                    thresholds = report.get("decision_thresholds") or {}
                    if thresholds.get("CRITICAL") is not None:
                        self.critical_threshold = float(thresholds["CRITICAL"])
                else:
                    self.model_version = "2.0.0"
            except Exception:
                logger.exception("Could not load AI artifact; using declared clinical rule engine")

    def predict(self, features: dict[str, Any]) -> tuple[Priority, float, list[str]]:
        if self.pipeline is not None:
            import pandas as pd

            normalized = dict(features)
            leak_value = None
            if "human_priority_leak" in self.model_features:
                leak_value = normalized.get("human_priority_leak") or normalized.get("human_priority")
                if hasattr(leak_value, "value"):
                    leak_value = leak_value.value
                normalized["human_priority_leak"] = str(leak_value or "").strip().upper() or None
            for feature in self.model_features:
                normalized.setdefault(feature, None)
            normalized["gender"] = str(normalized.get("gender") or "UNKNOWN").upper()
            arrival = str(normalized.get("arrival_method") or "WALKING").upper()
            normalized["arrival_method"] = "AMBULANCE" if arrival == "AMBULANCE" else "WALKING"
            complaint = str(normalized.get("chief_complaint") or "")
            rule_prediction, rule_confidence, rule_factors = self._clinical_rules(features)
            if self.educational_leakage and "human_priority_leak" in self.model_features and not normalized.get("human_priority_leak"):
                return rule_prediction, rule_confidence, [
                    "Educational leakage input was not supplied; transparent safety rules were used instead",
                    *rule_factors,
                ]
            if not self.educational_leakage and (not complaint.strip() or re.search(r"[\u0600-\u06ff]", complaint)):
                return rule_prediction, rule_confidence, [
                    "The trained text model does not cover Arabic or empty complaint text; transparent safety rules were used",
                    *rule_factors,
                ]
            frame = pd.DataFrame([normalized])
            raw_prediction = self.pipeline.predict(frame)[0]
            prediction = Priority(str(raw_prediction))
            confidence = 0.0
            if hasattr(self.pipeline, "predict_proba"):
                probabilities = self.pipeline.predict_proba(frame)[0]
                probability_by_class = {
                    str(label): float(value)
                    for label, value in zip(self.pipeline.classes_, probabilities)
                }
                if self.critical_threshold is not None and probability_by_class.get(Priority.CRITICAL.value, 0.0) >= self.critical_threshold:
                    prediction = Priority.CRITICAL
                confidence = probability_by_class.get(prediction.value, float(max(probabilities)))
            severity = {Priority.NORMAL: 0, Priority.URGENT: 1, Priority.CRITICAL: 2}
            factors = (["Educational leakage demo: prediction uses the nurse-entered human priority and is not a valid independent AI estimate"] if self.educational_leakage else ["Prediction generated by the versioned trained pipeline with deployment-aligned units"])
            if severity[rule_prediction] > severity[prediction]:
                prediction = rule_prediction
                confidence = max(confidence, rule_confidence)
                factors = ["A transparent safety rule raised the trained-model recommendation", *rule_factors]
            elif rule_prediction != Priority.NORMAL and severity[rule_prediction] == severity[prediction]:
                factors = [*factors, "Transparent safety rules independently support this severity", *rule_factors]
            return prediction, confidence, factors
        return self._clinical_rules(features)

    @staticmethod
    def _clinical_rules(features: dict[str, Any]) -> tuple[Priority, float, list[str]]:
        critical: list[str] = []
        urgent: list[str] = []
        spo2 = features.get("oxygen_saturation")
        hr = features.get("heart_rate")
        sbp = features.get("systolic_bp")
        rr = features.get("respiratory_rate")
        temperature = features.get("temperature")
        pain = features.get("pain_level")
        text = (features.get("chief_complaint") or "").lower()
        consciousness = str(features.get("consciousness_level") or "").upper()
        critical_flags = {
            "severe_bleeding": "Severe bleeding flag",
            "seizure": "Seizure flag",
            "loss_of_consciousness": "Loss of consciousness flag",
            "severe_allergy": "Severe allergy flag",
        }
        urgent_flags = {
            "difficulty_breathing": "Difficulty breathing flag",
            "chest_pain": "Chest pain flag",
        }
        critical.extend(reason for field, reason in critical_flags.items() if features.get(field))
        urgent.extend(reason for field, reason in urgent_flags.items() if features.get(field))
        if consciousness in {"UNRESPONSIVE", "RESPONDS_TO_PAIN"}:
            critical.append("Severely impaired consciousness")
        elif consciousness == "RESPONDS_TO_VOICE":
            urgent.append("Impaired consciousness")
        if spo2 is not None and spo2 < 90:
            critical.append("Oxygen saturation below 90%")
        elif spo2 is not None and spo2 < 94:
            urgent.append("Oxygen saturation below 94%")
        if sbp is not None and (sbp < 80 or sbp > 220):
            critical.append("Extreme systolic blood pressure")
        elif sbp is not None and (sbp < 95 or sbp > 180):
            urgent.append("Abnormal systolic blood pressure")
        if hr is not None and (hr < 40 or hr > 150):
            critical.append("Extreme heart rate")
        elif hr is not None and (hr < 50 or hr > 120):
            urgent.append("Abnormal heart rate")
        if rr is not None and (rr < 8 or rr > 35):
            critical.append("Extreme respiratory rate")
        elif rr is not None and rr > 24:
            urgent.append("Elevated respiratory rate")
        if temperature is not None and (temperature < 32 or temperature >= 41):
            critical.append("Extreme body temperature")
        elif temperature is not None and (temperature < 35 or temperature >= 39):
            urgent.append("Abnormal body temperature")
        if any(term in text for term in ["unconscious", "severe bleeding", "seizure", "anaphylaxis", "فاقد الوعي", "نزيف شديد", "تشنج", "حساسية مفرطة"]):
            critical.append("High-risk symptom keyword")
        elif any(term in text for term in ["chest pain", "difficulty breathing", "shortness of breath", "ألم الصدر", "الم في الصدر", "ضيق التنفس", "صعوبة التنفس"]):
            urgent.append("Urgent symptom keyword")
        if pain is not None and pain >= 8:
            urgent.append("Severe pain score")
        if critical:
            return Priority.CRITICAL, min(0.99, 0.86 + 0.03 * len(critical)), critical + urgent
        if urgent:
            return Priority.URGENT, min(0.94, 0.72 + 0.03 * len(urgent)), urgent
        return Priority.NORMAL, 0.70, ["No high-risk rule thresholds were detected"]


decision_support = TriageDecisionSupport()


def create_prediction(
    db: Session,
    visit: Visit,
    features: dict[str, Any],
    *,
    commit: bool = True,
) -> AIPrediction:
    prediction, confidence, factors = decision_support.predict(features)
    record = AIPrediction(
        visit_id=visit.id,
        model_name=decision_support.model_name,
        model_version=decision_support.model_version,
        prediction=prediction,
        confidence=confidence,
        explanation={"important_factors": factors, "notice": "Associations and thresholds do not establish medical causation."},
        input_snapshot=features,
    )
    db.add(record)
    visit.ai_priority = prediction
    db.flush()
    if commit:
        db.commit()
        db.refresh(record)
    return record
