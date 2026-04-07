"""Settings router — change password, profile update, system info."""

from __future__ import annotations

import platform
import sys
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import DATABASE_URL, SessionLocal, engine
from app.models.user_model import User
from app.utils.jwt_utils import (
    get_current_user_payload,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/settings", tags=["Settings"])

_STARTED_AT = datetime.utcnow()


# ── DB dependency ─────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


class ProfileUpdateRequest(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: str | None = None


class ProfileResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    unit_key: str | None
    is_active: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SystemStatusResponse(BaseModel):
    version: str
    python_version: str
    database: str
    uptime_seconds: float
    total_users: int
    total_tenants: int
    total_devices: int
    os_platform: str


# ── Change Password ──────────────────────────────────────────────────────────

@router.put("/change-password", summary="Change current user's password")
def change_password(
    body: ChangePasswordRequest,
    payload: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.hashed_password = hash_password(body.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


# ── Update Profile ───────────────────────────────────────────────────────────

@router.put("/profile", response_model=ProfileResponse, summary="Update profile")
def update_profile(
    body: ProfileUpdateRequest,
    payload: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.username is not None:
        existing = db.query(User).filter(User.username == body.username, User.id != user.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
        user.username = body.username

    if body.email is not None:
        existing = db.query(User).filter(User.email == body.email, User.id != user.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        user.email = body.email

    db.commit()
    db.refresh(user)
    return user


# ── Get Profile ──────────────────────────────────────────────────────────────

@router.get("/profile", response_model=ProfileResponse, summary="Get own profile")
def get_profile(
    payload: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── System Status (admin only) ───────────────────────────────────────────────

@router.get("/system", response_model=SystemStatusResponse, summary="System info (admin)")
def system_status(
    payload: dict = Depends(get_current_user_payload),
):
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    with engine.connect() as c:
        total_users = c.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
        total_tenants = c.execute(text("SELECT COUNT(*) FROM tenants")).scalar() or 0
        total_devices = c.execute(text("SELECT COUNT(*) FROM devices")).scalar() or 0

    db_type = "PostgreSQL" if "postgresql" in DATABASE_URL else "SQLite"
    uptime = (datetime.utcnow() - _STARTED_AT).total_seconds()

    return SystemStatusResponse(
        version="2.0.0",
        python_version=sys.version.split()[0],
        database=db_type,
        uptime_seconds=uptime,
        total_users=total_users,
        total_tenants=total_tenants,
        total_devices=total_devices,
        os_platform=platform.system(),
    )
