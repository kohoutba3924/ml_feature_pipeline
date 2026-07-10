import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import pandas as pd

from ml_feature_pipeline.ingestion.lcdv2 import stations as lcdv2_stations

# ------------------------------------------------------------
# FIXTURES
# ------------------------------------------------------------


@pytest.fixture
def mock_settings(monkeypatch, tmp_path):
    """
    Patch settings so that:
    - EXTERNAL_DATA_DIR points to a temp directory
    - API base URL and endpoints are predictable
    """

    class DummySettings:
        EXTERNAL_DATA_DIR = tmp_path / "external"
        LCDV2_API_BASE_URL = "https://fake-noaa.test"
        LCDV2_STATIONS_ENDPOINT = "/stations"
        LCDV2_DATASET_ID = "LCDV2"
        LCDV2_LOCATION_FILTER = "FIPS:55"  # Wisconsin
        NOAA_API_KEY = "fake-key"

    monkeypatch.setattr(lcdv2_stations, "settings", DummySettings())


@pytest.fixture
def mock_ingestion_state(monkeypatch):
    """
    Replace ingestion_state with a dummy object that records calls.
    """

    class DummyState:
        def __init__(self):
            self.calls = []

        def update(self, *args, **kwargs):
            self.calls.append(("update", args, kwargs))

        def mark_ingested_now(self, *args, **kwargs):
            self.calls.append(("mark", args, kwargs))

    dummy = DummyState()
    monkeypatch.setattr(lcdv2_stations, "ingestion_state", dummy)
    return dummy


@pytest.fixture
def mock_session(monkeypatch):
    """
    Patch SESSION.get so no real HTTP calls occur.
    """
    mock = MagicMock()
    monkeypatch.setattr(lcdv2_stations, "SESSION", mock)
    return mock


# ------------------------------------------------------------
# TESTS FOR fetch_stations()
# ------------------------------------------------------------


def test_fetch_stations_single_page(mock_session, mock_settings):
    """
    Ensure fetch_stations returns results when only one page is needed.
    """
    mock_session.get.return_value.status_code = 200
    mock_session.get.return_value.json.return_value = {
        "results": [{"id": "WBAN:04803"}, {"id": "WBAN:14839"}],
        "metadata": {"resultset": {"count": 2, "limit": 1000, "offset": 1}},
    }

    results = lcdv2_stations.fetch_stations()

    assert len(results) == 2
    assert results[0]["id"] == "WBAN:04803"
    assert mock_session.get.call_count == 1


def test_fetch_stations_multi_page(mock_session, mock_settings):
    """
    Ensure pagination works across multiple pages.
    """

    # First page
    first_page = MagicMock()
    first_page.status_code = 200
    first_page.json.return_value = {
        "results": [{"id": "WBAN:04803"}],
        "metadata": {"resultset": {"count": 2, "limit": 1, "offset": 1}},
    }

    # Second page
    second_page = MagicMock()
    second_page.status_code = 200
    second_page.json.return_value = {
        "results": [{"id": "WBAN:14839"}],
        "metadata": {"resultset": {"count": 2, "limit": 1, "offset": 2}},
    }

    mock_session.get.side_effect = [first_page, second_page]

    results = lcdv2_stations.fetch_stations()

    assert len(results) == 2
    assert results[1]["id"] == "WBAN:14839"
    assert mock_session.get.call_count == 2


def test_fetch_stations_no_results(mock_session, mock_settings):
    """
    Ensure empty results are handled gracefully.
    """
    mock_session.get.return_value.status_code = 200
    mock_session.get.return_value.json.return_value = {
        "results": [],
        "metadata": {"resultset": {"count": 0, "limit": 1000, "offset": 1}},
    }

    results = lcdv2_stations.fetch_stations()
    assert results == []


# ------------------------------------------------------------
# TESTS FOR normalize_station_metadata()
# ------------------------------------------------------------


def test_normalize_station_metadata_basic():
    """
    Ensure columns are selected and renamed correctly.
    """
    raw = [
        {
            "id": "WBAN:04803",
            "name": "Test Station",
            "latitude": 44.5,
            "longitude": -88.0,
            "elevation": 200.0,
            "datacoverage": 0.9,
            "mindate": "1950-01-01",
            "maxdate": "2024-01-01",
            "extra_column": "ignore_me",
        }
    ]

    df = lcdv2_stations.normalize_station_metadata(raw)

    assert list(df.columns) == [
        "station",
        "name",
        "latitude",
        "longitude",
        "elevation",
        "data_coverage",
        "min_date",
        "max_date",
    ]

    assert df.loc[0, "station"] == "WBAN:04803"
    assert df.loc[0, "data_coverage"] == 0.9


def test_normalize_station_metadata_missing_optional_column():
    """
    Elevation may be missing — ensure function does not crash.
    """
    raw = [
        {
            "id": "WBAN:04803",
            "name": "Test Station",
            "latitude": 44.5,
            "longitude": -88.0,
            "datacoverage": 0.9,
            "mindate": "1950-01-01",
            "maxdate": "2024-01-01",
        }
    ]

    df = lcdv2_stations.normalize_station_metadata(raw)

    # elevation should simply be absent
    assert "elevation" not in df.columns
    assert "station" in df.columns


# ------------------------------------------------------------
# TESTS FOR save_station_metadata()
# ------------------------------------------------------------


def test_save_station_metadata(monkeypatch, tmp_path, mock_settings):
    """
    Ensure DataFrame is saved to the correct path.
    """
    df = MagicMock()

    # Patch DataFrame.to_parquet so no real file is written
    with patch.object(df, "to_parquet") as mock_to_parquet:
        output_path = lcdv2_stations.save_station_metadata(df)

    expected_path = tmp_path / "external" / "lcdv2_stations.parquet"
    assert output_path == expected_path
    mock_to_parquet.assert_called_once_with(expected_path, index=False)


# ------------------------------------------------------------
# TESTS FOR ingest_station_metadata()
# ------------------------------------------------------------


def test_ingest_station_metadata(
    monkeypatch, mock_settings, mock_session, mock_ingestion_state, tmp_path
):
    """
    Full ingestion pipeline with all components mocked.
    """

    # Mock fetch_stations
    monkeypatch.setattr(
        lcdv2_stations,
        "fetch_stations",
        lambda: [{"id": "WBAN:04803", "datacoverage": 0.9}],
    )

    # Mock normalize_station_metadata
    fake_df = pd.DataFrame({"station": ["WBAN:04803"]})
    monkeypatch.setattr(
        lcdv2_stations,
        "normalize_station_metadata",
        lambda raw: fake_df,
    )

    # Mock save_station_metadata
    fake_path = tmp_path / "external" / "lcdv2_stations.parquet"
    monkeypatch.setattr(
        lcdv2_stations,
        "save_station_metadata",
        lambda df: fake_path,
    )

    result = lcdv2_stations.ingest_station_metadata()

    assert result == fake_path

    # ingestion_state should have been updated
    assert any(call[0] == "mark" for call in mock_ingestion_state.calls)
    assert any(call[0] == "update" for call in mock_ingestion_state.calls)
