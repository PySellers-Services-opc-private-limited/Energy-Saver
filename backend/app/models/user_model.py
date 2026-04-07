"""User model — supports Admin and Tenant roles."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)

    # "admin" or "tenant"
    role = Column(String(20), default="tenant", nullable=False)

    # For tenant users — links to tenants.unit_key
    unit_key = Column(String(50), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<User(username={self.username!r}, role={self.role!r})>"
