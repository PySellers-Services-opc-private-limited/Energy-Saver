"""DailyForecastVsActual — one row per tenant per device per day."""

from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


class DailyForecastVsActual(Base):
    __tablename__ = "daily_forecast_vs_actual"

    id = Column(Integer, primary_key=True, index=True)

    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_key = Column(String(50), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    # Consumption
    forecast_kwh = Column(Float, nullable=True)
    actual_kwh = Column(Float, nullable=True)
    delta_kwh = Column(Float, nullable=True)
    delta_pct = Column(Float, nullable=True)

    # Bill
    forecast_bill = Column(Float, nullable=True)
    actual_bill = Column(Float, nullable=True)

    # Solar
    forecast_solar_kwh = Column(Float, nullable=True)
    actual_solar_kwh = Column(Float, nullable=True)

    # Peak demand
    forecast_peak_kw = Column(Float, nullable=True)
    actual_peak_kw = Column(Float, nullable=True)

    # Anomalies
    anomaly_count = Column(Integer, default=0)

    # Model accuracy
    forecast_accuracy_pct = Column(Float, nullable=True)
    mae = Column(Float, nullable=True)
    mape = Column(Float, nullable=True)

    # RAG status: green | amber | red
    rag_status = Column(String(10), default="green")

    computed_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    tenant = relationship("Tenant")

    def __repr__(self) -> str:
        return (
            f"<DailyForecastVsActual(tenant_id={self.tenant_id}, "
            f"date={self.date}, rag={self.rag_status})>"
        )
