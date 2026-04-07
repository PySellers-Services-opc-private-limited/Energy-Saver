"""Device model — one physical meter/BACnet device per apartment unit."""

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)

    # Temporary operational identifier (may change on firmware swap)
    device_id = Column(String(100), nullable=True)

    # Permanent key — FK → tenants.unit_key
    unit_key = Column(
        String(50),
        ForeignKey("tenants.unit_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # BACnet object number derived from unit_key
    bacnet_object_no = Column(Integer, nullable=True)

    tenant = relationship("Tenant", back_populates="devices")

    def __repr__(self) -> str:
        return f"<Device(unit_key={self.unit_key!r}, device_id={self.device_id!r})>"
