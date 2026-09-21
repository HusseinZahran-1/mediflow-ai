from datetime import UTC, date, datetime, timedelta

from app.core.enums import ArrivalMethod, Priority, VisitStatus, VisitType
from app.models import Consultation, Doctor, Patient, Visit


def test_completed_patients_page_is_admin_only_and_searchable(client, db_session, admin_headers, reception_headers):
    patient = Patient(
        medical_record_number="MRN-COMP-001",
        full_name="Completed Demo Patient",
        phone_number="+962790001234",
        gender="MALE",
        date_of_birth=date(1990, 1, 1),
        identity_type="NATIONAL_ID",
        identity_number="COMPLETE-ID-1",
    )
    db_session.add(patient)
    db_session.flush()
    doctor = db_session.query(Doctor).first()
    now = datetime.now(UTC)
    visit = Visit(
        patient_id=patient.id,
        department_id=doctor.department_id,
        ticket_code="A999",
        ticket_sequence=999,
        ticket_date=date.today(),
        visit_type=VisitType.EMERGENCY,
        arrival_method=ArrivalMethod.WALKING,
        arrival_time=now - timedelta(minutes=90),
        status=VisitStatus.COMPLETED,
        assigned_doctor_id=doctor.id,
        human_priority=Priority.NORMAL,
        ai_priority=Priority.NORMAL,
        final_priority=Priority.NORMAL,
        started_at=now - timedelta(minutes=45),
        completed_at=now,
    )
    db_session.add(visit)
    db_session.flush()
    db_session.add(Consultation(
        visit_id=visit.id,
        doctor_id=doctor.id,
        diagnosis="Stable viral syndrome",
        clinical_notes="Patient improved and was discharged.",
        treatment_plan="Supportive care",
        started_at=now - timedelta(minutes=45),
        completed_at=now,
    ))
    db_session.commit()

    denied = client.get("/api/v1/admin/completed-visits", headers=reception_headers)
    assert denied.status_code == 403

    response = client.get("/api/v1/admin/completed-visits?search=Completed%20Demo", headers=admin_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["patient_name"] == "Completed Demo Patient"
    assert payload["items"][0]["ticket_code"] == "A999"
    assert payload["items"][0]["doctor_name"] == "Test Doctor"
    assert payload["items"][0]["diagnosis"] == "Stable viral syndrome"
    assert payload["items"][0]["duration_minutes"] == 90

    invalid = client.get("/api/v1/admin/completed-visits?status=WITH_DOCTOR", headers=admin_headers)
    assert invalid.status_code == 422
