from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.core.enums import UserRole


ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.ADMIN: {"*"},
    UserRole.RECEPTIONIST: {"patient:create", "patient:read", "patient:update", "visit:create", "visit:read", "visit:close", "insurance:manage", "department:read", "queue:read", "ocr:extract"},
    UserRole.TRIAGE_NURSE: {"patient:read", "visit:read", "visit:close", "triage:create", "triage:finalize", "queue:read", "ai:predict", "ai:review"},
    UserRole.NURSE: {"patient:read", "visit:read", "queue:read", "triage:read"},
    UserRole.DOCTOR: {"patient:read", "visit:read", "visit:close", "visit:clinical", "queue:read", "queue:call", "consultation:create", "lab:create", "radiology:create", "prescription:create", "ai:review"},
    UserRole.LAB_TECHNICIAN: {"patient:read", "visit:read", "lab:read", "lab:update"},
    UserRole.RADIOLOGY_TECHNICIAN: {"patient:read", "visit:read", "radiology:read", "radiology:update"},
    UserRole.PHARMACIST: {"prescription:read", "prescription:update"},
    UserRole.DISPLAY: {"display:read"},
}


def has_permission(role: UserRole, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(role, set())
    return "*" in permissions or permission in permissions


def require_permission(permission: str) -> Callable:
    from app.routers.dependencies import get_current_user

    def dependency(current_user=Depends(get_current_user)):
        if not has_permission(current_user.role, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return dependency
