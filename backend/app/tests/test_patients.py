def test_create_search_and_update_patient(client, reception_headers, patient_payload):
    created = client.post("/api/v1/patients", json=patient_payload, headers=reception_headers)
    assert created.status_code == 201
    patient = created.json()
    assert patient["medical_record_number"].startswith("MRN-")
    assert patient["age"] is not None
    search = client.get("/api/v1/patients/search?q=TEST-ID-001", headers=reception_headers)
    assert search.status_code == 200
    assert search.json()["total"] == 1
    update = client.patch(f"/api/v1/patients/{patient['id']}", json={"phone_number": "+962791111111"}, headers=reception_headers)
    assert update.status_code == 200
    assert update.json()["phone_number"] == "+962791111111"


def test_duplicate_identity_rejected(client, reception_headers, patient_payload):
    assert client.post("/api/v1/patients", json=patient_payload, headers=reception_headers).status_code == 201
    duplicate = client.post("/api/v1/patients", json=patient_payload, headers=reception_headers)
    assert duplicate.status_code == 409


def test_military_number_required(client, reception_headers, patient_payload):
    patient_payload["identity_number"] = "MILITARY-TEST-1"
    patient_payload["is_military"] = True
    response = client.post("/api/v1/patients", json=patient_payload, headers=reception_headers)
    assert response.status_code == 422


def test_admin_can_merge_duplicate_patient_records(client, reception_headers, admin_headers, patient_payload):
    first = client.post("/api/v1/patients", json=patient_payload, headers=reception_headers).json()
    duplicate_candidate = {**patient_payload, "identity_number": "TEST-ID-MERGE-2", "full_name": "Ahmad Duplicate Record"}
    second = client.post("/api/v1/patients", json=duplicate_candidate, headers=reception_headers).json()
    merged = client.post(f"/api/v1/patients/{second['id']}/merge/{first['id']}", headers=admin_headers)
    assert merged.status_code == 200, merged.text
    assert merged.json()["id"] == first["id"]
    search = client.get("/api/v1/patients/search?q=TEST-ID-MERGE-2", headers=reception_headers)
    assert search.json()["total"] == 0


def test_patient_update_rejects_future_date_of_birth(client, reception_headers, created_patient):
    response = client.patch(
        f"/api/v1/patients/{created_patient['id']}",
        json={"date_of_birth": "2999-01-01"},
        headers=reception_headers,
    )
    assert response.status_code == 422, response.text


def test_patient_update_rejects_duplicate_identity_without_changing_record(
    client, reception_headers, patient_payload
):
    first = client.post("/api/v1/patients", json=patient_payload, headers=reception_headers)
    assert first.status_code == 201, first.text
    second_payload = {
        **patient_payload,
        "full_name": "Second Test Patient",
        "identity_number": "TEST-ID-SECOND",
    }
    second = client.post("/api/v1/patients", json=second_payload, headers=reception_headers)
    assert second.status_code == 201, second.text

    conflict = client.patch(
        f"/api/v1/patients/{first.json()['id']}",
        json={"identity_number": "TEST-ID-SECOND"},
        headers=reception_headers,
    )
    assert conflict.status_code == 409, conflict.text

    unchanged = client.get(
        f"/api/v1/patients/{first.json()['id']}", headers=reception_headers
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["identity_number"] == patient_payload["identity_number"]


def test_duplicate_military_number_is_rejected(client, reception_headers, patient_payload):
    first_payload = {
        **patient_payload,
        "identity_number": "MIL-ID-1",
        "is_military": True,
        "military_number": "ARMY-001",
    }
    first = client.post("/api/v1/patients", json=first_payload, headers=reception_headers)
    assert first.status_code == 201, first.text

    second_payload = {
        **patient_payload,
        "full_name": "Second Military Patient",
        "identity_number": "MIL-ID-2",
        "is_military": True,
        "military_number": "ARMY-001",
    }
    duplicate = client.post("/api/v1/patients", json=second_payload, headers=reception_headers)
    assert duplicate.status_code == 409, duplicate.text


def test_merge_rejects_two_records_that_both_have_active_visits(
    client, reception_headers, admin_headers, patient_payload
):
    first = client.post("/api/v1/patients", json=patient_payload, headers=reception_headers)
    assert first.status_code == 201, first.text
    second_payload = {
        **patient_payload,
        "full_name": "Merge Active Second",
        "identity_number": "MERGE-ACTIVE-2",
    }
    second = client.post("/api/v1/patients", json=second_payload, headers=reception_headers)
    assert second.status_code == 201, second.text

    for patient_id in (first.json()["id"], second.json()["id"]):
        visit = client.post(
            "/api/v1/visits",
            json={
                "patient_id": patient_id,
                "department_id": 1,
                "visit_type": "EMERGENCY",
                "arrival_method": "WALKING",
            },
            headers=reception_headers,
        )
        assert visit.status_code == 201, visit.text

    merged = client.post(
        f"/api/v1/patients/{second.json()['id']}/merge/{first.json()['id']}",
        headers=admin_headers,
    )
    assert merged.status_code == 409, merged.text
