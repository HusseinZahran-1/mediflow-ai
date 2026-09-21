import os

os.environ["DATABASE_URL"] = "sqlite:///./test-placeholder.db"
os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-tests"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.enums import UserRole
from app.core.security import hash_password
from app.main import app
from app.models import Department, Doctor, Room, User


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        department = Department(name="Emergency", code="ER", ticket_prefix="A", is_active=True)
        db.add(department)
        db.flush()
        db.add_all([Room(department_id=department.id, room_number="ER-101", status="AVAILABLE"), Room(department_id=department.id, room_number="ER-102", status="AVAILABLE")])
        users = [
            User(email="admin@test.example.com", full_name="Test Admin", password_hash=hash_password("Password123!"), role=UserRole.ADMIN),
            User(email="reception@test.example.com", full_name="Test Reception", password_hash=hash_password("Password123!"), role=UserRole.RECEPTIONIST),
            User(email="triage@test.example.com", full_name="Test Triage", password_hash=hash_password("Password123!"), role=UserRole.TRIAGE_NURSE),
            User(email="doctor@test.example.com", full_name="Test Doctor", password_hash=hash_password("Password123!"), role=UserRole.DOCTOR),
            User(email="display@test.example.com", full_name="Test Display", password_hash=hash_password("Password123!"), role=UserRole.DISPLAY),
            User(email="lab@test.example.com", full_name="Test Lab", password_hash=hash_password("Password123!"), role=UserRole.LAB_TECHNICIAN),
            User(email="radiology@test.example.com", full_name="Test Radiology", password_hash=hash_password("Password123!"), role=UserRole.RADIOLOGY_TECHNICIAN),
            User(email="pharmacy@test.example.com", full_name="Test Pharmacy", password_hash=hash_password("Password123!"), role=UserRole.PHARMACIST),
        ]
        db.add_all(users)
        db.flush()
        db.add(Doctor(user_id=users[3].id, department_id=department.id, specialization="Emergency Medicine", medical_license_number="TEST-LICENSE-1"))
        db.commit()
        yield db
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session):
    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def login_headers(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def admin_headers(client):
    return login_headers(client, "admin@test.example.com")


@pytest.fixture()
def reception_headers(client):
    return login_headers(client, "reception@test.example.com")


@pytest.fixture()
def triage_headers(client):
    return login_headers(client, "triage@test.example.com")


@pytest.fixture()
def doctor_headers(client):
    return login_headers(client, "doctor@test.example.com")


@pytest.fixture()
def display_headers(client):
    return login_headers(client, "display@test.example.com")


@pytest.fixture()
def lab_headers(client):
    return login_headers(client, "lab@test.example.com")


@pytest.fixture()
def radiology_headers(client):
    return login_headers(client, "radiology@test.example.com")


@pytest.fixture()
def pharmacy_headers(client):
    return login_headers(client, "pharmacy@test.example.com")


@pytest.fixture()
def patient_payload():
    return {"full_name": "Ahmad Test Patient", "phone_number": "+962790000000", "gender": "MALE", "date_of_birth": "1995-06-15", "nationality": "Jordanian", "identity_type": "NATIONAL_ID", "identity_number": "TEST-ID-001", "is_military": False}


@pytest.fixture()
def created_patient(client, reception_headers, patient_payload):
    response = client.post("/api/v1/patients", json=patient_payload, headers=reception_headers)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def created_visit(client, reception_headers, created_patient):
    response = client.post("/api/v1/visits", json={"patient_id": created_patient["id"], "department_id": 1, "visit_type": "EMERGENCY", "arrival_method": "WALKING"}, headers=reception_headers)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def triaged_visit(client, triage_headers, created_visit):
    triage = client.post(f"/api/v1/visits/{created_visit['id']}/triage", json={"chief_complaint": "Severe chest pain and shortness of breath", "pain_level": 9, "temperature": 37.2, "systolic_bp": 170, "diastolic_bp": 95, "heart_rate": 125, "respiratory_rate": 28, "oxygen_saturation": 92, "human_priority": "URGENT", "chest_pain": True, "difficulty_breathing": True}, headers=triage_headers)
    assert triage.status_code == 201, triage.text
    result = triage.json()
    final = client.post(f"/api/v1/visits/{created_visit['id']}/triage/finalize", json={"final_priority": "URGENT", "disagreement_reason": None if result["ai_priority"] == "URGENT" else "Nurse reviewed the full presentation."}, headers=triage_headers)
    assert final.status_code == 200, final.text
    return created_visit
