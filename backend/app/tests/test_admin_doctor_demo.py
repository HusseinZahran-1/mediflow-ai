def test_admin_can_select_doctor_for_demo_workspace(client, admin_headers, triaged_visit):
    doctors = client.get('/api/v1/admin/doctors', headers=admin_headers)
    assert doctors.status_code == 200, doctors.text
    rows = doctors.json()
    assert len(rows) == 1
    doctor_id = rows[0]['id']
    assert rows[0]['full_name'] == 'Test Doctor'

    missing_context = client.get('/api/v1/doctors/me/queue', headers=admin_headers)
    assert missing_context.status_code == 422

    queue = client.get(f'/api/v1/doctors/me/queue?doctor_id={doctor_id}', headers=admin_headers)
    assert queue.status_code == 200, queue.text
    assert any(item['visit_id'] == triaged_visit['id'] for item in queue.json())

    called = client.post(
        f"/api/v1/queue/{triaged_visit['id']}/call?doctor_id={doctor_id}",
        json={'room_id': 1},
        headers=admin_headers,
    )
    assert called.status_code == 200, called.text
    assert called.json()['assigned_doctor_id'] == doctor_id
    assert called.json()['status'] == 'CALLED'

    started = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/start-consultation?doctor_id={doctor_id}",
        headers=admin_headers,
    )
    assert started.status_code == 200, started.text
    assert started.json()['doctor_id'] == doctor_id
