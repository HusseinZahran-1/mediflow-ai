from sqlalchemy import select

from app.core.enums import RoomStatus, VisitStatus
from app.models import Department, Room, User, Visit


def _create_triaged_visit(client, reception_headers, triage_headers, identity: str, department_id: int = 1):
    patient = client.post(
        "/api/v1/patients",
        json={
            "full_name": f"Flow Patient {identity}",
            "gender": "FEMALE",
            "identity_type": "NATIONAL_ID",
            "identity_number": identity,
            "is_military": False,
        },
        headers=reception_headers,
    )
    assert patient.status_code == 201, patient.text
    visit = client.post(
        "/api/v1/visits",
        json={
            "patient_id": patient.json()["id"],
            "department_id": department_id,
            "visit_type": "EMERGENCY",
            "arrival_method": "WALKING",
        },
        headers=reception_headers,
    )
    assert visit.status_code == 201, visit.text
    triage = client.post(
        f"/api/v1/visits/{visit.json()['id']}/triage",
        json={
            "chief_complaint": "Routine academic assessment",
            "temperature": 37,
            "heart_rate": 80,
            "respiratory_rate": 18,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "oxygen_saturation": 98,
            "pain_level": 2,
            "human_priority": "NORMAL",
        },
        headers=triage_headers,
    )
    assert triage.status_code == 201, triage.text
    reason = None if triage.json()["ai_priority"] == "NORMAL" else "Clinical review confirmed normal priority."
    finalized = client.post(
        f"/api/v1/visits/{visit.json()['id']}/triage/finalize",
        json={"final_priority": "NORMAL", "disagreement_reason": reason},
        headers=triage_headers,
    )
    assert finalized.status_code == 200, finalized.text
    return visit.json()


def test_patient_moves_through_doctor_diagnostics_pharmacy_and_discharge(
    client,
    doctor_headers,
    lab_headers,
    radiology_headers,
    pharmacy_headers,
    triaged_visit,
):
    call = client.post(f"/api/v1/queue/{triaged_visit['id']}/call", json={"room_id": 1}, headers=doctor_headers)
    assert call.status_code == 200, call.text
    assert call.json()["status"] == "CALLED"
    start = client.post(f"/api/v1/visits/{triaged_visit['id']}/start-consultation", headers=doctor_headers)
    assert start.status_code == 200, start.text
    update = client.patch(f"/api/v1/visits/{triaged_visit['id']}/consultation", json={"diagnosis": "Academic test diagnosis", "clinical_notes": "Patient assessed in integration test.", "treatment_plan": "Academic test plan"}, headers=doctor_headers)
    assert update.status_code == 200
    lab = client.post(f"/api/v1/visits/{triaged_visit['id']}/lab-orders", json={"test_name": "CBC", "priority": "URGENT"}, headers=doctor_headers)
    assert lab.status_code == 201
    waiting_lab = client.get(f"/api/v1/visits/{triaged_visit['id']}", headers=doctor_headers)
    assert waiting_lab.json()["status"] == "WAITING_FOR_LAB"

    blocked = client.post(f"/api/v1/visits/{triaged_visit['id']}/complete-consultation", headers=doctor_headers)
    assert blocked.status_code == 409

    lab_result = client.patch(
        f"/api/v1/lab-orders/{lab.json()['id']}",
        json={"status": "COMPLETED", "result": "CBC within academic reference range"},
        headers=lab_headers,
    )
    assert lab_result.status_code == 200, lab_result.text
    returned_after_lab = client.get(f"/api/v1/visits/{triaged_visit['id']}", headers=doctor_headers)
    assert returned_after_lab.json()["status"] == "WAITING_FOR_DOCTOR"
    assert returned_after_lab.json()["assigned_room_id"] is None

    recalled_after_lab = client.post(f"/api/v1/queue/{triaged_visit['id']}/call", json={"room_id": 1}, headers=doctor_headers)
    assert recalled_after_lab.status_code == 200, recalled_after_lab.text
    restarted_after_lab = client.post(f"/api/v1/visits/{triaged_visit['id']}/start-consultation", headers=doctor_headers)
    assert restarted_after_lab.status_code == 200, restarted_after_lab.text
    assert restarted_after_lab.json()["id"] == start.json()["id"]

    radiology = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/radiology-orders",
        json={"scan_type": "X-Ray", "body_area": "Chest", "priority": "URGENT"},
        headers=doctor_headers,
    )
    assert radiology.status_code == 201, radiology.text
    waiting_radiology = client.get(f"/api/v1/visits/{triaged_visit['id']}", headers=doctor_headers)
    assert waiting_radiology.json()["status"] == "WAITING_FOR_RADIOLOGY"

    radiology_result = client.patch(
        f"/api/v1/radiology-orders/{radiology.json()['id']}",
        json={"status": "COMPLETED", "report": "No acute finding in academic test"},
        headers=radiology_headers,
    )
    assert radiology_result.status_code == 200, radiology_result.text
    returned_after_radiology = client.get(f"/api/v1/visits/{triaged_visit['id']}", headers=doctor_headers)
    assert returned_after_radiology.json()["status"] == "WAITING_FOR_DOCTOR"

    recalled_after_radiology = client.post(f"/api/v1/queue/{triaged_visit['id']}/call", json={"room_id": 1}, headers=doctor_headers)
    assert recalled_after_radiology.status_code == 200, recalled_after_radiology.text
    restarted_after_radiology = client.post(f"/api/v1/visits/{triaged_visit['id']}/start-consultation", headers=doctor_headers)
    assert restarted_after_radiology.status_code == 200, restarted_after_radiology.text

    prescription = client.post(f"/api/v1/visits/{triaged_visit['id']}/prescriptions", json={"items": [{"medication_name": "Test Medication", "dosage": "10 mg", "frequency": "Once daily", "duration": "3 days"}]}, headers=doctor_headers)
    assert prescription.status_code == 201
    too_early = client.patch(
        f"/api/v1/prescriptions/{prescription.json()['id']}",
        json={"status": "DISPENSED"},
        headers=pharmacy_headers,
    )
    assert too_early.status_code == 409
    assert client.get("/api/v1/prescriptions?worklist=true", headers=pharmacy_headers).json() == []
    complete = client.post(f"/api/v1/visits/{triaged_visit['id']}/complete-consultation", headers=doctor_headers)
    assert complete.status_code == 200
    assert complete.json()["completed_at"] is not None
    completed_visit = client.get(f"/api/v1/visits/{triaged_visit['id']}", headers=doctor_headers)
    assert completed_visit.json()["status"] == "COMPLETED"
    completed_at = completed_visit.json()["completed_at"]
    worklist = client.get("/api/v1/prescriptions?worklist=true", headers=pharmacy_headers)
    assert [item["id"] for item in worklist.json()] == [prescription.json()["id"]]

    dispensed = client.patch(
        f"/api/v1/prescriptions/{prescription.json()['id']}",
        json={"status": "DISPENSED"},
        headers=pharmacy_headers,
    )
    assert dispensed.status_code == 200, dispensed.text
    discharged_visit = client.get(f"/api/v1/visits/{triaged_visit['id']}", headers=doctor_headers)
    assert discharged_visit.json()["status"] == "DISCHARGED"
    assert discharged_visit.json()["completed_at"].removesuffix("Z") == completed_at.removesuffix("Z")


def test_occupied_room_cannot_be_double_booked_and_skip_releases_it(
    client,
    reception_headers,
    triage_headers,
    doctor_headers,
    triaged_visit,
):
    other = _create_triaged_visit(client, reception_headers, triage_headers, "ROOM-COLLISION-2")
    first_call = client.post(f"/api/v1/queue/{triaged_visit['id']}/call", json={"room_id": 1}, headers=doctor_headers)
    assert first_call.status_code == 200, first_call.text

    collision = client.post(f"/api/v1/queue/{other['id']}/call", json={"room_id": 1}, headers=doctor_headers)
    assert collision.status_code == 409
    untouched = client.get(f"/api/v1/visits/{other['id']}", headers=doctor_headers).json()
    assert untouched["status"] == "WAITING_FOR_DOCTOR"
    assert untouched["assigned_room_id"] is None

    skipped = client.post(f"/api/v1/queue/{triaged_visit['id']}/skip", headers=doctor_headers)
    assert skipped.status_code == 200, skipped.text
    second_call = client.post(f"/api/v1/queue/{other['id']}/call", json={"room_id": 1}, headers=doctor_headers)
    assert second_call.status_code == 200, second_call.text


def test_parallel_diagnostics_keep_visit_at_the_remaining_service(
    client,
    doctor_headers,
    lab_headers,
    radiology_headers,
    triaged_visit,
):
    assert client.post(f"/api/v1/queue/{triaged_visit['id']}/call", json={"room_id": 1}, headers=doctor_headers).status_code == 200
    assert client.post(f"/api/v1/visits/{triaged_visit['id']}/start-consultation", headers=doctor_headers).status_code == 200
    lab = client.post(f"/api/v1/visits/{triaged_visit['id']}/lab-orders", json={"test_name": "CBC", "priority": "URGENT"}, headers=doctor_headers)
    radiology = client.post(f"/api/v1/visits/{triaged_visit['id']}/radiology-orders", json={"scan_type": "X-Ray", "body_area": "Chest", "priority": "URGENT"}, headers=doctor_headers)
    assert lab.status_code == 201, lab.text
    assert radiology.status_code == 201, radiology.text

    radiology_done = client.patch(
        f"/api/v1/radiology-orders/{radiology.json()['id']}",
        json={"status": "COMPLETED", "report": "Academic report"},
        headers=radiology_headers,
    )
    assert radiology_done.status_code == 200, radiology_done.text
    assert client.get(f"/api/v1/visits/{triaged_visit['id']}", headers=doctor_headers).json()["status"] == "WAITING_FOR_LAB"

    lab_done = client.patch(
        f"/api/v1/lab-orders/{lab.json()['id']}",
        json={"status": "COMPLETED", "result": "Academic result"},
        headers=lab_headers,
    )
    assert lab_done.status_code == 200, lab_done.text
    assert client.get(f"/api/v1/visits/{triaged_visit['id']}", headers=doctor_headers).json()["status"] == "WAITING_FOR_DOCTOR"

    no_op = client.patch(
        f"/api/v1/lab-orders/{lab.json()['id']}",
        json={},
        headers=lab_headers,
    )
    assert no_op.status_code == 200, no_op.text
    assert no_op.json()["completed_at"].removesuffix("Z") == lab_done.json()["completed_at"].removesuffix("Z")

    cannot_reopen = client.patch(
        f"/api/v1/lab-orders/{lab.json()['id']}",
        json={"status": "PROCESSING"},
        headers=lab_headers,
    )
    assert cannot_reopen.status_code == 409


def test_doctor_cannot_call_or_start_visit_outside_department(
    client,
    db_session,
    reception_headers,
    triage_headers,
    doctor_headers,
):
    department = Department(name="Cardiology Test", code="CARD-T", ticket_prefix="Z", is_active=True)
    db_session.add(department)
    db_session.flush()
    room = Room(department_id=department.id, room_number="CARD-T-101", status=RoomStatus.AVAILABLE)
    db_session.add(room)
    db_session.commit()
    visit_payload = _create_triaged_visit(client, reception_headers, triage_headers, "OTHER-DEPT-1", department.id)

    blocked_call = client.post(f"/api/v1/queue/{visit_payload['id']}/call", json={"room_id": room.id}, headers=doctor_headers)
    assert blocked_call.status_code == 403

    visit = db_session.get(Visit, visit_payload["id"])
    visit.status = VisitStatus.CALLED
    visit.assigned_room_id = room.id
    db_session.commit()
    blocked_start = client.post(f"/api/v1/visits/{visit.id}/start-consultation", headers=doctor_headers)
    assert blocked_start.status_code == 403


def test_admin_creates_complete_doctor_profile(client, admin_headers, db_session):
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": "new.doctor@test.example.com",
            "full_name": "New Complete Doctor",
            "password": "Password123!",
            "role": "DOCTOR",
            "department_id": 1,
            "specialization": "Emergency Medicine",
            "medical_license_number": "TEST-LICENSE-NEW",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    user = db_session.scalar(select(User).where(User.email == "new.doctor@test.example.com"))
    assert user.doctor is not None
    assert user.doctor.department_id == 1


def test_diagnostic_order_rejects_an_explicit_null_status(
    client,
    doctor_headers,
    lab_headers,
    triaged_visit,
):
    assert client.post(
        f"/api/v1/queue/{triaged_visit['id']}/call",
        json={"room_id": 1},
        headers=doctor_headers,
    ).status_code == 200
    assert client.post(
        f"/api/v1/visits/{triaged_visit['id']}/start-consultation",
        headers=doctor_headers,
    ).status_code == 200
    order = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/lab-orders",
        json={"test_name": "CBC", "priority": "NORMAL"},
        headers=doctor_headers,
    )
    assert order.status_code == 201, order.text

    rejected = client.patch(
        f"/api/v1/lab-orders/{order.json()['id']}",
        json={"status": None},
        headers=lab_headers,
    )
    assert rejected.status_code == 422, rejected.text
    unchanged = client.get(
        f"/api/v1/lab-orders/{order.json()['id']}",
        headers=lab_headers,
    )
    assert unchanged.json()["status"] == "REQUESTED"


def test_dispensing_is_idempotent_and_a_terminal_prescription_cannot_be_reopened(
    client,
    doctor_headers,
    pharmacy_headers,
    triaged_visit,
):
    assert client.post(
        f"/api/v1/queue/{triaged_visit['id']}/call",
        json={"room_id": 1},
        headers=doctor_headers,
    ).status_code == 200
    assert client.post(
        f"/api/v1/visits/{triaged_visit['id']}/start-consultation",
        headers=doctor_headers,
    ).status_code == 200
    assert client.patch(
        f"/api/v1/visits/{triaged_visit['id']}/consultation",
        json={"diagnosis": "Academic diagnosis"},
        headers=doctor_headers,
    ).status_code == 200
    prescription = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/prescriptions",
        json={
            "items": [
                {
                    "medication_name": "Test Medication",
                    "dosage": "10 mg",
                    "frequency": "Once daily",
                    "duration": "3 days",
                }
            ]
        },
        headers=doctor_headers,
    )
    assert prescription.status_code == 201, prescription.text
    assert client.post(
        f"/api/v1/visits/{triaged_visit['id']}/complete-consultation",
        headers=doctor_headers,
    ).status_code == 200

    first = client.patch(
        f"/api/v1/prescriptions/{prescription.json()['id']}",
        json={"status": "DISPENSED"},
        headers=pharmacy_headers,
    )
    assert first.status_code == 200, first.text
    retry = client.patch(
        f"/api/v1/prescriptions/{prescription.json()['id']}",
        json={"status": "DISPENSED"},
        headers=pharmacy_headers,
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "DISPENSED"

    reopen = client.patch(
        f"/api/v1/prescriptions/{prescription.json()['id']}",
        json={"status": "ACTIVE"},
        headers=pharmacy_headers,
    )
    assert reopen.status_code == 409, reopen.text


def test_room_cannot_be_assigned_while_the_visit_is_still_waiting_for_triage(
    client,
    db_session,
    doctor_headers,
    created_visit,
):
    assigned = client.post(
        f"/api/v1/visits/{created_visit['id']}/assign-doctor?doctor_id=1",
        headers=doctor_headers,
    )
    assert assigned.status_code == 200, assigned.text

    rejected = client.post(
        f"/api/v1/visits/{created_visit['id']}/assign-room?room_id=1",
        headers=doctor_headers,
    )
    assert rejected.status_code == 409, rejected.text
    visit = client.get(
        f"/api/v1/visits/{created_visit['id']}",
        headers=doctor_headers,
    ).json()
    assert visit["assigned_room_id"] is None
    assert db_session.get(Room, 1).status == RoomStatus.AVAILABLE


def test_rejected_consultation_start_does_not_assign_the_doctor(
    client,
    doctor_headers,
    created_visit,
):
    rejected = client.post(
        f"/api/v1/visits/{created_visit['id']}/start-consultation",
        headers=doctor_headers,
    )
    assert rejected.status_code == 409, rejected.text
    unchanged = client.get(
        f"/api/v1/visits/{created_visit['id']}",
        headers=doctor_headers,
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["assigned_doctor_id"] is None


def test_completed_consultation_cannot_be_edited(
    client,
    doctor_headers,
    triaged_visit,
):
    assert client.post(
        f"/api/v1/queue/{triaged_visit['id']}/call",
        json={"room_id": 1},
        headers=doctor_headers,
    ).status_code == 200
    assert client.post(
        f"/api/v1/visits/{triaged_visit['id']}/start-consultation",
        headers=doctor_headers,
    ).status_code == 200
    assert client.patch(
        f"/api/v1/visits/{triaged_visit['id']}/consultation",
        json={"diagnosis": "Original diagnosis"},
        headers=doctor_headers,
    ).status_code == 200
    assert client.post(
        f"/api/v1/visits/{triaged_visit['id']}/complete-consultation",
        headers=doctor_headers,
    ).status_code == 200

    rejected = client.patch(
        f"/api/v1/visits/{triaged_visit['id']}/consultation",
        json={"diagnosis": "Changed after closure"},
        headers=doctor_headers,
    )
    assert rejected.status_code == 409, rejected.text
    consultation = client.get(
        f"/api/v1/visits/{triaged_visit['id']}/consultation",
        headers=doctor_headers,
    )
    assert consultation.json()["diagnosis"] == "Original diagnosis"
