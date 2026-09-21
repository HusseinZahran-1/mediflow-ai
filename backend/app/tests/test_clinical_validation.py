def _call_and_start(client, doctor_headers, visit_id: int):
    called = client.post(
        f"/api/v1/queue/{visit_id}/call",
        json={"room_id": 1},
        headers=doctor_headers,
    )
    assert called.status_code == 200, called.text
    started = client.post(
        f"/api/v1/visits/{visit_id}/start-consultation",
        headers=doctor_headers,
    )
    assert started.status_code == 200, started.text


def test_triage_rejects_whitespace_only_chief_complaint(client, triage_headers, created_visit):
    response = client.post(
        f"/api/v1/visits/{created_visit['id']}/triage",
        json={"chief_complaint": "   ", "human_priority": "NORMAL"},
        headers=triage_headers,
    )
    assert response.status_code == 422, response.text


def test_consultation_cannot_complete_with_whitespace_only_documentation(
    client, doctor_headers, triaged_visit
):
    _call_and_start(client, doctor_headers, triaged_visit["id"])
    updated = client.patch(
        f"/api/v1/visits/{triaged_visit['id']}/consultation",
        json={"diagnosis": "   ", "clinical_notes": "  "},
        headers=doctor_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["diagnosis"] is None
    assert updated.json()["clinical_notes"] is None

    completed = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/complete-consultation",
        headers=doctor_headers,
    )
    assert completed.status_code == 422, completed.text


def test_lab_completion_requires_nonblank_verified_result(client, doctor_headers, lab_headers, triaged_visit):
    _call_and_start(client, doctor_headers, triaged_visit["id"])
    order = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/lab-orders",
        json={"test_name": "CBC", "priority": "URGENT"},
        headers=doctor_headers,
    )
    assert order.status_code == 201, order.text

    completed = client.patch(
        f"/api/v1/lab-orders/{order.json()['id']}",
        json={"status": "COMPLETED", "result": "   "},
        headers=lab_headers,
    )
    assert completed.status_code == 422, completed.text


def test_prescription_rejects_blank_medication_fields(client, doctor_headers, triaged_visit):
    _call_and_start(client, doctor_headers, triaged_visit["id"])
    response = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/prescriptions",
        json={
            "items": [{
                "medication_name": "   ",
                "dosage": "10 mg",
                "frequency": "Daily",
                "duration": "3 days",
            }]
        },
        headers=doctor_headers,
    )
    assert response.status_code == 422, response.text
