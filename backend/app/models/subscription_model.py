"""Subscription model — tracks plan details per tenant."""

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    plan = Column(String(50), nullable=False)  # basic | pro | enterprise
    max_devices = Column(Integer, nullable=False, default=5)
    max_users = Column(Integer, nullable=False, default=2)
    max_buildings = Column(Integer, nullable=False, default=1)
    price_per_month = Column(Numeric(10, 2), nullable=False, default=499)
    billing_cycle = Column(String(20), nullable=False, default="monthly")  # monthly | annual
    status = Column(String(20), nullable=False, default="active")  # active | suspended | expired
    starts_at = Column(Date, nullable=False)
    ends_at = Column(Date, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<Subscription(plan={self.plan!r}, tenant_id={self.tenant_id})>"
