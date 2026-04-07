"""EnergyLog model — one row per meter reading per apartment unit."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class EnergyLog(Base):
    __tablename__ = "energy_logs"

    id = Column(Integer, primary_key=True, index=True)

    unit_key = Column(
        String(50),
        ForeignKey("tenants.unit_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    voltage = Column(Float, nullable=True)        # Volts
    current = Column(Float, nullable=True)        # Amps
    power = Column(Float, nullable=True)          # kW
    consumption = Column(Float, nullable=False)   # kWh

    tenant = relationship("Tenant", back_populates="energy_logs")

    def __repr__(self) -> str:
        return (
            f"<EnergyLog(unit_key={self.unit_key!r}, "
            f"consumption={self.consumption} kWh, ts={self.timestamp})>"
        )
