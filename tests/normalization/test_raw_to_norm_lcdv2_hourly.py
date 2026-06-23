import pytest
import polars as pl
from pathlib import Path
from datetime import datetime

from comfort_index_pipeline.normalization import raw_to_norm_lcdv2_hourly as norm

# ------------------------------------------------------------
# FIXTURES
# ------------------------------------------------------------


@pytest.fixture
def mock_settings(monkeypatch, tmp_path):
    """
    Patch settings so normalization reads/writes to temp directories.
    """

    class DummySettings:
        RAW_DATA_DIR = tmp_path / "raw"
        NORMALIZED_DATA_DIR = tmp_path / "normalized"

    monkeypatch.setattr(norm, "settings", DummySettings())


@pytest.fixture
def mock_normalization_state(monkeypatch):
    """
    Replace normalization_state with a dummy object that records calls.
    """

    class DummyState:
        def __init__(self):
            self.calls = []
            self.store = {}

        def update(self, dataset, key, value):
            self.calls.append(("update", dataset, key, value))
            self.store.setdefault(dataset, {})[key] = value

        def get(self, dataset, key):
            return self.store.get(dataset, {}).get(key)

    dummy = DummyState()
    monkeypatch.setattr(norm, "normalization_state", dummy)
    return dummy


@pytest.fixture
def sample_csv(tmp_path):
    """
    Create a minimal LCDV2 hourly CSV for testing.
    """
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "DATE,STATION,"
        "HourlyDryBulbTemperature,HourlyWetBulbTemperature,"
        "HourlyDewPointTemperature,HourlyRelativeHumidity,"
        "HourlyWindSpeed,HourlyWindDirection,HourlyWindGustSpeed,"
        "HourlyPrecipitation,HourlyVisibility,"
        "HourlyStationPressure,HourlyAltimeterSetting\n"
        "2025-01-01T00:00:00,72662604864,"
        "32,30,28,80,"
        "5,180,10,"
        "0.0,10.0,"
        "1012,29.92\n"
        "2025-01-01T01:00:00,72662604864,"
        "9999,9999,9999,99,"
        "999,999,999,"
        "9999,9999,"
        "9999,9999\n"
    )
    return csv_path


# ------------------------------------------------------------
# TEST: File-level normalization
# ------------------------------------------------------------


def test_normalize_file(sample_csv):
    df = norm.normalize_lcdv2_hourly_file(sample_csv)

    # Two rows
    assert df.height == 2

    # Station normalized
    assert df["station"][0] == "WBAN:04864"

    # Timestamp parsed
    assert isinstance(df["timestamp"][0], datetime)

    # Sentinel values become None
    assert df["dry_bulb_temp"][1] is None
    assert df["wind_speed"][1] is None
    assert df["precipitation"][1] is None

    # Valid row preserved
    assert df["dry_bulb_temp"][0] == 32.0


# ------------------------------------------------------------
# TEST: Parquet writing + directory structure
# ------------------------------------------------------------


def test_run_normalization_writes_parquet(
    mock_settings, mock_normalization_state, tmp_path, sample_csv
):
    # Create raw directory structure
    raw_dir = tmp_path / "raw" / "lcdv2" / "daily" / "2025"
    raw_dir.mkdir(parents=True)
    sample_csv.rename(raw_dir / "72662604864-2025.csv")

    # Run normalization
    norm.run_lcdv2_hourly_normalization([2025])

    # Parquet file exists
    expected = (
        tmp_path
        / "normalized"
        / "lcdv2"
        / "station_id=WBAN_04864"
        / "year=2025"
        / "part.parquet"
    )
    assert expected.exists()

    # State updated
    calls = mock_normalization_state.calls
    assert any(call[0] == "update" and call[2] == "years_normalized" for call in calls)


# ------------------------------------------------------------
# TEST: State merging behavior
# ------------------------------------------------------------


def test_state_merges_years(
    mock_settings, mock_normalization_state, tmp_path, sample_csv
):
    # Pretend 2024 already normalized
    mock_normalization_state.store = {"lcdv2_hourly": {"years_normalized": [2024]}}

    # Create raw directory structure
    raw_dir = tmp_path / "raw" / "lcdv2" / "daily" / "2025"
    raw_dir.mkdir(parents=True)
    sample_csv.rename(raw_dir / "72662604864-2025.csv")

    # Run normalization for 2025
    norm.run_lcdv2_hourly_normalization([2025])

    # Years merged
    updated_years = mock_normalization_state.store["lcdv2_hourly"]["years_normalized"]
    assert updated_years == [2024, 2025]
