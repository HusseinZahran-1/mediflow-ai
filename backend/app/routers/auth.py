from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.routers.dependencies import get_current_user
from app.schemas import LoginRequest, LogoutRequest, Message, RefreshRequest, TokenPair, UserRead
from app.services.auth_service import authenticate, issue_token_pair, refresh_tokens, revoke_refresh_token


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenPair)
def login(data: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    return issue_token_pair(authenticate(db, data.email, data.password))


@router.post("/refresh", response_model=TokenPair)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    return refresh_tokens(db, data.refresh_token)


@router.post("/logout", response_model=Message, status_code=status.HTTP_200_OK)
def logout(data: LogoutRequest, db: Session = Depends(get_db)) -> Message:
    revoke_refresh_token(db, data.refresh_token)
    return Message(message="Logged out successfully")


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user

