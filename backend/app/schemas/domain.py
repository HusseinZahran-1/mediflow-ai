from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.enums import ArrivalMethod, OrderStatus, Priority, RoomStatus, UserRole, VisitStatus, VisitType


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=False)


class Message(BaseModel):
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    department_id: int | None = None
    specialization: str | None = Field(default=None, max_length=150)
    medical_license_number: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_doctor_profile(self):
        self.full_name = self.full_name.strip()
        if len(self.full_name) < 2:
            raise ValueError("full_name must contain at least 2 non-whitespace characters")
        if self.specialization is not None:
            self.specialization = self.specialization.strip() or None
        if self.medical_license_number is not None:
            self.medical_license_number = self.medical_license_number.strip() or None
        if self.role == UserRole.DOCTOR and not all((self.department_id, self.specialization, self.medical_license_number)):
            raise ValueError("department_id, specialization, and medical_license_number are required for doctors")
        return self


class UserRead(ORMModel):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class PatientBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    phone_number: str | None = Field(default=None, max_length=30)
    gender: str = Field(min_length=1, max_length=30)
    date_of_birth: date | None = None
    nationality: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=255)
    identity_type: str = Field(min_length=2, max_length=50)
    identity_number: str = Field(min_length=2, max_length=100)
    is_military: bool = False
    military_number: str | None = Field(default=None, max_length=100)
    emergency_contact_name: str | None = Field(default=None, max_length=150)
    emergency_contact_phone: str | None = Field(default=None, max_length=30)
    blood_type: str | None = Field(default=None, max_length=8)

    @model_validator(mode="after")
    def validate_military(self):
        self.full_name = self.full_name.strip()
        self.gender = self.gender.strip()
        self.identity_type = self.identity_type.strip()
        self.identity_number = self.identity_number.strip()
        if len(self.full_name) < 2:
            raise ValueError("full_name must contain at least 2 non-whitespace characters")
        if not self.gender:
            raise ValueError("gender cannot be blank")
        if len(self.identity_type) < 2:
            raise ValueError("identity_type must contain at least 2 non-whitespace characters")
        if len(self.identity_number) < 2:
            raise ValueError("identity_number must contain at least 2 non-whitespace characters")
        if self.military_number is not None:
            self.military_number = self.military_number.strip() or None
        if self.is_military and not self.military_number:
            raise ValueError("military_number is required for military patients")
        if not self.is_military:
            self.military_number = None
        if self.date_of_birth and self.date_of_birth > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return self


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone_number: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    nationality: str | None = None
    address: str | None = None
    identity_type: str | None = None
    identity_number: str | None = None
    is_military: bool | None = None
    military_number: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    blood_type: str | None = None

    @model_validator(mode="after")
    def validate_update(self):
        if self.full_name is not None:
            self.full_name = self.full_name.strip()
            if len(self.full_name) < 2:
                raise ValueError("full_name must contain at least 2 non-whitespace characters")
        if self.identity_number is not None:
            self.identity_number = self.identity_number.strip()
            if len(self.identity_number) < 2:
                raise ValueError("identity_number must contain at least 2 non-whitespace characters")
        if self.identity_type is not None:
            self.identity_type = self.identity_type.strip()
            if len(self.identity_type) < 2:
                raise ValueError("identity_type must contain at least 2 non-whitespace characters")
        if self.gender is not None:
            self.gender = self.gender.strip()
            if not self.gender:
                raise ValueError("gender cannot be blank")
        if self.military_number is not None:
            self.military_number = self.military_number.strip() or None
        if self.date_of_birth and self.date_of_birth > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return self


class PatientRead(ORMModel):
    id: int
    medical_record_number: str
    full_name: str
    phone_number: str | None
    gender: str
    date_of_birth: date | None
    age: int | None
    nationality: str | None
    address: str | None
    identity_type: str
    identity_number: str
    is_military: bool
    military_number: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    blood_type: str | None
    is_active: bool
    merged_into_id: int | None
    created_at: datetime
    updated_at: datetime


class PatientPage(BaseModel):
    items: list[PatientRead]
    total: int
    page: int
    page_size: int


class InsuranceCreate(BaseModel):
    company_name: str = Field(min_length=2, max_length=150)
    insurance_number: str = Field(min_length=2, max_length=100)
    policy_number: str | None = None
    coverage_type: str | None = None
    expiry_date: date | None = None
    is_active: bool = True


class InsuranceUpdate(BaseModel):
    company_name: str | None = None
    insurance_number: str | None = None
    policy_number: str | None = None
    coverage_type: str | None = None
    expiry_date: date | None = None
    is_active: bool | None = None


class InsuranceRead(InsuranceCreate, ORMModel):
    id: int
    patient_id: int
    created_at: datetime
    updated_at: datetime


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=1, max_length=20)
    ticket_prefix: str = Field(min_length=1, max_length=5, pattern=r"^[A-Za-z0-9]+$")
    description: str | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def normalize_department(self):
        self.name = self.name.strip()
        self.code = self.code.strip().upper()
        self.ticket_prefix = self.ticket_prefix.strip().upper()
        if len(self.name) < 2 or not self.code or not self.ticket_prefix:
            raise ValueError("Department name, code, and ticket prefix cannot be blank")
        if self.description is not None:
            self.description = self.description.strip() or None
        return self


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    code: str | None = Field(default=None, min_length=1, max_length=20)
    ticket_prefix: str | None = Field(default=None, min_length=1, max_length=5, pattern=r"^[A-Za-z0-9]+$")
    description: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def normalize_department_update(self):
        if self.name is not None:
            self.name = self.name.strip()
            if len(self.name) < 2:
                raise ValueError("Department name cannot be blank")
        if self.code is not None:
            self.code = self.code.strip().upper()
            if not self.code:
                raise ValueError("Department code cannot be blank")
        if self.ticket_prefix is not None:
            self.ticket_prefix = self.ticket_prefix.strip().upper()
            if not self.ticket_prefix:
                raise ValueError("Ticket prefix cannot be blank")
        if self.description is not None:
            self.description = self.description.strip() or None
        return self


class DepartmentRead(DepartmentCreate, ORMModel):
    id: int


class RoomCreate(BaseModel):
    department_id: int
    room_number: str = Field(min_length=1, max_length=30)
    room_name: str | None = Field(default=None, max_length=100)
    room_type: str | None = Field(default=None, max_length=80)
    status: RoomStatus = RoomStatus.AVAILABLE

    @model_validator(mode="after")
    def normalize_room(self):
        self.room_number = self.room_number.strip()
        if not self.room_number:
            raise ValueError("room_number cannot be blank")
        if self.room_name is not None:
            self.room_name = self.room_name.strip() or None
        if self.room_type is not None:
            self.room_type = self.room_type.strip() or None
        return self


class RoomRead(RoomCreate, ORMModel):
    id: int


class VisitCreate(BaseModel):
    patient_id: int
    department_id: int
    visit_type: VisitType
    arrival_method: ArrivalMethod


class VisitUpdate(BaseModel):
    status: VisitStatus | None = None
    assigned_doctor_id: int | None = None
    assigned_room_id: int | None = None


class VisitClosureCreate(BaseModel):
    status: Literal[VisitStatus.CANCELLED, VisitStatus.LEFT_WITHOUT_BEING_SEEN]
    reason: str = Field(min_length=3, max_length=1000)
    expected_status: VisitStatus

    @model_validator(mode="after")
    def normalize_reason(self):
        self.reason = self.reason.strip()
        if len(self.reason) < 3:
            raise ValueError("Closure reason must contain at least 3 non-whitespace characters")
        return self


class VisitDispositionCreate(BaseModel):
    status: Literal[VisitStatus.ADMITTED, VisitStatus.TRANSFERRED]
    reason: str = Field(min_length=3, max_length=1000)
    destination: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_disposition(self):
        self.reason = self.reason.strip()
        if len(self.reason) < 3:
            raise ValueError("Disposition reason must contain at least 3 non-whitespace characters")
        if self.destination is not None:
            self.destination = self.destination.strip() or None
        if self.status == VisitStatus.TRANSFERRED and not self.destination:
            raise ValueError("Destination is required for transferred visits")
        return self


class VisitRead(ORMModel):
    id: int
    patient_id: int
    department_id: int
    ticket_code: str
    ticket_sequence: int
    ticket_date: date
    public_token: str
    visit_type: VisitType
    arrival_method: ArrivalMethod
    arrival_time: datetime
    status: VisitStatus
    assigned_doctor_id: int | None
    assigned_room_id: int | None
    human_priority: Priority | None
    ai_priority: Priority | None
    final_priority: Priority | None
    priority_score: float
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class CompletedVisitItem(BaseModel):
    visit_id: int
    patient_id: int
    medical_record_number: str
    patient_name: str
    phone_number: str | None
    gender: str
    age: int | None
    identity_number: str
    ticket_code: str
    department_id: int
    department_name: str
    assigned_doctor_id: int | None
    doctor_name: str | None
    priority: Priority | None
    status: VisitStatus
    arrival_time: datetime
    started_at: datetime | None
    completed_at: datetime | None
    duration_minutes: int | None
    diagnosis: str | None
    clinical_notes: str | None
    treatment_plan: str | None


class CompletedVisitPage(BaseModel):
    items: list[CompletedVisitItem]
    total: int
    page: int
    page_size: int


class TriageCreate(BaseModel):
    chief_complaint: str = Field(min_length=2)
    symptoms: str | None = None
    symptom_start_time: datetime | None = None
    pain_level: int | None = Field(default=None, ge=0, le=10)
    temperature: float | None = Field(default=None, ge=25, le=45)
    systolic_bp: int | None = Field(default=None, ge=30, le=300)
    diastolic_bp: int | None = Field(default=None, ge=20, le=200)
    heart_rate: int | None = Field(default=None, ge=20, le=260)
    respiratory_rate: int | None = Field(default=None, ge=4, le=80)
    oxygen_saturation: float | None = Field(default=None, ge=30, le=100)
    blood_glucose: float | None = Field(default=None, ge=10, le=1000)
    weight: float | None = Field(default=None, ge=0.5, le=500)
    height: float | None = Field(default=None, ge=20, le=260)
    consciousness_level: str | None = None
    severe_bleeding: bool = False
    difficulty_breathing: bool = False
    chest_pain: bool = False
    seizure: bool = False
    loss_of_consciousness: bool = False
    severe_allergy: bool = False
    pregnancy: bool = False
    recent_surgery: bool = False
    chronic_diseases: str | None = None
    medications: str | None = None
    nurse_notes: str | None = None
    human_priority: Priority

    @model_validator(mode="after")
    def normalize_text(self):
        self.chief_complaint = self.chief_complaint.strip()
        if len(self.chief_complaint) < 2:
            raise ValueError("chief_complaint must contain at least 2 non-whitespace characters")
        for field_name in ("symptoms", "consciousness_level", "chronic_diseases", "medications", "nurse_notes"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class TriageRead(TriageCreate, ORMModel):
    id: int
    visit_id: int
    ai_priority: Priority | None
    ai_confidence: float | None
    final_priority: Priority | None
    finalized_by: int | None
    disagreement_reason: str | None
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TriageFinalize(BaseModel):
    final_priority: Priority
    disagreement_reason: str | None = None

    @model_validator(mode="after")
    def normalize_disagreement_reason(self):
        if self.disagreement_reason is not None:
            self.disagreement_reason = self.disagreement_reason.strip() or None
        return self


class AIPredictRequest(BaseModel):
    visit_id: int
    human_priority: Priority | None = None
    age: int | None = Field(default=None, ge=0, le=130)
    gender: str | None = None
    temperature: float | None = Field(default=None, ge=25, le=45)
    heart_rate: int | None = Field(default=None, ge=20, le=260)
    respiratory_rate: int | None = Field(default=None, ge=4, le=80)
    systolic_bp: int | None = Field(default=None, ge=30, le=300)
    diastolic_bp: int | None = Field(default=None, ge=20, le=200)
    oxygen_saturation: float | None = Field(default=None, ge=30, le=100)
    pain_level: int | None = Field(default=None, ge=0, le=10)
    arrival_method: ArrivalMethod | None = None
    chief_complaint: str = ""
    medical_history: str | None = None
    consciousness_level: str | None = None
    severe_bleeding: bool = False
    difficulty_breathing: bool = False
    chest_pain: bool = False
    seizure: bool = False
    loss_of_consciousness: bool = False
    severe_allergy: bool = False
    pregnancy: bool = False
    recent_surgery: bool = False


class AIPredictionRead(ORMModel):
    id: int
    visit_id: int
    model_name: str
    model_version: str
    prediction: Priority
    confidence: float
    explanation: dict[str, Any] | None
    input_snapshot: dict[str, Any]
    accepted_by_user: bool | None
    reviewed_by: int | None
    created_at: datetime


class OCRResponse(BaseModel):
    raw_text: str
    review_required: bool = True
    notice: str = "OCR output must be reviewed by authorized reception staff before saving."


class AIReview(BaseModel):
    accepted: bool


class QueueItem(BaseModel):
    visit_id: int
    ticket_code: str
    patient_name: str
    department_id: int
    department: str
    priority: Priority
    status: VisitStatus
    arrival_time: datetime
    wait_minutes: int
    room: str | None = None


class DisplayItem(BaseModel):
    ticket_code: str
    department: str
    priority: Priority | None = None
    status: VisitStatus
    room: str | None


class CallRequest(BaseModel):
    room_id: int


class ConsultationCreate(BaseModel):
    diagnosis: str | None = None
    clinical_notes: str | None = None
    treatment_plan: str | None = None
    follow_up_date: date | None = None

    @model_validator(mode="after")
    def normalize_notes(self):
        for field_name in ("diagnosis", "clinical_notes", "treatment_plan"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.strip() or None)
        return self


class ConsultationRead(ConsultationCreate, ORMModel):
    id: int
    visit_id: int
    doctor_id: int
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LabOrderCreate(BaseModel):
    test_name: str = Field(min_length=1, max_length=160)
    priority: Priority = Priority.NORMAL
    notes: str | None = None

    @model_validator(mode="after")
    def normalize_lab_order(self):
        self.test_name = self.test_name.strip()
        if not self.test_name:
            raise ValueError("test_name cannot be blank")
        if self.notes is not None:
            self.notes = self.notes.strip() or None
        return self


class LabOrderUpdate(BaseModel):
    status: OrderStatus | None = None
    result: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def normalize_lab_update(self):
        if self.result is not None:
            self.result = self.result.strip() or None
        if self.notes is not None:
            self.notes = self.notes.strip() or None
        return self


class LabOrderRead(ORMModel):
    id: int
    visit_id: int
    ticket_code: str | None = None
    doctor_id: int
    test_name: str
    priority: Priority
    status: OrderStatus
    result: str | None
    notes: str | None
    requested_at: datetime
    completed_at: datetime | None


class RadiologyOrderCreate(BaseModel):
    scan_type: str = Field(min_length=1, max_length=120)
    body_area: str = Field(min_length=1, max_length=120)
    priority: Priority = Priority.NORMAL

    @model_validator(mode="after")
    def normalize_radiology_order(self):
        self.scan_type = self.scan_type.strip()
        self.body_area = self.body_area.strip()
        if not self.scan_type or not self.body_area:
            raise ValueError("scan_type and body_area cannot be blank")
        return self


class RadiologyOrderUpdate(BaseModel):
    status: OrderStatus | None = None
    report: str | None = None
    attachment_reference: str | None = None

    @model_validator(mode="after")
    def normalize_radiology_update(self):
        if self.report is not None:
            self.report = self.report.strip() or None
        if self.attachment_reference is not None:
            self.attachment_reference = self.attachment_reference.strip() or None
        return self


class RadiologyOrderRead(ORMModel):
    id: int
    visit_id: int
    ticket_code: str | None = None
    doctor_id: int
    scan_type: str
    body_area: str
    priority: Priority
    status: OrderStatus
    report: str | None
    attachment_reference: str | None
    requested_at: datetime
    completed_at: datetime | None


class PrescriptionItemCreate(BaseModel):
    medication_name: str = Field(min_length=1, max_length=160)
    dosage: str = Field(min_length=1, max_length=100)
    frequency: str = Field(min_length=1, max_length=100)
    duration: str = Field(min_length=1, max_length=100)
    instructions: str | None = None

    @model_validator(mode="after")
    def normalize_item(self):
        for field_name in ("medication_name", "dosage", "frequency", "duration"):
            value = getattr(self, field_name).strip()
            if not value:
                raise ValueError(f"{field_name} cannot be blank")
            setattr(self, field_name, value)
        if self.instructions is not None:
            self.instructions = self.instructions.strip() or None
        return self


class PrescriptionCreate(BaseModel):
    status: Literal["ACTIVE"] = "ACTIVE"
    items: list[PrescriptionItemCreate] = Field(min_length=1)


class PrescriptionCancelCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def normalize_reason(self):
        self.reason = self.reason.strip()
        if len(self.reason) < 3:
            raise ValueError("Cancellation reason must contain at least 3 non-whitespace characters")
        return self


class PrescriptionItemRead(PrescriptionItemCreate, ORMModel):
    id: int


class PrescriptionRead(ORMModel):
    id: int
    visit_id: int
    ticket_code: str | None = None
    priority: Priority | None = None
    doctor_id: int
    status: str
    items: list[PrescriptionItemRead]
    created_at: datetime
    updated_at: datetime


class AuditRead(ORMModel):
    id: int
    user_id: int | None
    action: str
    entity_type: str
    entity_id: str | None
    old_data: dict[str, Any] | None
    new_data: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime


class DashboardMetrics(BaseModel):
    patients_today: int
    waiting: int
    critical: int
    urgent: int
    normal: int
    completed: int
    average_wait_minutes: float
    longest_wait_minutes: int
    by_department: list[dict[str, Any]]
