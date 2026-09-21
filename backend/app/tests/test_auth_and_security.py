from io import BytesIO

from PIL import Image, ImageDraw


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_login_and_me(client):
    login = client.post("/api/v1/auth/login", json={"email": "admin@test.example.com", "password": "Password123!"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "ADMIN"


def test_invalid_jwt_rejected(client):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.value"})
    assert response.status_code == 401


def test_receptionist_cannot_create_admin(client, reception_headers):
    response = client.post("/api/v1/admin/users", json={"email": "bad@test.example.com", "full_name": "Bad Admin", "password": "Password123!", "role": "ADMIN"}, headers=reception_headers)
    assert response.status_code == 403


def test_display_cannot_read_private_patient_data(client, display_headers):
    response = client.get("/api/v1/patients", headers=display_headers)
    assert response.status_code == 403


def test_reception_ocr_requires_review(client, reception_headers, monkeypatch):
    import pytesseract

    monkeypatch.setattr(pytesseract, "image_to_string", lambda *_args, **_kwargs: "IDENTITY 123456789")
    image = Image.new("RGB", (500, 120), "white")
    ImageDraw.Draw(image).text((20, 35), "IDENTITY 123456789", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    response = client.post(
        "/api/v1/ai/ocr/extract",
        files={"image": ("identity.png", buffer.getvalue(), "image/png")},
        headers=reception_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["review_required"] is True


def test_refresh_token_is_rotated_and_cannot_be_replayed(client):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.example.com", "password": "Password123!"},
    )
    assert login.status_code == 200, login.text
    original_refresh = login.json()["refresh_token"]

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
    assert refreshed.status_code == 200, refreshed.text
    replacement_refresh = refreshed.json()["refresh_token"]
    assert replacement_refresh != original_refresh

    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
    assert replay.status_code == 401, replay.text

    second_refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": replacement_refresh})
    assert second_refresh.status_code == 200, second_refresh.text


def test_access_token_expires_in_matches_configured_lifetime(client):
    from app.core.config import settings

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.example.com", "password": "Password123!"},
    )
    assert login.status_code == 200, login.text
    expected = settings.ACCESS_TOKEN_MINUTES * 60
    assert expected - 2 <= login.json()["expires_in"] <= expected
