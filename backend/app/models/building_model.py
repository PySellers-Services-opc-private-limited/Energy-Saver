"""Building model — one tenant can have many buildings."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Building(Base):
    __tablename__ = "buildings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(200), nullable=False)
    address = Column(Text, nullable=True)
    area_sqm = Column(Numeric(10, 2), nullable=True)
    floor_count = Column(Integer, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="buildings")

    def __repr__(self) -> str:
        return f"<Building(name={self.name!r}, tenant_id={self.tenant_id})>"
