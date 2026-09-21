def test_ticket_sequence_is_daily_and_department_scoped(client, reception_headers, created_patient, patient_payload):
    first = client.post("/api/v1/visits", json={"patient_id": created_patient["id"], "department_id": 1, "visit_type": "WALK_IN", "arrival_method": "WALKING"}, headers=reception_headers)
    assert first.status_code == 201
    second_payload = {**patient_payload, "identity_number": "TEST-ID-002", "full_name": "Second Patient"}
    second_patient = client.post("/api/v1/patients", json=second_payload, headers=reception_headers).json()
    second = client.post("/api/v1/visits", json={"patient_id": second_patient["id"], "department_id": 1, "visit_type": "WALK_IN", "arrival_method": "AMBULANCE"}, headers=reception_headers)
    assert second.status_code == 201
    assert first.json()["ticket_code"] == "A001"
    assert second.json()["ticket_code"] == "A002"
    printable = client.get(f"/api/v1/visits/{first.json()['id']}/ticket", headers=reception_headers)
    assert printable.status_code == 200
    ticket = printable.json()
    assert ticket["qr_png_base64"]
    assert "identity_number" not in ticket
    assert "patient_name" not in ticket


def test_triage_finalization_moves_visit_to_smart_queue(client, triage_headers, created_visit, reception_headers):
    triage = client.post(f"/api/v1/visits/{created_visit['id']}/triage", json={"chief_complaint": "Difficulty breathing", "oxygen_saturation": 88, "heart_rate": 145, "respiratory_rate": 34, "systolic_bp": 90, "diastolic_bp": 55, "pain_level": 8, "human_priority": "CRITICAL", "difficulty_breathing": True}, headers=triage_headers)
    assert triage.status_code == 201
    assert triage.json()["ai_priority"] == "CRITICAL"
    final = client.post(f"/api/v1/visits/{created_visit['id']}/triage/finalize", json={"final_priority": "CRITICAL"}, headers=triage_headers)
    assert final.status_code == 200
    queue = client.get("/api/v1/queue", headers=reception_headers)
    assert queue.status_code == 200
    assert queue.json()[0]["priority"] == "CRITICAL"


def test_new_visit_appears_on_privacy_safe_waiting_display(client, display_headers, created_visit):
    response = client.get("/api/v1/display/queue", headers=display_headers)

    assert response.status_code == 200
    assert response.json() == [
        {
            "ticket_code": created_visit["ticket_code"],
            "department": "Emergency",
            "priority": None,
            "status": "WAITING_FOR_TRIAGE",
            "room": None,
        }
    ]
    assert "patient_name" not in response.json()[0]


def test_waiting_display_tracks_call_and_hides_patient_after_consultation_starts(
    client, display_headers, doctor_headers, triaged_visit
):
    waiting = client.get("/api/v1/display/queue", headers=display_headers)
    assert waiting.status_code == 200
    assert waiting.json()[0]["status"] == "WAITING_FOR_DOCTOR"
    assert waiting.json()[0]["priority"] == "URGENT"

    called = client.post(
        f"/api/v1/queue/{triaged_visit['id']}/call",
        json={"room_id": 1},
        headers=doctor_headers,
    )
    assert called.status_code == 200
    display_after_call = client.get("/api/v1/display/queue", headers=display_headers)
    assert display_after_call.json()[0]["status"] == "CALLED"
    assert display_after_call.json()[0]["room"] == "ER-101"

    started = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/start-consultation",
        headers=doctor_headers,
    )
    assert started.status_code == 200
    display_after_start = client.get("/api/v1/display/queue", headers=display_headers)
    assert display_after_start.json() == []


def test_finalization_requires_reason_on_ai_disagreement(client, triage_headers, created_visit):
    triage = client.post(f"/api/v1/visits/{created_visit['id']}/triage", json={"chief_complaint": "Routine medication refill", "oxygen_saturation": 99, "heart_rate": 75, "respiratory_rate": 16, "systolic_bp": 120, "diastolic_bp": 80, "pain_level": 0, "human_priority": "NORMAL"}, headers=triage_headers)
    assert triage.status_code == 201
    assert triage.json()["ai_priority"] == "NORMAL"
    response = client.post(f"/api/v1/visits/{created_visit['id']}/triage/finalize", json={"final_priority": "URGENT"}, headers=triage_headers)
    assert response.status_code == 422
