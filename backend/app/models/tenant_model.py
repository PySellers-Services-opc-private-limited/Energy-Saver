from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(200), nullable=False)
    email = Column(String(150), nullable=False, unique=True, index=True)
    phone = Column(String(20), nullable=True)

    # PRIMARY identifier — used as FK in devices, energy_logs, alerts
    unit_key = Column(String(50), unique=True, nullable=False, index=True)

    image = Column(Text, nullable=True)

    # Tenant classification: home | commercial | industrial
    tenant_type = Column(String(50), nullable=True)

    # Subscription: basic | pro | enterprise
    subscription_plan = Column(String(50), nullable=True)
    plan_start_date = Column(Date, nullable=True)
    plan_end_date = Column(Date, nullable=True)

    timezone = Column(String(100), nullable=False, default="UTC")
    currency = Column(String(10), nullable=False, default="INR")

    is_active = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(Text, nullable=True)  # JSON string for custom attrs

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    devices = relationship(
        "Device", back_populates="tenant", cascade="all, delete-orphan"
    )
    energy_logs = relationship(
        "EnergyLog", back_populates="tenant", cascade="all, delete-orphan"
    )
    alerts = relationship(
        "TenantAlert", back_populates="tenant", cascade="all, delete-orphan"
    )
    buildings = relationship(
        "Building", back_populates="tenant", cascade="all, delete-orphan"
    )
    subscriptions = relationship(
        "Subscription", back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant(name={self.name!r}, unit_key={self.unit_key!r})>"