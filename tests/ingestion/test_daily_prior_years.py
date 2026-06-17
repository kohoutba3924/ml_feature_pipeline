import pytest
from unittest.mock import MagicMock

from comfort_index_pipeline.ingestion.lcdv2 import daily_prior_years

# ------------------------------------------------------------
# FIXTURES
# ------------------------------------------------------------


@pytest.fixture
def mock_target_wbans(monkeypatch):
    """
    Replace TARGET_STATION_WBANS with a small, deterministic set.
    This avoids loading the real parquet file.
    """
    monkeypatch.setattr(daily_prior_years, "TARGET_STATION_WBANS", {"99999", "14839"})


@pytest.fixture
def mock_settings(monkeypatch, tmp_path):
    """
    Patch settings paths so ingestion writes to a temporary directory.
    """

    class DummySettings:
        RAW_DATA_DIR = tmp_path / "raw"
        EXTERNAL_DATA_DIR = tmp_path / "external"
        LCDV2_PRIOR_YEAR_BASE_URL = "https://fake-noaa.test"
        LCDV2_HISTORICAL_YEARS = 2

    monkeypatch.setattr(daily_prior_years, "settings", DummySettings())


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
    monkeypatch.setattr(daily_prior_years, "ingestion_state", dummy)
    return dummy


@pytest.fixture
def mock_session(monkeypatch):
    """
    Patch SESSION.get so no real HTTP calls occur.
    """
    mock = MagicMock()
    monkeypatch.setattr(daily_prior_years, "SESSION", mock)
    return mock


# ------------------------------------------------------------
# PURE LOGIC TESTS
# ------------------------------------------------------------


def test_extract_wban_from_filename():
    assert daily_prior_years.extract_wban_from_filename("01001099999.csv") == "99999"
    assert daily_prior_years.extract_wban_from_filename("72640014839.csv") == "14839"


def test_get_years_to_ingest(monkeypatch):
    # Mock today's date by replacing the module's reference to `date`
    class DummyDate:
        @staticmethod
        def today():
            class D:
                year = 2026

            return D()

    monkeypatch.setattr(daily_prior_years, "date", DummyDate)
    monkeypatch.setattr(daily_prior_years.settings, "LCDV2_HISTORICAL_YEARS", 2)

    assert daily_prior_years.get_years_to_ingest() == [2024, 2025]


def test_list_daily_files_regex_parsing(mock_session, mock_settings):
    # Fake NOAA directory listing
    mock_session.get.return_value.status_code = 200
    mock_session.get.return_value.text = """
        <a href="01001099999.csv">file</a>
        <a href="not_a_file.txt">file</a>
        <a href="72640014839.csv">file</a>
    """

    files = daily_prior_years.list_daily_files_for_year(2024)
    assert files == ["01001099999.csv", "72640014839.csv"]


# ------------------------------------------------------------
# BOUNDARY TESTS
# ------------------------------------------------------------


def test_missing_file_detection(
    monkeypatch, tmp_path, mock_target_wbans, mock_settings, mock_session
):
    """
    Ensure missing files are detected correctly.
    """

    # Mock directory listing for ALL years
    monkeypatch.setattr(
        daily_prior_years,
        "list_daily_files_for_year",
        lambda year: ["01001099999.csv", "72640014839.csv"],
    )

    # Mock HTTP response for worker
    mock_session.get.return_value.status_code = 200
    mock_session.get.return_value.content = b"fake"

    # Create output directory with only one file present
    output_dir = tmp_path / "raw" / "lcdv2" / "daily" / "2024"
    output_dir.mkdir(parents=True)

    # Pretend 01001099999-2024.csv already exists
    (output_dir / "01001099999-2024.csv").write_text("test")

    # Run ingestion
    results = daily_prior_years.ingest_daily_raw()

    # Only one file should be downloaded
    assert results[2024]["total_files"] == 2
    assert len(results[2024]["downloaded"]) == 1


def test_already_exists_branch(
    monkeypatch, tmp_path, mock_target_wbans, mock_settings, mock_session
):
    """
    Ensure the 'already exists' branch triggers correctly.
    """

    # Mock directory listing for ALL years
    monkeypatch.setattr(
        daily_prior_years,
        "list_daily_files_for_year",
        lambda year: ["01001099999.csv"],
    )

    # Mock HTTP response for worker (needed for year 2025)
    mock_session.get.return_value.status_code = 200
    mock_session.get.return_value.content = b"fake"

    # Create output directory with the expected file already present
    output_dir = tmp_path / "raw" / "lcdv2" / "daily" / "2024"
    output_dir.mkdir(parents=True)
    (output_dir / "01001099999-2024.csv").write_text("exists")

    results = daily_prior_years.ingest_daily_raw()

    assert results[2024]["status"] == "already_exists"
    assert results[2024]["downloaded"] == []


def test_download_worker(mock_session, tmp_path, mock_settings):
    """
    Ensure the worker writes the file and returns the correct filename.
    """
    mock_session.get.return_value.status_code = 200
    mock_session.get.return_value.content = b"fake-data"

    output_dir = tmp_path / "raw"
    output_dir.mkdir()

    result = daily_prior_years._download_worker(2024, "01001099999.csv", output_dir)

    assert result == "01001099999-2024.csv"
    assert (output_dir / result).read_bytes() == b"fake-data"


# ------------------------------------------------------------
# INTEGRATION TEST
# ------------------------------------------------------------


def test_full_ingestion_flow(
    monkeypatch,
    tmp_path,
    mock_target_wbans,
    mock_settings,
    mock_session,
    mock_ingestion_state,
):
    """
    End-to-end ingestion test with mocked NOAA + filesystem.
    """

    # Mock directory listing
    monkeypatch.setattr(
        daily_prior_years,
        "list_daily_files_for_year",
        lambda year: ["01001099999.csv", "72640014839.csv"],
    )

    # Mock HTTP file content
    mock_session.get.return_value.status_code = 200
    mock_session.get.return_value.content = b"fake"

    results = daily_prior_years.ingest_daily_raw()

    # Validate results
    assert results[2024]["status"] == "downloaded"
    assert len(results[2024]["downloaded"]) == 2

    # Validate files were written
    out_dir = tmp_path / "raw" / "lcdv2" / "daily" / "2024"
    assert (out_dir / "01001099999-2024.csv").exists()
    assert (out_dir / "72640014839-2024.csv").exists()

    # Validate ingestion_state was updated
    assert any(call[0] == "update" for call in mock_ingestion_state.calls)
