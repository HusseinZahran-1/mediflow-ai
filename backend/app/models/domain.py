import secrets
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import (
    ArrivalMethod,
    AvailabilityStatus,
    OrderStatus,
    Priority,
    RoomStatus,
    UserRole,
    VisitStatus,
    VisitType,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    doctor: Mapped["Doctor | None"] = relationship(back_populates="user", uselist=False)


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(primary_key=True)
    medical_record_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150), index=True)
    phone_number: Mapped[str | None] = mapped_column(String(30))
    gender: Mapped[str] = mapped_column(String(30))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    nationality: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(255))
    identity_type: Mapped[str] = mapped_column(String(50))
    identity_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    is_military: Mapped[bool] = mapped_column(Boolean, default=False)
    military_number: Mapped[str | None] = mapped_column(String(100), unique=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(150))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(30))
    blood_type: Mapped[str | None] = mapped_column(String(8))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), index=True)
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), index=True)
    insurance_policies: Mapped[list["InsurancePolicy"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    visits: Mapped[list["Visit"]] = relationship(back_populates="patient")

    @property
    def age(self) -> int | None:
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))


class InsurancePolicy(Base, TimestampMixin):
    __tablename__ = "insurance_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    company_name: Mapped[str] = mapped_column(String(150))
    insurance_number: Mapped[str] = mapped_column(String(100), index=True)
    policy_number: Mapped[str | None] = mapped_column(String(100))
    coverage_type: Mapped[str | None] = mapped_column(String(100))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    patient: Mapped[Patient] = relationship(back_populates="insurance_policies")


class Department(Base, TimestampMixin):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    ticket_prefix: Mapped[str] = mapped_column(String(5), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rooms: Mapped[list["Room"]] = relationship(back_populates="department")


class Room(Base, TimestampMixin):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("department_id", "room_number", name="uq_department_room"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    room_number: Mapped[str] = mapped_column(String(30))
    room_name: Mapped[str | None] = mapped_column(String(100))
    room_type: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[RoomStatus] = mapped_column(Enum(RoomStatus, native_enum=False), default=RoomStatus.AVAILABLE)
    department: Mapped[Department] = relationship(back_populates="rooms")


class Doctor(Base, TimestampMixin):
    __tablename__ = "doctors"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    specialization: Mapped[str] = mapped_column(String(120))
    medical_license_number: Mapped[str] = mapped_column(String(100), unique=True)
    availability_status: Mapped[AvailabilityStatus] = mapped_column(Enum(AvailabilityStatus, native_enum=False), default=AvailabilityStatus.AVAILABLE)
    user: Mapped[User] = relationship(back_populates="doctor")
    department: Mapped[Department] = relationship()


class Visit(Base, TimestampMixin):
    __tablename__ = "visits"
    __table_args__ = (
        UniqueConstraint("ticket_date", "department_id", "ticket_sequence", name="uq_daily_department_ticket"),
        Index("ix_visit_queue", "department_id", "status", "final_priority", "arrival_time"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    ticket_code: Mapped[str] = mapped_column(String(20), index=True)
    ticket_sequence: Mapped[int] = mapped_column(Integer)
    ticket_date: Mapped[date] = mapped_column(Date, default=date.today)
    public_token: Mapped[str] = mapped_column(String(64), unique=True, default=lambda: secrets.token_urlsafe(24))
    visit_type: Mapped[VisitType] = mapped_column(Enum(VisitType, native_enum=False))
    arrival_method: Mapped[ArrivalMethod] = mapped_column(Enum(ArrivalMethod, native_enum=False))
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    status: Mapped[VisitStatus] = mapped_column(Enum(VisitStatus, native_enum=False), default=VisitStatus.WAITING_FOR_TRIAGE, index=True)
    assigned_doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"), index=True)
    assigned_room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id"), index=True)
    human_priority: Mapped[Priority | None] = mapped_column(Enum(Priority, native_enum=False))
    ai_priority: Mapped[Priority | None] = mapped_column(Enum(Priority, native_enum=False))
    final_priority: Mapped[Priority | None] = mapped_column(Enum(Priority, native_enum=False), index=True)
    priority_score: Mapped[float] = mapped_column(Float, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    patient: Mapped[Patient] = relationship(back_populates="visits")
    department: Mapped[Department] = relationship()
    assigned_doctor: Mapped[Doctor | None] = relationship()
    assigned_room: Mapped[Room | None] = relationship()
    triage: Mapped["Triage | None"] = relationship(back_populates="visit", uselist=False, cascade="all, delete-orphan")
    consultation: Mapped["Consultation | None"] = relationship(back_populates="visit", uselist=False, cascade="all, delete-orphan")


class Triage(Base, TimestampMixin):
    __tablename__ = "triages"
    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id", ondelete="CASCADE"), unique=True, index=True)
    chief_complaint: Mapped[str] = mapped_column(Text)
    symptoms: Mapped[str | None] = mapped_column(Text)
    symptom_start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pain_level: Mapped[int | None] = mapped_column(Integer)
    temperature: Mapped[float | None] = mapped_column(Float)
    systolic_bp: Mapped[int | None] = mapped_column(Integer)
    diastolic_bp: Mapped[int | None] = mapped_column(Integer)
    heart_rate: Mapped[int | None] = mapped_column(Integer)
    respiratory_rate: Mapped[int | None] = mapped_column(Integer)
    oxygen_saturation: Mapped[float | None] = mapped_column(Float)
    blood_glucose: Mapped[float | None] = mapped_column(Float)
    weight: Mapped[float | None] = mapped_column(Float)
    height: Mapped[float | None] = mapped_column(Float)
    consciousness_level: Mapped[str | None] = mapped_column(String(50))
    severe_bleeding: Mapped[bool] = mapped_column(Boolean, default=False)
    difficulty_breathing: Mapped[bool] = mapped_column(Boolean, default=False)
    chest_pain: Mapped[bool] = mapped_column(Boolean, default=False)
    seizure: Mapped[bool] = mapped_column(Boolean, default=False)
    loss_of_consciousness: Mapped[bool] = mapped_column(Boolean, default=False)
    severe_allergy: Mapped[bool] = mapped_column(Boolean, default=False)
    pregnancy: Mapped[bool] = mapped_column(Boolean, default=False)
    recent_surgery: Mapped[bool] = mapped_column(Boolean, default=False)
    chronic_diseases: Mapped[str | None] = mapped_column(Text)
    medications: Mapped[str | None] = mapped_column(Text)
    nurse_notes: Mapped[str | None] = mapped_column(Text)
    human_priority: Mapped[Priority] = mapped_column(Enum(Priority, native_enum=False))
    ai_priority: Mapped[Priority | None] = mapped_column(Enum(Priority, native_enum=False))
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    final_priority: Mapped[Priority | None] = mapped_column(Enum(Priority, native_enum=False))
    finalized_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    disagreement_reason: Mapped[str | None] = mapped_column(Text)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    visit: Mapped[Visit] = relationship(back_populates="triage")


class Consultation(Base, TimestampMixin):
    __tablename__ = "consultations"
    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id", ondelete="CASCADE"), unique=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    diagnosis: Mapped[str | None] = mapped_column(Text)
    clinical_notes: Mapped[str | None] = mapped_column(Text)
    treatment_plan: Mapped[str | None] = mapped_column(Text)
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    visit: Mapped[Visit] = relationship(back_populates="consultation")
    doctor: Mapped[Doctor] = relationship()


class LabOrder(Base, TimestampMixin):
    __tablename__ = "lab_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    test_name: Mapped[str] = mapped_column(String(160))
    priority: Mapped[Priority] = mapped_column(Enum(Priority, native_enum=False), default=Priority.NORMAL)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, native_enum=False), default=OrderStatus.REQUESTED)
    result: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RadiologyOrder(Base, TimestampMixin):
    __tablename__ = "radiology_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    scan_type: Mapped[str] = mapped_column(String(120))
    body_area: Mapped[str] = mapped_column(String(120))
    priority: Mapped[Priority] = mapped_column(Enum(Priority, native_enum=False), default=Priority.NORMAL)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, native_enum=False), default=OrderStatus.REQUESTED)
    report: Mapped[str | None] = mapped_column(Text)
    attachment_reference: Mapped[str | None] = mapped_column(String(255))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Prescription(Base, TimestampMixin):
    __tablename__ = "prescriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    items: Mapped[list["PrescriptionItem"]] = relationship(back_populates="prescription", cascade="all, delete-orphan")


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id", ondelete="CASCADE"))
    medication_name: Mapped[str] = mapped_column(String(160))
    dosage: Mapped[str] = mapped_column(String(100))
    frequency: Mapped[str] = mapped_column(String(100))
    duration: Mapped[str] = mapped_column(String(100))
    instructions: Mapped[str | None] = mapped_column(Text)
    prescription: Mapped[Prescription] = relationship(back_populates="items")


class AIPrediction(Base):
    __tablename__ = "ai_predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), index=True)
    model_name: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(50))
    prediction: Mapped[Priority] = mapped_column(Enum(Priority, native_enum=False))
    confidence: Mapped[float] = mapped_column(Float)
    explanation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    accepted_by_user: Mapped[bool | None] = mapped_column(Boolean)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(80))
    old_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    new_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)
