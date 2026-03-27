"""
Tests for tariff utilities in utils/helpers.py
"""
import pytest
from utils.helpers import (
    current_tariff,
    is_peak_hour,
    cheapest_hours,
    TARIFF_SCHEDULE,
)


class TestTariffSchedule:
    def test_all_hours_covered(self):
        for h in range(24):
            assert h in TARIFF_SCHEDULE

    def test_peak_hours_are_expensive(self):
        # Peak: 17:00–20:00
        for h in range(17, 21):
            assert TARIFF_SCHEDULE[h] == pytest.approx(0.28)

    def test_off_peak_hours_are_cheap(self):
        for h in list(range(0, 7)) + list(range(22, 24)):
            assert TARIFF_SCHEDULE[h] == pytest.approx(0.08)

    def test_standard_hours(self):
        for h in range(7, 17):
            assert TARIFF_SCHEDULE[h] == pytest.approx(0.13)


class TestCurrentTariff:
    def test_explicit_hour_peak(self):
        assert current_tariff(18) == pytest.approx(0.28)

    def test_explicit_hour_offpeak(self):
        assert current_tariff(3) == pytest.approx(0.08)

    def test_returns_float(self):
        assert isinstance(current_tariff(12), float)

    def test_no_arg_returns_something(self):
        result = current_tariff()
        assert result > 0


class TestIsPeakHour:
    def test_peak_hour_true(self):
        assert is_peak_hour(18) is True

    def test_offpeak_hour_false(self):
        assert is_peak_hour(3) is False

    def test_standard_hour_false(self):
        assert is_peak_hour(10) is False


class TestCheapestHours:
    def test_returns_n_hours(self):
        assert len(cheapest_hours(8)) == 8

    def test_returns_list_of_ints(self):
        for h in cheapest_hours(4):
            assert isinstance(h, int)
            assert 0 <= h <= 23

    def test_sorted_ascending(self):
        hours = cheapest_hours(6)
        assert hours == sorted(hours)

    def test_no_peak_hours_in_cheapest(self):
        """The 8 cheapest hours should not include peak (17-20) hours."""
        cheapest = cheapest_hours(8)
        for h in range(17, 21):
            assert h not in cheapest
