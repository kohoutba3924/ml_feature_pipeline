import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

from comfort_index_pipeline.ingestion import acs_5yr as acs

# ------------------------------------------------------------
# FIXTURES
# ------------------------------------------------------------


@pytest.fixture
def mock_settings(monkeypatch, tmp_path):
    """
    Patch settings so ACS ingestion writes to temp directories.
    """

    class DummySettings:
        RAW_DATA_DIR = tmp_path / "raw"
        ACS_YEAR = 2024
        ACS_STATE_FIPS = "55"
        ACS_DATASET = "acs/acs5"
        ACS_API_BASE_URL = "https://fake-census.test"
        ACS_API_KEY = "fake-key"
        ACS_VARIABLES = ["A", "B", "C", "D"]
        ACS_VAR_CHUNK_SIZE = 2

    monkeypatch.setattr(acs, "settings", DummySettings())


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
    monkeypatch.setattr(acs, "ingestion_state", dummy)
    return dummy


@pytest.fixture
def mock_session(monkeypatch):
    """
    Patch SESSION.get so no real HTTP calls occur.
    """
    mock = MagicMock()
    monkeypatch.setattr(acs, "SESSION", mock)
    return mock


# ------------------------------------------------------------
# TEST chunk_variables()
# ------------------------------------------------------------


def test_chunk_variables():
    result = acs.chunk_variables(["A", "B", "C", "D", "E"], 2)
    assert result == [["A", "B"], ["C", "D"], ["E"]]


# ------------------------------------------------------------
# TEST build_acs_url_for_chunk()
# ------------------------------------------------------------


def test_build_acs_url_for_chunk(mock_settings):
    url = acs.build_acs_url_for_chunk(["A", "B"])

    assert "get=A,B" in url
    assert "for=tract:*" in url
    assert "in=state:55" in url
    assert "2024" in url
    assert "acs/acs5" in url
    assert "fake-key" in url


# ------------------------------------------------------------
# TEST fetch_acs_data()
# ------------------------------------------------------------


def test_fetch_acs_data_success(mock_session, mock_settings):
    mock_session.get.return_value.json.return_value = [["header"], ["row"]]

    result = acs.fetch_acs_data("https://fake-url")

    assert result == [["header"], ["row"]]
    mock_session.get.assert_called_once()


def test_fetch_acs_data_json_failure(mock_session, mock_settings):
    mock_session.get.return_value.json.side_effect = ValueError("bad json")
    mock_session.get.return_value.text = "raw text"

    with pytest.raises(ValueError):
        acs.fetch_acs_data("https://fake-url")


# ------------------------------------------------------------
# TEST merge_chunk_into_master()
# ------------------------------------------------------------


def test_merge_chunk_into_master_basic():
    master = {}
    chunk_data = [
        ["var1", "var2", "state", "county", "tract"],
        ["10", "20", "55", "001", "000100"],
    ]
    acs.merge_chunk_into_master(master, chunk_data, ["var1", "var2"])

    assert master == {("55", "001", "000100"): {"var1": "10", "var2": "20"}}


def test_merge_chunk_into_master_existing_key():
    master = {("55", "001", "000100"): {"var1": "10"}}
    chunk_data = [
        ["var1", "var2", "state", "county", "tract"],
        ["10", "30", "55", "001", "000100"],
    ]
    acs.merge_chunk_into_master(master, chunk_data, ["var1", "var2"])

    assert master[("55", "001", "000100")] == {"var1": "10", "var2": "30"}


def test_merge_chunk_into_master_empty():
    master = {}
    acs.merge_chunk_into_master(master, [], ["A"])
    assert master == {}


# ------------------------------------------------------------
# TEST save_merged_acs_csv()
# ------------------------------------------------------------


def test_save_merged_acs_csv(monkeypatch, tmp_path, mock_settings):
    master = {
        ("55", "001", "000100"): {"A": "10", "B": "20"},
        ("55", "001", "000200"): {"A": "30", "B": "40"},
    }
    variables = ["A", "B"]
    output_path = tmp_path / "acs.csv"

    m = mock_open()
    with patch("builtins.open", m):
        acs.save_merged_acs_csv(master, variables, output_path)

    handle = m()
    written = [call.args[0] for call in handle.write.call_args_list]

    # Ensure header and rows appear
    assert "state,county,tract,A,B" in "".join(written)
    assert "55,001,000100,10,20" in "".join(written)
    assert "55,001,000200,30,40" in "".join(written)


# ------------------------------------------------------------
# TEST ingest_acs_5yr() skip branch
# ------------------------------------------------------------


def test_ingest_acs_5yr_skip(monkeypatch, mock_settings, tmp_path):
    output_path = tmp_path / "raw" / "acs_5yr" / "2024" / "acs_2024_tracts_state_55.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("exists")

    result = acs.ingest_acs_5yr()

    assert result["status"] == "skipped"
    assert result["reason"] == "already_ingested"


# ------------------------------------------------------------
# TEST ingest_acs_5yr() success path
# ------------------------------------------------------------


def test_ingest_acs_5yr_success(
    monkeypatch, mock_settings, mock_ingestion_state, tmp_path
):
    # Chunking
    monkeypatch.setattr(
        acs, "chunk_variables", lambda vars, size: [["A", "B"], ["C", "D"]]
    )

    # URL builder
    monkeypatch.setattr(
        acs, "build_acs_url_for_chunk", lambda chunk: "https://fake-url"
    )

    # Fake chunk data
    fake_chunk = [
        ["A", "B", "C", "D", "state", "county", "tract"],
        ["10", "20", "30", "40", "55", "001", "000100"],
    ]
    monkeypatch.setattr(acs, "fetch_acs_data", lambda url: fake_chunk)

    # Use real merge
    # Patch CSV save
    monkeypatch.setattr(acs, "save_merged_acs_csv", lambda master, vars, path: None)

    result = acs.ingest_acs_5yr()

    assert result["status"] == "success"
    assert result["chunks"] == 2
    assert result["tracts"] == 1

    # ingestion_state should have been updated
    assert any(call[0] == "mark" for call in mock_ingestion_state.calls)
    assert any(call[0] == "update" for call in mock_ingestion_state.calls)


# ------------------------------------------------------------
# TEST ingest_acs_5yr() fetch failure
# ------------------------------------------------------------


def test_ingest_acs_5yr_fetch_failure(
    monkeypatch, mock_settings, mock_ingestion_state, tmp_path
):
    monkeypatch.setattr(
        acs, "chunk_variables", lambda vars, size: [["A", "B"], ["C", "D"]]
    )
    monkeypatch.setattr(
        acs, "build_acs_url_for_chunk", lambda chunk: "https://fake-url"
    )

    # First chunk OK, second chunk fails
    def fake_fetch(url):
        if "first" not in fake_fetch.__dict__:
            fake_fetch.first = True
            return [
                ["A", "B", "state", "county", "tract"],
                ["10", "20", "55", "001", "000100"],
            ]
        raise Exception("fetch failed")

    monkeypatch.setattr(acs, "fetch_acs_data", fake_fetch)

    result = acs.ingest_acs_5yr()

    assert result["status"] == "failed"
    assert result["chunk"] == 2
    assert "fetch failed" in result["error"]

    # No ingestion_state updates
    assert mock_ingestion_state.calls == []


# ------------------------------------------------------------
# TEST ingest_acs_5yr() merge failure
# ------------------------------------------------------------


def test_ingest_acs_5yr_merge_failure(
    monkeypatch, mock_settings, mock_ingestion_state, tmp_path
):
    monkeypatch.setattr(acs, "chunk_variables", lambda vars, size: [["A", "B"]])
    monkeypatch.setattr(
        acs, "build_acs_url_for_chunk", lambda chunk: "https://fake-url"
    )

    fake_chunk = [
        ["A", "state", "county", "tract"],
        ["10", "55", "001", "000100"],
    ]
    monkeypatch.setattr(acs, "fetch_acs_data", lambda url: fake_chunk)

    # Force merge failure
    monkeypatch.setattr(
        acs,
        "merge_chunk_into_master",
        lambda master, data, vars: (_ for _ in ()).throw(Exception("merge failed")),
    )

    result = acs.ingest_acs_5yr()

    assert result["status"] == "failed"
    assert result["chunk"] == 1
    assert "merge failed" in result["error"]

    assert mock_ingestion_state.calls == []


# ------------------------------------------------------------
# TEST ingest_acs_5yr() save failure
# ------------------------------------------------------------


def test_ingest_acs_5yr_save_failure(
    monkeypatch, mock_settings, mock_ingestion_state, tmp_path
):
    monkeypatch.setattr(acs, "chunk_variables", lambda vars, size: [["A", "B"]])
    monkeypatch.setattr(
        acs, "build_acs_url_for_chunk", lambda chunk: "https://fake-url"
    )

    fake_chunk = [
        ["A", "B", "state", "county", "tract"],
        ["10", "20", "55", "001", "000100"],
    ]
    monkeypatch.setattr(acs, "fetch_acs_data", lambda url: fake_chunk)

    # Use real merge
    monkeypatch.setattr(
        acs,
        "save_merged_acs_csv",
        lambda master, vars, path: (_ for _ in ()).throw(Exception("save failed")),
    )

    result = acs.ingest_acs_5yr()

    assert result["status"] == "failed"
    assert "save failed" in result["error"]

    # Should NOT perform final ingestion_state update
    assert not any(
        call[0] == "update" and "last_successful_full_run_timestamp" in call[1]
        for call in mock_ingestion_state.calls
    )
