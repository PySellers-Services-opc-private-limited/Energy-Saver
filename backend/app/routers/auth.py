"""
Auth router – login, register, and current-user endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user
from app.database import UserORM
from app.services.auth_service import authenticate_user, create_access_token, create_user, get_user

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    username: str  = Field(min_length=3, max_length=64)
    email:    str  = Field(min_length=5, max_length=128)
    password: str  = Field(min_length=8)


class UserResponse(BaseModel):
    id:       int
    username: str
    email:    str
    is_admin: bool

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/token", response_model=TokenResponse, summary="Login – get JWT")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    user = await authenticate_user(session, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user.username, {"admin": user.is_admin})
    return TokenResponse(access_token=token)


@router.post("/register", response_model=UserResponse, status_code=201, summary="Register new user")
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    existing = await get_user(session, body.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    user = await create_user(session, body.username, body.email, body.password)
    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse, summary="Get current user info")
async def me(current_user: UserORM = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
