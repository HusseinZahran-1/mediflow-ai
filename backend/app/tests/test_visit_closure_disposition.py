from contextlib import contextmanager

from sqlalchemy import event, select
from sqlalchemy.dialects import postgresql

from app.core.enums import OrderStatus, RoomStatus, UserRole, VisitStatus
from app.core.security import hash_password
from app.models import AuditLog, Consultation, Doctor, LabOrder, Prescription, Room, Triage, User, Visit


def _create_visit(client, reception_headers, identity_number: str) -> dict:
    patient = client.post(
        "/api/v1/patients",
        json={
            "full_name": f"Closure Patient {identity_number}",
            "gender": "FEMALE",
            "identity_type": "NATIONAL_ID",
            "identity_number": identity_number,
            "is_military": False,
        },
        headers=reception_headers,
    )
    assert patient.status_code == 201, patient.text
    visit = client.post(
        "/api/v1/visits",
        json={
            "patient_id": patient.json()["id"],
            "department_id": 1,
            "visit_type": "EMERGENCY",
            "arrival_method": "WALKING",
        },
        headers=reception_headers,
    )
    assert visit.status_code == 201, visit.text
    return visit.json()


def _triage_visit(client, triage_headers, visit_id: int, *, finalize: bool) -> dict:
    triage = client.post(
        f"/api/v1/visits/{visit_id}/triage",
        json={
            "chief_complaint": "Academic workflow assessment",
            "temperature": 37,
            "heart_rate": 80,
            "respiratory_rate": 18,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "oxygen_saturation": 98,
            "pain_level": 2,
            "human_priority": "NORMAL",
        },
        headers=triage_headers,
    )
    assert triage.status_code == 201, triage.text
    if not finalize:
        return triage.json()
    reason = None if triage.json()["ai_priority"] == "NORMAL" else "Clinical review confirmed normal priority."
    finalized = client.post(
        f"/api/v1/visits/{visit_id}/triage/finalize",
        json={"final_priority": "NORMAL", "disagreement_reason": reason},
        headers=triage_headers,
    )
    assert finalized.status_code == 200, finalized.text
    return finalized.json()


def _start_documented_consultation(client, doctor_headers, visit_id: int, *, document: bool = True) -> dict:
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
    if document:
        documented = client.patch(
            f"/api/v1/visits/{visit_id}/consultation",
            json={"diagnosis": "Documented academic diagnosis", "clinical_notes": "Disposition reviewed."},
            headers=doctor_headers,
        )
        assert documented.status_code == 200, documented.text
        return documented.json()
    return started.json()


def _create_prescription(client, doctor_headers, visit_id: int, medication: str = "Test medicine") -> dict:
    response = client.post(
        f"/api/v1/visits/{visit_id}/prescriptions",
        json={
            "items": [
                {
                    "medication_name": medication,
                    "dosage": "10 mg",
                    "frequency": "Once daily",
                    "duration": "3 days",
                }
            ]
        },
        headers=doctor_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _visit_audit(db_session, visit_id: int, action: str) -> AuditLog:
    result = db_session.scalar(
        select(AuditLog)
        .where(AuditLog.entity_id == str(visit_id), AuditLog.action == action)
        .order_by(AuditLog.id.desc())
    )
    assert result is not None
    return result


@contextmanager
def _locked_select_tables(db_session):
    locked_tables: list[str] = []

    def record_lock(_connection, clause, _multiparams, _params, _execution_options):
        if getattr(clause, "_for_update_arg", None) is None:
            return
        sql = str(clause.compile(dialect=postgresql.dialect()))
        for table in ("visits", "triages", "lab_orders", "radiology_orders", "prescriptions", "rooms"):
            if f"FROM {table}" in sql:
                locked_tables.append(table)
                break

    event.listen(db_session.bind, "before_execute", record_lock)
    try:
        yield locked_tables
    finally:
        event.remove(db_session.bind, "before_execute", record_lock)


def test_reception_closure_checks_expected_state_and_audits_reason(
    client,
    db_session,
    reception_headers,
    created_visit,
):
    stale = client.post(
        f"/api/v1/visits/{created_visit['id']}/closure",
        json={
            "status": "CANCELLED",
            "reason": "Duplicate registration",
            "expected_status": "IN_TRIAGE",
        },
        headers=reception_headers,
    )
    assert stale.status_code == 409, stale.text
    assert db_session.get(Visit, created_visit["id"]).status == VisitStatus.WAITING_FOR_TRIAGE

    too_short = client.post(
        f"/api/v1/visits/{created_visit['id']}/closure",
        json={"status": "CANCELLED", "reason": "  ", "expected_status": "WAITING_FOR_TRIAGE"},
        headers=reception_headers,
    )
    assert too_short.status_code == 422, too_short.text

    closed = client.post(
        f"/api/v1/visits/{created_visit['id']}/closure",
        json={
            "status": "CANCELLED",
            "reason": "Duplicate registration",
            "expected_status": "WAITING_FOR_TRIAGE",
        },
        headers=reception_headers,
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "CANCELLED"
    assert closed.json()["completed_at"] is not None
    record = _visit_audit(db_session, created_visit["id"], "VISIT_CLOSED")
    assert record.new_data == {
        "status": "CANCELLED",
        "reason": "Duplicate registration",
        "cancelled_prescriptions": 0,
    }


def test_closure_enforces_reception_triage_and_general_permissions(
    client,
    reception_headers,
    triage_headers,
    display_headers,
    created_visit,
):
    receptionist_lwbs = client.post(
        f"/api/v1/visits/{created_visit['id']}/closure",
        json={
            "status": "LEFT_WITHOUT_BEING_SEEN",
            "reason": "Patient departed",
            "expected_status": "WAITING_FOR_TRIAGE",
        },
        headers=reception_headers,
    )
    assert receptionist_lwbs.status_code == 403, receptionist_lwbs.text

    forbidden_role = client.post(
        f"/api/v1/visits/{created_visit['id']}/closure",
        json={
            "status": "CANCELLED",
            "reason": "Not authorized",
            "expected_status": "WAITING_FOR_TRIAGE",
        },
        headers=display_headers,
    )
    assert forbidden_role.status_code == 403, forbidden_role.text

    triage_lwbs = client.post(
        f"/api/v1/visits/{created_visit['id']}/closure",
        json={
            "status": "LEFT_WITHOUT_BEING_SEEN",
            "reason": "Patient departed",
            "expected_status": "WAITING_FOR_TRIAGE",
        },
        headers=triage_headers,
    )
    assert triage_lwbs.status_code == 200, triage_lwbs.text

    second = _create_visit(client, reception_headers, "TRIAGE-CLOSE-2")
    _triage_visit(client, triage_headers, second["id"], finalize=False)
    triage_cancelled = client.post(
        f"/api/v1/visits/{second['id']}/closure",
        json={
            "status": "CANCELLED",
            "reason": "Triage registration error",
            "expected_status": "IN_TRIAGE",
        },
        headers=triage_headers,
    )
    assert triage_cancelled.status_code == 200, triage_cancelled.text
    assert triage_cancelled.json()["status"] == "CANCELLED"


def test_triage_visit_lock_prevents_finalization_after_closure(
    client,
    db_session,
    triage_headers,
    created_visit,
):
    with _locked_select_tables(db_session) as create_locks:
        _triage_visit(client, triage_headers, created_visit["id"], finalize=False)
    assert create_locks[0] == "visits"

    closed = client.post(
        f"/api/v1/visits/{created_visit['id']}/closure",
        json={
            "status": "CANCELLED",
            "reason": "Patient left during triage",
            "expected_status": "IN_TRIAGE",
        },
        headers=triage_headers,
    )
    assert closed.status_code == 200, closed.text

    with _locked_select_tables(db_session) as finalize_locks:
        rejected_finalize = client.post(
            f"/api/v1/visits/{created_visit['id']}/triage/finalize",
            json={"final_priority": "NORMAL"},
            headers=triage_headers,
        )
    assert rejected_finalize.status_code == 409, rejected_finalize.text
    assert finalize_locks[:2] == ["visits", "triages"]
    assert db_session.get(Visit, created_visit["id"]).status == VisitStatus.CANCELLED
    triage = db_session.scalar(select(Triage).where(Triage.visit_id == created_visit["id"]))
    assert triage.finalized_at is None


def test_doctor_closure_cancels_active_prescriptions_and_releases_room(
    client,
    db_session,
    doctor_headers,
    lab_headers,
    pharmacy_headers,
    triaged_visit,
):
    _start_documented_consultation(client, doctor_headers, triaged_visit["id"])
    prescription = _create_prescription(client, doctor_headers, triaged_visit["id"])
    lab = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/lab-orders",
        json={"test_name": "CBC", "priority": "NORMAL"},
        headers=doctor_headers,
    )
    assert lab.status_code == 201, lab.text
    result = client.patch(
        f"/api/v1/lab-orders/{lab.json()['id']}",
        json={"status": "COMPLETED", "result": "No significant finding"},
        headers=lab_headers,
    )
    assert result.status_code == 200, result.text

    assigned = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/assign-room?room_id=1",
        headers=doctor_headers,
    )
    assert assigned.status_code == 200, assigned.text
    assert db_session.get(Room, 1).status == RoomStatus.OCCUPIED

    closed = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/closure",
        json={
            "status": "LEFT_WITHOUT_BEING_SEEN",
            "reason": "Patient declined further care",
            "expected_status": "WAITING_FOR_DOCTOR",
        },
        headers=doctor_headers,
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "LEFT_WITHOUT_BEING_SEEN"
    assert closed.json()["assigned_room_id"] is None
    assert db_session.get(Room, 1).status == RoomStatus.AVAILABLE
    assert db_session.get(Prescription, prescription["id"]).status == "CANCELLED"
    assert client.get("/api/v1/prescriptions?worklist=true", headers=pharmacy_headers).json() == []
    record = _visit_audit(db_session, triaged_visit["id"], "VISIT_CLOSED")
    assert record.new_data["cancelled_prescriptions"] == 1
    assert record.new_data["reason"] == "Patient declined further care"


def test_doctor_closure_respects_ownership_and_admin_uses_state_machine(
    client,
    db_session,
    doctor_headers,
    admin_headers,
    triaged_visit,
):
    other_user = User(
        email="other.closure.doctor@test.example.com",
        full_name="Other Closure Doctor",
        password_hash=hash_password("Password123!"),
        role=UserRole.DOCTOR,
    )
    db_session.add(other_user)
    db_session.flush()
    other_doctor = Doctor(
        user_id=other_user.id,
        department_id=1,
        specialization="Emergency Medicine",
        medical_license_number="TEST-CLOSURE-OTHER",
    )
    db_session.add(other_doctor)
    db_session.flush()
    visit = db_session.get(Visit, triaged_visit["id"])
    visit.assigned_doctor_id = other_doctor.id
    db_session.commit()

    rejected = client.post(
        f"/api/v1/visits/{visit.id}/closure",
        json={
            "status": "CANCELLED",
            "reason": "Doctor requested closure",
            "expected_status": "WAITING_FOR_DOCTOR",
        },
        headers=doctor_headers,
    )
    assert rejected.status_code == 403, rejected.text
    assert db_session.get(Visit, visit.id).status == VisitStatus.WAITING_FOR_DOCTOR

    admin_closed = client.post(
        f"/api/v1/visits/{visit.id}/closure",
        json={
            "status": "CANCELLED",
            "reason": "Administrative correction",
            "expected_status": "WAITING_FOR_DOCTOR",
        },
        headers=admin_headers,
    )
    assert admin_closed.status_code == 200, admin_closed.text
    invalid_terminal_reopen = client.post(
        f"/api/v1/visits/{visit.id}/closure",
        json={
            "status": "LEFT_WITHOUT_BEING_SEEN",
            "reason": "Invalid second closure",
            "expected_status": "CANCELLED",
        },
        headers=admin_headers,
    )
    assert invalid_terminal_reopen.status_code == 409, invalid_terminal_reopen.text


def test_admitted_disposition_completes_consultation_cancels_rx_and_releases_room(
    client,
    db_session,
    doctor_headers,
    pharmacy_headers,
    triaged_visit,
):
    _start_documented_consultation(client, doctor_headers, triaged_visit["id"])
    prescription = _create_prescription(client, doctor_headers, triaged_visit["id"])

    admitted = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/disposition",
        json={"status": "ADMITTED", "reason": "Requires inpatient monitoring"},
        headers=doctor_headers,
    )
    assert admitted.status_code == 200, admitted.text
    assert admitted.json()["status"] == "ADMITTED"
    assert admitted.json()["assigned_room_id"] is None
    assert admitted.json()["completed_at"] is not None
    assert db_session.get(Room, 1).status == RoomStatus.AVAILABLE
    consultation = db_session.scalar(select(Consultation).where(Consultation.visit_id == triaged_visit["id"]))
    assert consultation.completed_at is not None
    assert db_session.get(Prescription, prescription["id"]).status == "CANCELLED"
    assert client.get("/api/v1/prescriptions?worklist=true", headers=pharmacy_headers).json() == []
    record = _visit_audit(db_session, triaged_visit["id"], "VISIT_DISPOSITION_RECORDED")
    assert record.new_data == {
        "status": "ADMITTED",
        "reason": "Requires inpatient monitoring",
        "destination": None,
        "cancelled_prescriptions": 1,
    }


def test_transfer_requires_destination_is_doctor_only_and_records_destination(
    client,
    db_session,
    doctor_headers,
    admin_headers,
    triaged_visit,
):
    _start_documented_consultation(client, doctor_headers, triaged_visit["id"])

    missing_destination = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/disposition",
        json={"status": "TRANSFERRED", "reason": "Needs specialist care"},
        headers=doctor_headers,
    )
    assert missing_destination.status_code == 422, missing_destination.text

    admin_rejected = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/disposition",
        json={"status": "ADMITTED", "reason": "Admin cannot decide"},
        headers=admin_headers,
    )
    assert admin_rejected.status_code == 403, admin_rejected.text

    transferred = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/disposition",
        json={
            "status": "TRANSFERRED",
            "reason": "Needs specialist care",
            "destination": "  Regional Cardiac Center  ",
        },
        headers=doctor_headers,
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["status"] == "TRANSFERRED"
    record = _visit_audit(db_session, triaged_visit["id"], "VISIT_DISPOSITION_RECORDED")
    assert record.new_data["destination"] == "Regional Cardiac Center"


def test_disposition_rejects_wrong_state_ownership_missing_notes_and_pending_orders(
    client,
    db_session,
    doctor_headers,
    triaged_visit,
):
    wrong_state = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/disposition",
        json={"status": "ADMITTED", "reason": "Needs inpatient care"},
        headers=doctor_headers,
    )
    assert wrong_state.status_code == 409, wrong_state.text

    visit = db_session.get(Visit, triaged_visit["id"])
    visit.status = VisitStatus.WITH_DOCTOR
    visit.assigned_doctor_id = None
    db_session.commit()
    unowned = client.post(
        f"/api/v1/visits/{visit.id}/disposition",
        json={"status": "ADMITTED", "reason": "Needs inpatient care"},
        headers=doctor_headers,
    )
    assert unowned.status_code == 403, unowned.text

    visit.assigned_doctor_id = 1
    db_session.commit()
    no_consultation = client.post(
        f"/api/v1/visits/{visit.id}/disposition",
        json={"status": "ADMITTED", "reason": "Needs inpatient care"},
        headers=doctor_headers,
    )
    assert no_consultation.status_code == 409, no_consultation.text

    started = client.post(f"/api/v1/visits/{visit.id}/start-consultation", headers=doctor_headers)
    assert started.status_code == 200, started.text
    undocumented = client.post(
        f"/api/v1/visits/{visit.id}/disposition",
        json={"status": "ADMITTED", "reason": "Needs inpatient care"},
        headers=doctor_headers,
    )
    assert undocumented.status_code == 409, undocumented.text

    documented = client.patch(
        f"/api/v1/visits/{visit.id}/consultation",
        json={"clinical_notes": "Requires monitored inpatient treatment."},
        headers=doctor_headers,
    )
    assert documented.status_code == 200, documented.text
    db_session.add(
        LabOrder(
            visit_id=visit.id,
            doctor_id=1,
            test_name="Pending academic panel",
            status=OrderStatus.REQUESTED,
        )
    )
    db_session.commit()
    pending = client.post(
        f"/api/v1/visits/{visit.id}/disposition",
        json={"status": "ADMITTED", "reason": "Needs inpatient care"},
        headers=doctor_headers,
    )
    assert pending.status_code == 409, pending.text
    assert db_session.get(Visit, visit.id).status == VisitStatus.WITH_DOCTOR
    consultation = db_session.scalar(select(Consultation).where(Consultation.visit_id == visit.id))
    assert consultation.completed_at is None


def test_visit_and_child_rows_are_locked_in_consistent_order_and_last_rx_discharges(
    client,
    db_session,
    doctor_headers,
    lab_headers,
    pharmacy_headers,
    triaged_visit,
):
    with _locked_select_tables(db_session) as call_locks:
        called = client.post(
            f"/api/v1/queue/{triaged_visit['id']}/call",
            json={"room_id": 1},
            headers=doctor_headers,
        )
    assert called.status_code == 200, called.text
    assert call_locks[:2] == ["visits", "rooms"]

    started = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/start-consultation",
        headers=doctor_headers,
    )
    assert started.status_code == 200, started.text
    documented = client.patch(
        f"/api/v1/visits/{triaged_visit['id']}/consultation",
        json={"diagnosis": "Lock-order diagnosis"},
        headers=doctor_headers,
    )
    assert documented.status_code == 200, documented.text
    lab = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/lab-orders",
        json={"test_name": "Lock order panel", "priority": "NORMAL"},
        headers=doctor_headers,
    )
    assert lab.status_code == 201, lab.text
    with _locked_select_tables(db_session) as diagnostic_locks:
        completed_lab = client.patch(
            f"/api/v1/lab-orders/{lab.json()['id']}",
            json={"status": "COMPLETED", "result": "Verified"},
            headers=lab_headers,
        )
    assert completed_lab.status_code == 200, completed_lab.text
    assert diagnostic_locks[:2] == ["visits", "lab_orders"]
    assert client.get(
        f"/api/v1/visits/{triaged_visit['id']}", headers=doctor_headers
    ).json()["status"] == "WAITING_FOR_DOCTOR"

    with _locked_select_tables(db_session) as direct_room_locks:
        direct_room = client.post(
            f"/api/v1/visits/{triaged_visit['id']}/assign-room?room_id=1",
            headers=doctor_headers,
        )
    assert direct_room.status_code == 200, direct_room.text
    assert direct_room_locks[:2] == ["visits", "rooms"]

    with _locked_select_tables(db_session) as patch_room_locks:
        patched_room = client.patch(
            f"/api/v1/visits/{triaged_visit['id']}",
            json={"assigned_room_id": 2},
            headers=doctor_headers,
        )
    assert patched_room.status_code == 200, patched_room.text
    assert patch_room_locks[:2] == ["visits", "rooms"]
    assert db_session.get(Room, 1).status == RoomStatus.AVAILABLE
    assert db_session.get(Room, 2).status == RoomStatus.OCCUPIED

    assert client.post(
        f"/api/v1/queue/{triaged_visit['id']}/call",
        json={"room_id": 1},
        headers=doctor_headers,
    ).status_code == 200
    assert client.post(
        f"/api/v1/visits/{triaged_visit['id']}/start-consultation",
        headers=doctor_headers,
    ).status_code == 200
    first_rx = _create_prescription(client, doctor_headers, triaged_visit["id"], "First medicine")
    second_rx = _create_prescription(client, doctor_headers, triaged_visit["id"], "Second medicine")
    completed = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/complete-consultation",
        headers=doctor_headers,
    )
    assert completed.status_code == 200, completed.text

    with _locked_select_tables(db_session) as first_rx_locks:
        first_dispense = client.patch(
            f"/api/v1/prescriptions/{first_rx['id']}",
            json={"status": "DISPENSED"},
            headers=pharmacy_headers,
        )
    assert first_dispense.status_code == 200, first_dispense.text
    assert first_rx_locks[:2] == ["visits", "prescriptions"]
    assert db_session.get(Visit, triaged_visit["id"]).status == VisitStatus.COMPLETED

    with _locked_select_tables(db_session) as second_rx_locks:
        second_dispense = client.patch(
            f"/api/v1/prescriptions/{second_rx['id']}",
            json={"status": "DISPENSED"},
            headers=pharmacy_headers,
        )
    assert second_dispense.status_code == 200, second_dispense.text
    assert second_rx_locks[:2] == ["visits", "prescriptions"]
    assert db_session.get(Visit, triaged_visit["id"]).status == VisitStatus.DISCHARGED


def test_triage_can_record_lwbs_after_triage_has_started(
    client, triage_headers, created_visit
):
    _triage_visit(client, triage_headers, created_visit["id"], finalize=False)
    closed = client.post(
        f"/api/v1/visits/{created_visit['id']}/closure",
        json={
            "status": "LEFT_WITHOUT_BEING_SEEN",
            "reason": "Patient left during triage assessment",
            "expected_status": "IN_TRIAGE",
        },
        headers=triage_headers,
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "LEFT_WITHOUT_BEING_SEEN"


def test_doctor_can_close_called_patient_and_room_is_released(
    client, db_session, doctor_headers, triaged_visit
):
    called = client.post(
        f"/api/v1/queue/{triaged_visit['id']}/call",
        json={"room_id": 1},
        headers=doctor_headers,
    )
    assert called.status_code == 200, called.text
    assert called.json()["status"] == "CALLED"
    assert db_session.get(Room, 1).status == RoomStatus.OCCUPIED

    closed = client.post(
        f"/api/v1/visits/{triaged_visit['id']}/closure",
        json={
            "status": "LEFT_WITHOUT_BEING_SEEN",
            "reason": "Patient did not respond after being called",
            "expected_status": "CALLED",
        },
        headers=doctor_headers,
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "LEFT_WITHOUT_BEING_SEEN"
    assert closed.json()["assigned_room_id"] is None
    assert db_session.get(Room, 1).status == RoomStatus.AVAILABLE
