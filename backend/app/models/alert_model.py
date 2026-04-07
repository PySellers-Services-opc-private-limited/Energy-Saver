"""TenantAlert model — anomaly / notification alerts per apartment unit."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class TenantAlert(Base):
    __tablename__ = "tenant_alerts"

    id = Column(Integer, primary_key=True, index=True)

    unit_key = Column(
        String(50),
        ForeignKey("tenants.unit_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    message = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    tenant = relationship("Tenant", back_populates="alerts")

    def __repr__(self) -> str:
        return f"<TenantAlert(unit_key={self.unit_key!r}, ts={self.created_at})>"
