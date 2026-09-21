from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_token, decode_token, hash_password, verify_password
from app.core.enums import UserRole
from app.models import Department, Doctor, RevokedToken, User
from app.schemas import TokenPair, UserCreate
from app.services.audit import audit


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return user


def issue_token_pair(user: User) -> TokenPair:
    access, _, access_expires = create_token(str(user.id), "access", user.role.value)
    refresh, _, _ = create_token(str(user.id), "refresh", user.role.value)
    expires_in = max(0, int((access_expires - datetime.now(UTC)).total_seconds()))
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=expires_in,
        user=user,
    )


def _revoke_payload(db: Session, payload: dict) -> None:
    if db.scalar(select(RevokedToken).where(RevokedToken.jti == payload["jti"])):
        return
    db.add(RevokedToken(
        jti=payload["jti"],
        expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
    ))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if db.scalar(select(RevokedToken).where(RevokedToken.jti == payload["jti"])):
            return
        raise exc


def refresh_tokens(db: Session, refresh_token: str) -> TokenPair:
    payload = decode_token(refresh_token, "refresh")
    if db.scalar(select(RevokedToken).where(RevokedToken.jti == payload["jti"])):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive or missing")
    # Rotate refresh tokens: once exchanged, the previous token cannot be replayed.
    _revoke_payload(db, payload)
    return issue_token_pair(user)


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    payload = decode_token(refresh_token, "refresh")
    _revoke_payload(db, payload)


def create_user(db: Session, data: UserCreate, actor_id: int | None = None) -> User:
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(status_code=409, detail="Email is already registered")
    department = None
    if data.role == UserRole.DOCTOR:
        department = db.get(Department, data.department_id)
        if not department or not department.is_active:
            raise HTTPException(status_code=422, detail="An active department is required for doctors")
        if db.scalar(select(Doctor).where(Doctor.medical_license_number == data.medical_license_number)):
            raise HTTPException(status_code=409, detail="Medical license number is already registered")
    try:
        user = User(
            email=data.email.lower(),
            full_name=data.full_name,
            role=data.role,
            password_hash=hash_password(data.password),
        )
        db.add(user)
        db.flush()
        if data.role == UserRole.DOCTOR:
            db.add(Doctor(
                user_id=user.id,
                department_id=department.id,
                specialization=data.specialization,
                medical_license_number=data.medical_license_number,
            ))
        audit(db, user_id=actor_id, action="USER_CREATED", entity_type="User", entity_id=user.id, new_data={"email": user.email, "role": user.role.value})
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email or medical license number is already registered") from exc
