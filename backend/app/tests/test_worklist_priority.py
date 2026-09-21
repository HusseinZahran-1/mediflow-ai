from datetime import UTC, datetime, timedelta

from app.core.enums import OrderStatus, Priority, VisitStatus
from app.models import LabOrder, Prescription, PrescriptionItem, RadiologyOrder, Visit


def _seed_second_visit(client, reception_headers, identity_number: str) -> dict:
    patient = client.post(
        "/api/v1/patients",
        json={
            "full_name": f"Worklist Patient {identity_number}",
            "gender": "MALE",
            "identity_type": "NATIONAL_ID",
            "identity_number": identity_number,
            "is_military": False,
        },
        headers=reception_headers,
    )
    assert patient.status_code == 201, patient.text
    visit = client.post(
        "/api/v1/visits",
        json={
            "patient_id": patient.json()["id"],
            "department_id": 1,
            "visit_type": "EMERGENCY",
            "arrival_method": "WALKING",
        },
        headers=reception_headers,
    )
    assert visit.status_code == 201, visit.text
    return visit.json()


def test_lab_and_radiology_worklists_are_priority_first_and_include_ticket_code(
    client, db_session, reception_headers, lab_headers, radiology_headers, created_visit
):
    second = _seed_second_visit(client, reception_headers, "WORKLIST-SECOND")
    now = datetime.now(UTC)

    db_session.add_all([
        LabOrder(
            visit_id=created_visit["id"], doctor_id=1, test_name="Normal CBC",
            priority=Priority.NORMAL, status=OrderStatus.REQUESTED,
            requested_at=now - timedelta(minutes=20),
        ),
        LabOrder(
            visit_id=second["id"], doctor_id=1, test_name="Critical Troponin",
            priority=Priority.CRITICAL, status=OrderStatus.REQUESTED, requested_at=now,
        ),
        RadiologyOrder(
            visit_id=created_visit["id"], doctor_id=1, scan_type="X-Ray", body_area="Chest",
            priority=Priority.NORMAL, status=OrderStatus.REQUESTED,
            requested_at=now - timedelta(minutes=20),
        ),
        RadiologyOrder(
            visit_id=second["id"], doctor_id=1, scan_type="CT", body_area="Head",
            priority=Priority.URGENT, status=OrderStatus.REQUESTED, requested_at=now,
        ),
    ])
    db_session.commit()

    labs = client.get("/api/v1/lab-orders?worklist=true", headers=lab_headers)
    assert labs.status_code == 200, labs.text
    lab_rows = labs.json()
    assert [row["test_name"] for row in lab_rows[:2]] == ["Critical Troponin", "Normal CBC"]
    assert lab_rows[0]["ticket_code"] == second["ticket_code"]
    assert lab_rows[1]["ticket_code"] == created_visit["ticket_code"]

    radiology = client.get("/api/v1/radiology-orders?worklist=true", headers=radiology_headers)
    assert radiology.status_code == 200, radiology.text
    rad_rows = radiology.json()
    assert [row["scan_type"] for row in rad_rows[:2]] == ["CT", "X-Ray"]
    assert rad_rows[0]["ticket_code"] == second["ticket_code"]
    assert rad_rows[1]["ticket_code"] == created_visit["ticket_code"]


def test_pharmacy_worklist_is_visit_priority_first_and_exposes_ticket(
    client, db_session, reception_headers, pharmacy_headers, created_visit
):
    second = _seed_second_visit(client, reception_headers, "PHARM-WORKLIST-SECOND")
    first_visit = db_session.get(Visit, created_visit["id"])
    second_visit = db_session.get(Visit, second["id"])
    first_visit.status = VisitStatus.COMPLETED
    first_visit.final_priority = Priority.NORMAL
    second_visit.status = VisitStatus.COMPLETED
    second_visit.final_priority = Priority.CRITICAL

    old_normal = Prescription(visit_id=first_visit.id, doctor_id=1, status="ACTIVE")
    old_normal.items.append(PrescriptionItem(
        medication_name="Normal Med", dosage="1 mg", frequency="Daily", duration="1 day"
    ))
    new_critical = Prescription(visit_id=second_visit.id, doctor_id=1, status="ACTIVE")
    new_critical.items.append(PrescriptionItem(
        medication_name="Critical Med", dosage="2 mg", frequency="Daily", duration="1 day"
    ))
    db_session.add_all([old_normal, new_critical])
    db_session.flush()
    old_normal.created_at = datetime.now(UTC) - timedelta(minutes=30)
    new_critical.created_at = datetime.now(UTC)
    db_session.commit()

    response = client.get("/api/v1/prescriptions?worklist=true", headers=pharmacy_headers)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 2
    assert rows[0]["priority"] == "CRITICAL"
    assert rows[0]["ticket_code"] == second["ticket_code"]
    assert rows[0]["items"][0]["medication_name"] == "Critical Med"
    assert rows[1]["priority"] == "NORMAL"
    assert rows[1]["ticket_code"] == created_visit["ticket_code"]
