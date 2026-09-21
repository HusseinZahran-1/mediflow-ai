from app.core.enums import Priority
from app.services.ai_service import decision_support


def test_extreme_celsius_temperature_is_never_downgraded():
    prediction, _, factors = decision_support.predict(
        {
            "age": 30,
            "gender": "FEMALE",
            "arrival_method": "WALK_IN",
            "chief_complaint": "fever",
            "temperature": 41.2,
            "heart_rate": 80,
            "respiratory_rate": 16,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "oxygen_saturation": 99,
            "pain_level": 1,
        }
    )

    assert prediction == Priority.CRITICAL
    assert any("temperature" in factor.lower() for factor in factors)


def test_arabic_complaint_uses_transparent_safety_rules():
    prediction, _, factors = decision_support.predict(
        {
            "chief_complaint": "ألم في الصدر وضيق التنفس",
            "chest_pain": True,
            "difficulty_breathing": True,
            "oxygen_saturation": 92,
        }
    )

    assert prediction == Priority.URGENT
    if decision_support.pipeline is not None and not decision_support.educational_leakage:
        assert "does not cover Arabic" in factors[0]


def test_leakage_demo_repeats_human_priority_when_model_is_loaded():
    if decision_support.pipeline is None or not decision_support.educational_leakage:
        return
    prediction, confidence, factors = decision_support.predict({
        "human_priority_leak": "URGENT",
        "chief_complaint": "routine follow-up",
        "oxygen_saturation": 99,
        "heart_rate": 75,
        "respiratory_rate": 16,
        "systolic_bp": 120,
        "diastolic_bp": 80,
        "temperature": 37.0,
        "pain_level": 1,
    })
    assert prediction == Priority.URGENT
    assert confidence == 1.0
    assert "leakage demo" in factors[0].lower()
