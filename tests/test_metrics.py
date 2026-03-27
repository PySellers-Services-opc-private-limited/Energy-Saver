"""
Tests for PipelineMetrics in utils/helpers.py
"""
import time
import pytest
from utils.helpers import PipelineMetrics


class TestPipelineMetrics:
    def setup_method(self):
        self.m = PipelineMetrics()

    def test_inc_basic(self):
        self.m.inc("messages")
        self.m.inc("messages")
        assert self.m.summary()["counters"]["messages"] == 2

    def test_inc_with_amount(self):
        self.m.inc("bytes", 1024)
        assert self.m.summary()["counters"]["bytes"] == 1024

    def test_set_gauge(self):
        self.m.set("cpu", 0.75)
        assert self.m.summary()["gauges"]["cpu"] == pytest.approx(0.75)

    def test_observe_creates_histogram(self):
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            self.m.observe("latency_ms", v)
        s = self.m.summary()
        assert "latency_ms" in s["histograms"]
        h = s["histograms"]["latency_ms"]
        assert h["count"] == 5
        assert h["mean"] == pytest.approx(3.0)

    def test_histogram_capped_at_1000(self):
        for i in range(1500):
            self.m.observe("test", float(i))
        # Should be capped at 500 after overflow
        s = self.m.summary()
        assert s["histograms"]["test"]["count"] <= 1000

    def test_uptime_positive(self):
        s = self.m.summary()
        assert s["uptime_s"] >= 0

    def test_summary_has_all_keys(self):
        s = self.m.summary()
        assert "uptime_s" in s
        assert "counters" in s
        assert "gauges" in s
        assert "histograms" in s
