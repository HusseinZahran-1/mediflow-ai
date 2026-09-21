import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import HTTPException, status

from app.core.config import settings


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=64)
    return f"scrypt$16384$8$1${_b64encode(salt)}${_b64encode(derived)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=_b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=64
        )
        return hmac.compare_digest(actual, _b64decode(expected))
    except (ValueError, TypeError):
        return False


def create_token(subject: str, token_type: Literal["access", "refresh"], role: str) -> tuple[str, str, datetime]:
    now = datetime.now(UTC)
    expires = now + (
        timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
        if token_type == "access"
        else timedelta(days=settings.REFRESH_TOKEN_DAYS)
    )
    jti = str(uuid.uuid4())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": subject, "type": token_type, "role": role, "jti": jti, "iat": int(now.timestamp()), "exp": int(expires.timestamp())}
    encoded_header = _b64encode(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    message = f"{encoded_header}.{encoded_payload}".encode()
    signature = hmac.new(settings.JWT_SECRET_KEY.encode(), message, hashlib.sha256).digest()
    return f"{message.decode()}.{_b64encode(signature)}", jti, expires


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        message = f"{encoded_header}.{encoded_payload}".encode()
        expected = hmac.new(settings.JWT_SECRET_KEY.encode(), message, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(encoded_signature)):
            raise credentials_error
        payload = json.loads(_b64decode(encoded_payload))
        if int(payload["exp"]) <= int(time.time()):
            raise credentials_error
        if expected_type and payload.get("type") != expected_type:
            raise credentials_error
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        raise credentials_error from exc

