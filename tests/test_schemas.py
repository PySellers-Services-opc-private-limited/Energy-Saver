"""
Tests for config/schemas.py
"""
import time
import pytest
from config.schemas import (
    SensorReadingSchema,
    HVACCommandSchema,
    AlertSchema,
    ValidationError,
    HVAC_MODES,
    ALERT_LEVELS,
)


# ─────────────────────────────────────────────────────────────
# SensorReadingSchema
# ─────────────────────────────────────────────────────────────

class TestSensorReadingSchema:
    def _valid(self, **overrides) -> dict:
        base = {
            "device_id": "dev-001",
            "timestamp": time.time(),
            "consumption_kwh": 2.5,
            "temperature": 21.0,
            "humidity": 55.0,
        }
        base.update(overrides)
        return base

    def test_valid_minimal(self):
        r = SensorReadingSchema.validate(self._valid())
        assert r.device_id == "dev-001"
        assert r.consumption_kwh == pytest.approx(2.5)

    def test_defaults_applied(self):
        r = SensorReadingSchema.validate(self._valid())
        assert r.occupancy == pytest.approx(0.0)
        assert r.solar_kwh == pytest.approx(0.0)
        assert r.tariff == pytest.approx(0.13)

    def test_extra_keys_ignored(self):
        data = self._valid()
        data["unknown_field"] = "should_be_ignored"
        r = SensorReadingSchema.validate(data)
        assert not hasattr(r, "unknown_field")

    def test_empty_device_id_raises(self):
        with pytest.raises(ValidationError, match="device_id"):
            SensorReadingSchema.validate(self._valid(device_id=""))

    def test_invalid_timestamp_raises(self):
        with pytest.raises(ValidationError, match="timestamp"):
            SensorReadingSchema.validate(self._valid(timestamp=-1.0))

    def test_consumption_out_of_range_raises(self):
        with pytest.raises(ValidationError, match="consumption_kwh"):
            SensorReadingSchema.validate(self._valid(consumption_kwh=200.0))

    def test_humidity_out_of_range_raises(self):
        with pytest.raises(ValidationError, match="humidity"):
            SensorReadingSchema.validate(self._valid(humidity=110.0))

    def test_to_dict_keys(self):
        r = SensorReadingSchema.validate(self._valid())
        d = r.to_dict()
        assert "device_id" in d
        assert "consumption_kwh" in d
        assert "_BOUNDS" not in d

    def test_boundary_values_accepted(self):
        r = SensorReadingSchema.validate(self._valid(consumption_kwh=0.0))
        assert r.consumption_kwh == pytest.approx(0.0)
        r2 = SensorReadingSchema.validate(self._valid(consumption_kwh=100.0))
        assert r2.consumption_kwh == pytest.approx(100.0)


# ─────────────────────────────────────────────────────────────
# HVACCommandSchema
# ─────────────────────────────────────────────────────────────

class TestHVACCommandSchema:
    def test_valid_command(self):
        cmd = HVACCommandSchema(
            device_id="hvac-01",
            timestamp=time.time(),
            mode="COMFORT",
            setpoint_c=22.0,
        )
        assert cmd.mode == "COMFORT"

    def test_all_valid_modes(self):
        for mode in HVAC_MODES:
            cmd = HVACCommandSchema(
                device_id="hvac-01",
                timestamp=time.time(),
                mode=mode,
                setpoint_c=22.0,
            )
            assert cmd.mode == mode

    def test_invalid_mode_raises(self):
        with pytest.raises(ValidationError, match="mode"):
            HVACCommandSchema(
                device_id="hvac-01",
                timestamp=time.time(),
                mode="BLAST",
                setpoint_c=22.0,
            )

    def test_setpoint_out_of_range_raises(self):
        with pytest.raises(ValidationError, match="setpoint_c"):
            HVACCommandSchema(
                device_id="hvac-01",
                timestamp=time.time(),
                mode="COMFORT",
                setpoint_c=50.0,
            )

    def test_to_dict(self):
        cmd = HVACCommandSchema(
            device_id="hvac-01",
            timestamp=time.time(),
            mode="ECO",
            setpoint_c=18.0,
            reason="off-peak",
        )
        d = cmd.to_dict()
        assert d["mode"] == "ECO"
        assert d["reason"] == "off-peak"


# ─────────────────────────────────────────────────────────────
# AlertSchema
# ─────────────────────────────────────────────────────────────

class TestAlertSchema:
    def test_valid_alert(self):
        a = AlertSchema(
            device_id="dev-001",
            timestamp=time.time(),
            level="WARN",
            anomaly_score=0.72,
            message="High consumption detected",
        )
        assert a.level == "WARN"

    def test_all_valid_levels(self):
        for level in ALERT_LEVELS:
            a = AlertSchema(
                device_id="dev-001",
                timestamp=time.time(),
                level=level,
                anomaly_score=0.5,
                message="test",
            )
            assert a.level == level

    def test_invalid_level_raises(self):
        with pytest.raises(ValidationError, match="level"):
            AlertSchema(
                device_id="dev-001",
                timestamp=time.time(),
                level="SEVERE",
                anomaly_score=0.9,
                message="test",
            )

    def test_anomaly_score_out_of_range_raises(self):
        with pytest.raises(ValidationError, match="anomaly_score"):
            AlertSchema(
                device_id="dev-001",
                timestamp=time.time(),
                level="WARN",
                anomaly_score=1.5,
                message="test",
            )
