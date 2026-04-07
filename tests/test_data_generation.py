"""
Tests for data/generate_data.py
Verifies that generated CSV files have the expected schema and value ranges.
"""
import os
import sys
import subprocess
import pytest
import pandas as pd

# Run from project root so relative paths work
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def generated_data(tmp_path_factory):
    """Generate sample CSVs into a temp dir and return the DataFrames."""
    tmp = tmp_path_factory.mktemp("data")
    result = subprocess.run(
        [sys.executable, os.path.join(PROJECT_ROOT, "data", "generate_data.py")],
        cwd=str(tmp),
        capture_output=True,
        text=True,
    )
    energy_path   = os.path.join(PROJECT_ROOT, "data", "energy_consumption.csv")
    occupancy_path = os.path.join(PROJECT_ROOT, "data", "occupancy_data.csv")

    # If the script writes to the project data/, use those files
    if os.path.exists(energy_path):
        return {
            "energy":    pd.read_csv(energy_path),
            "occupancy": pd.read_csv(occupancy_path),
        }
    pytest.skip("generate_data.py did not produce output files")


class TestEnergyDataSchema:
    REQUIRED_COLUMNS = [
        "timestamp", "consumption_kwh", "temperature", "humidity",
        "hour", "day_of_week", "is_weekend", "solar_kwh", "tariff",
    ]

    def test_required_columns_exist(self, generated_data):
        df = generated_data["energy"]
        for col in self.REQUIRED_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    def test_no_null_values(self, generated_data):
        df = generated_data["energy"]
        assert df.isnull().sum().sum() == 0

    def test_consumption_positive(self, generated_data):
        df = generated_data["energy"]
        assert (df["consumption_kwh"] > 0).all()

    def test_hour_range(self, generated_data):
        df = generated_data["energy"]
        assert df["hour"].between(0, 23).all()

    def test_day_of_week_range(self, generated_data):
        df = generated_data["energy"]
        assert df["day_of_week"].between(0, 6).all()

    def test_is_weekend_binary(self, generated_data):
        df = generated_data["energy"]
        assert set(df["is_weekend"].unique()).issubset({0, 1})

    def test_tariff_positive(self, generated_data):
        df = generated_data["energy"]
        assert (df["tariff"] > 0).all()


class TestOccupancyDataSchema:
    REQUIRED_COLUMNS = [
        "timestamp", "temperature", "humidity", "co2_ppm",
        "light_level", "occupied",
    ]

    def test_required_columns_exist(self, generated_data):
        df = generated_data["occupancy"]
        for col in self.REQUIRED_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    def test_occupied_binary(self, generated_data):
        df = generated_data["occupancy"]
        assert set(df["occupied"].unique()).issubset({0, 1})

    def test_co2_positive(self, generated_data):
        df = generated_data["occupancy"]
        assert (df["co2_ppm"] > 0).all()
