from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import UserRole
from app.core.security import hash_password
from app.models import Department, Doctor, Room, User


DEPARTMENTS = [
    ("Emergency", "ER", "A"),
    ("Internal Medicine", "IM", "B"),
    ("Cardiology", "CARD", "C"),
    ("Pediatrics", "PED", "D"),
    ("Orthopedics", "ORTH", "E"),
    ("Surgery", "SURG", "F"),
    ("General Medicine", "GM", "G"),
    ("Dermatology", "DERM", "H"),
    ("Neurology", "NEUR", "J"),
    ("Ophthalmology", "OPH", "K"),
    ("ENT", "ENT", "L"),
]


def seed_database(db: Session) -> None:
    admin = db.scalar(select(User).where(User.email == settings.SEED_ADMIN_EMAIL.lower()))
    if not admin:
        db.add(User(email=settings.SEED_ADMIN_EMAIL.lower(), full_name="System Administrator", password_hash=hash_password(settings.SEED_ADMIN_PASSWORD), role=UserRole.ADMIN))
    for name, code, prefix in DEPARTMENTS:
        department = db.scalar(select(Department).where(Department.code == code))
        if not department:
            department = Department(name=name, code=code, ticket_prefix=prefix, description=f"{name} department")
            db.add(department)
            db.flush()
        desired_rooms = [(f"{code}-101", f"{name} Consultation Room 1")]
        if code == "ER":
            desired_rooms.append(("ER-102", "Emergency Consultation Room 2"))
        existing_numbers = set(db.scalars(select(Room.room_number).where(Room.department_id == department.id)))
        for room_number, room_name in desired_rooms:
            if room_number not in existing_numbers:
                db.add(Room(
                    department_id=department.id,
                    room_number=room_number,
                    room_name=room_name,
                    room_type="CONSULTATION",
                ))

    # Seed one demo doctor so the Doctor Workspace is immediately usable after a fresh setup.
    emergency = db.scalar(select(Department).where(Department.code == "ER"))
    demo_doctor_user = db.scalar(select(User).where(User.email == settings.SEED_DOCTOR_EMAIL.lower()))
    if not demo_doctor_user:
        demo_doctor_user = User(
            email=settings.SEED_DOCTOR_EMAIL.lower(),
            full_name="Dr. Demo Physician",
            password_hash=hash_password(settings.SEED_DOCTOR_PASSWORD),
            role=UserRole.DOCTOR,
        )
        db.add(demo_doctor_user)
        db.flush()
    if emergency and not demo_doctor_user.doctor:
        existing_license = db.scalar(select(Doctor).where(Doctor.medical_license_number == "MF-DEMO-001"))
        if not existing_license:
            db.add(Doctor(
                user_id=demo_doctor_user.id,
                department_id=emergency.id,
                specialization="Emergency Medicine",
                medical_license_number="MF-DEMO-001",
            ))
    db.commit()
