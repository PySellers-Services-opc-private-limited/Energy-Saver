"""
Auth service – password hashing, JWT creation and verification.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import UserORM

logger = logging.getLogger("energy_saver_ai.auth")

# ── Secrets (override via env vars in production) ─────────────────────────────
SECRET_KEY       = os.getenv("JWT_SECRET_KEY", "energy-saver-ai-change-me-in-prod-32chars!")
ALGORITHM        = "HS256"
ACCESS_TOKEN_TTL = int(os.getenv("JWT_ACCESS_TTL_MINUTES", "60"))


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(subject: str, extra: dict | None = None) -> str:
    expire  = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_TTL)
    payload = {"sub": subject, "exp": expire, **(extra or {})}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises JWTError if invalid/expired."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── DB helpers ────────────────────────────────────────────────────────────────

async def get_user(session: AsyncSession, username: str) -> UserORM | None:
    result = await session.execute(
        select(UserORM).where(UserORM.username == username)
    )
    return result.scalar_one_or_none()


async def authenticate_user(session: AsyncSession, username: str, password: str) -> UserORM | None:
    user = await get_user(session, username)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user


async def create_user(
    session: AsyncSession,
    username: str,
    email: str,
    password: str,
    is_admin: bool = False,
) -> UserORM:
    user = UserORM(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        is_admin=is_admin,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info(f"Created user: {username}")
    return user


async def ensure_default_admin(session: AsyncSession) -> None:
    """Create a default admin user if no users exist (first-run)."""
    default_user = await get_user(session, "admin")
    if default_user is None:
        await create_user(
            session,
            username="admin",
            email="admin@energy-saver.ai",
            password=os.getenv("DEFAULT_ADMIN_PASSWORD", "Admin@1234!"),
            is_admin=True,
        )
        logger.info("Default admin user created (change the password!)")
