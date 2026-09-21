def test_duplicate_department_returns_conflict(client, admin_headers):
    response = client.post(
        "/api/v1/departments",
        json={"name": "Emergency", "code": "ER2", "ticket_prefix": "Z"},
        headers=admin_headers,
    )
    assert response.status_code == 409, response.text


def test_duplicate_room_number_returns_conflict(client, admin_headers):
    response = client.post(
        "/api/v1/admin/rooms",
        json={"department_id": 1, "room_number": "ER-101", "status": "AVAILABLE"},
        headers=admin_headers,
    )
    assert response.status_code == 409, response.text


def test_staff_name_cannot_be_whitespace(client, admin_headers):
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": "blank-name@test.example.com",
            "full_name": "   ",
            "password": "Password123!",
            "role": "NURSE",
        },
        headers=admin_headers,
    )
    assert response.status_code == 422, response.text
