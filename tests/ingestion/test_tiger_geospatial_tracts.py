import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from ml_feature_pipeline.ingestion import tiger_geospatial_tracts as tiger

# ------------------------------------------------------------
# FIXTURES
# ------------------------------------------------------------


@pytest.fixture
def mock_settings(monkeypatch, tmp_path):
    """
    Patch settings so TIGER ingestion writes to temp directories.
    """

    class DummySettings:
        RAW_DATA_DIR = tmp_path / "raw"
        TIGER_TRACT_BASE_URL = "https://fake-tiger.test/{year}"
        TIGER_STATE_FIPS = "55"
        TIGER_TRACT_YEAR = 2024

    monkeypatch.setattr(tiger, "settings", DummySettings())


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
    monkeypatch.setattr(tiger, "ingestion_state", dummy)
    return dummy


@pytest.fixture
def mock_session(monkeypatch):
    """
    Patch SESSION.get so no real HTTP calls occur.
    """
    mock = MagicMock()
    monkeypatch.setattr(tiger, "SESSION", mock)
    return mock


# ------------------------------------------------------------
# TEST A — build_tiger_geospatial_url()
# ------------------------------------------------------------


def test_build_tiger_geospatial_url(mock_settings):
    url, filename = tiger.build_tiger_geospatial_url(2024)

    assert filename == "tl_2024_55_tract.zip"
    assert url == "https://fake-tiger.test/2024/tl_2024_55_tract.zip"


# ------------------------------------------------------------
# TEST B & C — download_tiger_geospatial_zip()
# ------------------------------------------------------------


def test_download_tiger_geospatial_zip_success(mock_session, tmp_path):
    mock_session.get.return_value.status_code = 200
    mock_session.get.return_value.content = b"fakezip"

    dest = tmp_path / "file.zip"
    tiger.download_tiger_geospatial_zip("https://fake-url", dest)

    assert dest.read_bytes() == b"fakezip"
    mock_session.get.assert_called_once()


def test_download_tiger_geospatial_zip_failure(mock_session, tmp_path):
    mock_session.get.side_effect = Exception("network error")

    with pytest.raises(Exception):
        tiger.download_tiger_geospatial_zip("https://fake-url", tmp_path / "file.zip")


# ------------------------------------------------------------
# Test for extract_tiger_geospatial_zip()
# ------------------------------------------------------------


def test_extract_tiger_geospatial_zip(monkeypatch, tmp_path):
    mock_zip = MagicMock()
    mock_zip.__enter__.return_value = mock_zip

    # Patch ZipFile constructor to return our mock
    with patch("zipfile.ZipFile", return_value=mock_zip):
        tiger.extract_tiger_geospatial_zip(tmp_path / "fake.zip", tmp_path / "extract")

    mock_zip.extractall.assert_called_once_with(tmp_path / "extract")


# ------------------------------------------------------------
# Test for ingest_tiger_geospatial_tracts() skip branch
# ------------------------------------------------------------


def test_ingest_tiger_geospatial_tracts_skip(monkeypatch, mock_settings, tmp_path):
    year = 2024
    output_dir = tmp_path / "raw" / "tiger_geospatial_tracts" / str(year)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create the .shp file to trigger skip
    shp_path = output_dir / f"tl_{year}_55_tract.shp"
    shp_path.write_text("exists")

    result = tiger.ingest_tiger_geospatial_tracts()

    assert result["status"] == "skipped"
    assert result["reason"] == "already_ingested"


# ------------------------------------------------------------
# Test for ingest_tiger_geospatial_tracts() success path
# ------------------------------------------------------------


def test_ingest_tiger_geospatial_tracts_success(
    monkeypatch, mock_settings, mock_ingestion_state, tmp_path
):
    year = 2024
    output_dir = tmp_path / "raw" / "tiger_geospatial_tracts" / str(year)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Patch URL builder
    monkeypatch.setattr(
        tiger,
        "build_tiger_geospatial_url",
        lambda y: ("https://fake-url", "tl_2024_55_tract.zip"),
    )

    # Patch download + extract to no-op
    monkeypatch.setattr(tiger, "download_tiger_geospatial_zip", lambda url, dest: None)
    monkeypatch.setattr(tiger, "extract_tiger_geospatial_zip", lambda z, d: None)

    # Patch unlink so it doesn't error
    monkeypatch.setattr(Path, "unlink", lambda self: None)

    result = tiger.ingest_tiger_geospatial_tracts()

    assert result["status"] == "success"
    assert result["year"] == 2024
    assert "tiger_geospatial_tracts" in result["output_dir"]

    # ingestion_state should have been updated
    assert any(call[0] == "mark" for call in mock_ingestion_state.calls)
    assert any(call[0] == "update" for call in mock_ingestion_state.calls)


# ------------------------------------------------------------
# Test for ingest_tiger_geospatial_tracts() download failure
# ------------------------------------------------------------


def test_ingest_tiger_geospatial_tracts_download_failure(
    monkeypatch, mock_settings, mock_ingestion_state, tmp_path
):
    year = 2024
    output_dir = tmp_path / "raw" / "tiger_geospatial_tracts" / str(year)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        tiger,
        "build_tiger_geospatial_url",
        lambda y: ("https://fake-url", "tl_2024_55_tract.zip"),
    )

    # Force download failure
    monkeypatch.setattr(
        tiger,
        "download_tiger_geospatial_zip",
        lambda url, dest: (_ for _ in ()).throw(Exception("download failed")),
    )

    result = tiger.ingest_tiger_geospatial_tracts()

    assert result["status"] == "failed"
    assert "download failed" in result["error"]

    # No ingestion_state updates should occur
    assert mock_ingestion_state.calls == []


# ------------------------------------------------------------
# Test for ingest_tiger_geospatial_tracts() extraction failure
# ------------------------------------------------------------


def test_ingest_tiger_geospatial_tracts_extract_failure(
    monkeypatch, mock_settings, mock_ingestion_state, tmp_path
):
    year = 2024
    output_dir = tmp_path / "raw" / "tiger_geospatial_tracts" / str(year)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        tiger,
        "build_tiger_geospatial_url",
        lambda y: ("https://fake-url", "tl_2024_55_tract.zip"),
    )

    # Download succeeds
    monkeypatch.setattr(tiger, "download_tiger_geospatial_zip", lambda url, dest: None)

    # Extraction fails
    monkeypatch.setattr(
        tiger,
        "extract_tiger_geospatial_zip",
        lambda z, d: (_ for _ in ()).throw(Exception("extract failed")),
    )

    result = tiger.ingest_tiger_geospatial_tracts()

    assert result["status"] == "failed"
    assert "extract failed" in result["error"]

    # Should NOT perform final ingestion_state update
    assert not any(
        call[0] == "update" and "last_successful_full_run_timestamp" in call[1]
        for call in mock_ingestion_state.calls
    )
