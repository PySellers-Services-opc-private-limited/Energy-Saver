"""
Tests for utils/helpers.py
"""
import numpy as np
import pytest
from utils.helpers import (
    reading_to_vector,
    normalize_window,
    estimate_annual_savings,
    FEATURE_NAMES,
    FEATURE_DEFAULTS,
    N_FEATURES,
)


class TestReadingToVector:
    def test_output_length(self):
        r = {"consumption_kwh": 3.5, "temperature": 22.0}
        vec = reading_to_vector(r)
        assert len(vec) == N_FEATURES

    def test_missing_fields_use_defaults(self):
        vec = reading_to_vector({})
        for i, name in enumerate(FEATURE_NAMES):
            assert vec[i] == float(FEATURE_DEFAULTS[name])

    def test_custom_values_passed_through(self):
        r = {"consumption_kwh": 5.5, "temperature": 30.0, "humidity": 80.0}
        vec = reading_to_vector(r)
        assert vec[FEATURE_NAMES.index("consumption_kwh")] == pytest.approx(5.5)
        assert vec[FEATURE_NAMES.index("temperature")] == pytest.approx(30.0)
        assert vec[FEATURE_NAMES.index("humidity")] == pytest.approx(80.0)

    def test_all_floats(self):
        vec = reading_to_vector({"consumption_kwh": 2})
        assert all(isinstance(v, float) for v in vec)


class TestNormalizeWindow:
    def setup_method(self):
        np.random.seed(42)
        self.window = np.random.rand(48, N_FEATURES)

    def test_output_shape_preserved(self):
        norm, mins, maxs = normalize_window(self.window)
        assert norm.shape == self.window.shape

    def test_values_in_zero_one(self):
        norm, _, _ = normalize_window(self.window)
        assert norm.min() >= -1e-9
        assert norm.max() <= 1.0 + 1e-9

    def test_mins_maxs_correct_length(self):
        _, mins, maxs = normalize_window(self.window)
        assert len(mins) == N_FEATURES
        assert len(maxs) == N_FEATURES

    def test_constant_column_handled(self):
        """Constant column should not produce NaN/inf."""
        w = self.window.copy()
        w[:, 0] = 3.14   # constant
        norm, _, _ = normalize_window(w)
        assert not np.any(np.isnan(norm))
        assert not np.any(np.isinf(norm))


class TestEstimateAnnualSavings:
    def test_keys_present(self):
        result = estimate_annual_savings(baseline_kwh_per_day=30.0, tariff_per_kwh=0.15)
        for key in ("kwh_saved_per_day", "kwh_saved_per_year", "cost_saved_per_year",
                    "co2_saved_kg_per_year", "breakdown"):
            assert key in result

    def test_positive_savings(self):
        result = estimate_annual_savings(baseline_kwh_per_day=30.0, tariff_per_kwh=0.15)
        assert result["kwh_saved_per_day"] > 0
        assert result["cost_saved_per_year"] > 0

    def test_zero_tariff(self):
        result = estimate_annual_savings(baseline_kwh_per_day=30.0, tariff_per_kwh=0.0)
        assert result["cost_saved_per_year"] == pytest.approx(0.0)

    def test_breakdown_sums_to_total(self):
        result = estimate_annual_savings(baseline_kwh_per_day=30.0, tariff_per_kwh=0.15)
        total_breakdown = sum(result["breakdown"].values())
        assert total_breakdown == pytest.approx(result["kwh_saved_per_year"], rel=1e-3)

    def test_co2_positive(self):
        result = estimate_annual_savings(baseline_kwh_per_day=50.0, tariff_per_kwh=0.12)
        assert result["co2_saved_kg_per_year"] > 0
