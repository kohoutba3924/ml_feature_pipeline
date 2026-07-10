import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import pandas as pd

from ml_feature_pipeline.ingestion import elevation

# ------------------------------------------------------------
# FIXTURES
# ------------------------------------------------------------


@pytest.fixture
def mock_settings(monkeypatch, tmp_path):
    """
    Patch settings so elevation ingestion writes to temp directories.
    """

    class DummySettings:
        RAW_DATA_DIR = tmp_path / "raw"
        EXTERNAL_DATA_DIR = tmp_path / "external"
        NORMALIZED_DATA_DIR = tmp_path / "normalized"
        USGS_ELEVATION_API_BASE_URL = "https://fake-epqs.test"

    monkeypatch.setattr(elevation, "settings", DummySettings())


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
    monkeypatch.setattr(elevation, "ingestion_state", dummy)
    return dummy


@pytest.fixture
def mock_session(monkeypatch):
    """
    Patch SESSION.get so no real HTTP calls occur.
    """
    mock = MagicMock()
    monkeypatch.setattr(elevation, "SESSION", mock)
    return mock


# ------------------------------------------------------------
# TESTS FOR _query_epqs()
# ------------------------------------------------------------


def test_query_epqs_success(mock_session, mock_settings):
    mock_session.get.return_value.json.return_value = {"value": 123.45}

    result = elevation._query_epqs(44.5, -88.0)

    assert result == 123.45
    mock_session.get.assert_called_once()


def test_query_epqs_missing_value(mock_session, mock_settings):
    mock_session.get.return_value.json.return_value = {"foo": "bar"}

    result = elevation._query_epqs(44.5, -88.0)

    assert result is None


def test_query_epqs_non_json(mock_session, mock_settings):
    mock_session.get.return_value.json.side_effect = ValueError("bad json")

    result = elevation._query_epqs(44.5, -88.0)

    assert result is None


def test_query_epqs_request_exception(mock_session, mock_settings):
    mock_session.get.side_effect = Exception("network error")

    result = elevation._query_epqs(44.5, -88.0)

    assert result is None


# ------------------------------------------------------------
# TESTS FOR _load_station_coordinates()
# ------------------------------------------------------------


def test_load_station_coordinates_happy_path(monkeypatch, mock_settings):
    df = pd.DataFrame(
        {
            "station": ["A", "B"],
            "latitude": [44.1, 44.2],
            "longitude": [-88.1, -88.2],
        }
    )

    with patch("pandas.read_parquet", return_value=df):
        coords = elevation._load_station_coordinates()

    assert coords == [
        ("A", 44.1, -88.1),
        ("B", 44.2, -88.2),
    ]


# ------------------------------------------------------------
# TESTS FOR _load_tract_coordinates()
# ------------------------------------------------------------


def test_load_tract_coordinates_happy_path(monkeypatch, mock_settings):
    df = pd.DataFrame(
        {
            "tract": ["55001010100", "55001010200"],
            "centroid_lat": [44.5, 44.6],
            "centroid_lon": [-88.0, -88.1],
        }
    )

    with patch("pandas.read_parquet", return_value=df):
        coords = elevation._load_tract_coordinates()

    assert coords == [
        ("55001010100", 44.5, -88.0),
        ("55001010200", 44.6, -88.1),
    ]


def test_load_tract_coordinates_missing_columns(monkeypatch, mock_settings):
    df = pd.DataFrame(
        {
            "tract": ["55001010100"],
            "centroid_lat": [44.5],
            # centroid_lon missing
        }
    )

    with patch("pandas.read_parquet", return_value=df):
        with pytest.raises(RuntimeError):
            elevation._load_tract_coordinates()


# ------------------------------------------------------------
# TESTS FOR WORKER FUNCTIONS
# ------------------------------------------------------------


def test_eqps_worker_station(monkeypatch):
    monkeypatch.setattr(elevation, "_query_epqs", lambda lat, lon: 111.0)

    result = elevation._eqps_worker_station("A", 44.5, -88.0)

    assert result == {
        "station": "A",
        "latitude": 44.5,
        "longitude": -88.0,
        "elevation_m": 111.0,
    }


def test_eqps_worker_tract(monkeypatch):
    monkeypatch.setattr(elevation, "_query_epqs", lambda lat, lon: 222.0)

    result = elevation._eqps_worker_tract("55001010100", 44.5, -88.0)

    assert result == {
        "tract": "55001010100",
        "centroid_lat": 44.5,
        "centroid_lon": -88.0,
        "elevation_m": 222.0,
    }


# ------------------------------------------------------------
# TESTS FOR ingest_station_elevation()
# ------------------------------------------------------------


def test_ingest_station_elevation_success(
    monkeypatch, mock_settings, mock_session, mock_ingestion_state, tmp_path
):
    monkeypatch.setattr(
        elevation,
        "_load_station_coordinates",
        lambda: [("A", 44.5, -88.0), ("B", 44.6, -88.1)],
    )

    monkeypatch.setattr(elevation, "_query_epqs", lambda lat, lon: 100.0)

    with patch("pandas.DataFrame.to_parquet") as mock_to_parquet:
        result = elevation.ingest_station_elevation()

    assert result["status"] == "success"
    assert result["count"] == 2
    assert "station_elevation.parquet" in result["path"]

    assert any(call[0] == "mark" for call in mock_ingestion_state.calls)
    assert any(call[0] == "update" for call in mock_ingestion_state.calls)


def test_ingest_station_elevation_skip(monkeypatch, mock_settings, tmp_path):
    output_path = tmp_path / "raw" / "elevation" / "station_elevation.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("exists")

    result = elevation.ingest_station_elevation()

    assert result["status"] == "skipped"


# ------------------------------------------------------------
# TESTS FOR ingest_tract_elevation()
# ------------------------------------------------------------


def test_ingest_tract_elevation_success(
    monkeypatch, mock_settings, mock_session, mock_ingestion_state, tmp_path
):
    monkeypatch.setattr(
        elevation,
        "_load_tract_coordinates",
        lambda: [("55001010100", 44.5, -88.0), ("55001010200", 44.6, -88.1)],
    )

    monkeypatch.setattr(elevation, "_query_epqs", lambda lat, lon: 150.0)

    with patch("pandas.DataFrame.to_parquet") as mock_to_parquet:
        result = elevation.ingest_tract_elevation()

    assert result["status"] == "success"
    assert result["count"] == 2
    assert "tract_elevation.parquet" in result["path"]

    assert any(call[0] == "mark" for call in mock_ingestion_state.calls)
    assert any(call[0] == "update" for call in mock_ingestion_state.calls)


def test_ingest_tract_elevation_skip(monkeypatch, mock_settings, tmp_path):
    output_path = tmp_path / "raw" / "elevation" / "tract_elevation.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("exists")

    result = elevation.ingest_tract_elevation()

    assert result["status"] == "skipped"
