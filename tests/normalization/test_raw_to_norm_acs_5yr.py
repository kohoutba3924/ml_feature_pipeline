import pytest
import pandas as pd

from comfort_index_pipeline.normalization import raw_to_norm_acs_5yr as norm
from comfort_index_pipeline.metadata_reference.acs5_variables import ACS5_VARIABLES

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
        ACS_YEAR = 2024
        ACS_STATE_FIPS = "55"

    monkeypatch.setattr(norm, "settings", DummySettings())


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
    monkeypatch.setattr(norm, "ingestion_state", dummy)
    return dummy


# ------------------------------------------------------------
# TEST: Missing raw CSV
# ------------------------------------------------------------


def test_normalize_missing_raw_csv(mock_settings):
    result = norm.normalize_acs_5yr()
    assert result["status"] == "failed"
    assert "Raw ACS CSV not found" in result["error"]


# ------------------------------------------------------------
# TEST: Skip when normalized file already exists
# ------------------------------------------------------------


def test_normalize_skip_if_output_exists(mock_settings, tmp_path):
    # Create raw CSV so the function gets past the first check
    raw_path = tmp_path / "raw" / "acs_5yr" / "2024" / "acs_2024_tracts_state_55.csv"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("dummy")

    # Create normalized output file
    output_path = tmp_path / "normalized" / "acs5_2024.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("exists")

    result = norm.normalize_acs_5yr()

    assert result["status"] == "skipped"
    assert result["reason"] == "already_normalized"


# ------------------------------------------------------------
# TEST: Missing required geo columns
# ------------------------------------------------------------


def test_normalize_missing_geo_columns(mock_settings, tmp_path):
    raw_path = tmp_path / "raw" / "acs_5yr" / "2024" / "acs_2024_tracts_state_55.csv"
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    # Missing "tract"
    df = pd.DataFrame(
        {
            "state": ["55"],
            "county": ["001"],
            # "tract" missing
            **{var: ["10"] for var in ACS5_VARIABLES.keys()},
        }
    )
    df.to_csv(raw_path, index=False)

    result = norm.normalize_acs_5yr()
    assert result["status"] == "failed"
    assert "Required column 'tract' missing" in result["error"]


# ------------------------------------------------------------
# TEST: Missing ACS variables
# ------------------------------------------------------------


def test_normalize_missing_acs_variables(mock_settings, tmp_path):
    raw_path = tmp_path / "raw" / "acs_5yr" / "2024" / "acs_2024_tracts_state_55.csv"
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    # Drop one ACS variable
    vars_minus_one = list(ACS5_VARIABLES.keys())[:-1]

    df = pd.DataFrame(
        {
            "state": ["55"],
            "county": ["001"],
            "tract": ["000100"],
            **{var: ["10"] for var in vars_minus_one},
        }
    )
    df.to_csv(raw_path, index=False)

    result = norm.normalize_acs_5yr()
    assert result["status"] == "failed"
    assert "Missing ACS variables" in result["error"]


# ------------------------------------------------------------
# TEST: Successful normalization
# ------------------------------------------------------------


def test_normalize_success(mock_settings, mock_ingestion_state, tmp_path):
    raw_path = tmp_path / "raw" / "acs_5yr" / "2024" / "acs_2024_tracts_state_55.csv"
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    # Build a minimal valid CSV
    df = pd.DataFrame(
        {
            "state": ["55"],
            "county": ["001"],
            "tract": ["000100"],
            **{var: ["10"] for var in ACS5_VARIABLES.keys()},
        }
    )
    df.to_csv(raw_path, index=False)

    result = norm.normalize_acs_5yr()

    assert result["status"] == "success"
    assert result["rows"] == 1

    # Check ingestion_state calls
    assert any(call[0] == "update" for call in mock_ingestion_state.calls)
    assert any(call[0] == "mark" for call in mock_ingestion_state.calls)

    # Check output parquet exists
    output_path = tmp_path / "normalized" / "acs5_2024.parquet"
    assert output_path.exists()

    # Validate contents
    out_df = pd.read_parquet(output_path)

    # GEOID construction
    assert out_df.loc[0, "tract"] == "55001000100"
    assert out_df.loc[0, "tract_code"] == "000100"

    # All normalized columns exist
    for norm_name in ACS5_VARIABLES.values():
        assert norm_name in out_df.columns

    # Numeric conversion
    for norm_name in ACS5_VARIABLES.values():
        assert out_df[norm_name].dtype.kind in ("i", "f")


# ------------------------------------------------------------
# TEST: Numeric coercion
# ------------------------------------------------------------


def test_normalize_numeric_coercion(mock_settings, tmp_path):
    raw_path = tmp_path / "raw" / "acs_5yr" / "2024" / "acs_2024_tracts_state_55.csv"
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    # Insert non-numeric values
    df = pd.DataFrame(
        {
            "state": ["55"],
            "county": ["001"],
            "tract": ["000100"],
            **{var: ["not_a_number"] for var in ACS5_VARIABLES.keys()},
        }
    )
    df.to_csv(raw_path, index=False)

    result = norm.normalize_acs_5yr()
    assert result["status"] == "success"

    out_df = pd.read_parquet(tmp_path / "normalized" / "acs5_2024.parquet")

    # All normalized fields should be NaN
    for norm_name in ACS5_VARIABLES.values():
        assert pd.isna(out_df.loc[0, norm_name])


# ------------------------------------------------------------
# TEST: Column ordering
# ------------------------------------------------------------


def test_normalize_column_order(mock_settings, tmp_path):
    raw_path = tmp_path / "raw" / "acs_5yr" / "2024" / "acs_2024_tracts_state_55.csv"
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(
        {
            "state": ["55"],
            "county": ["001"],
            "tract": ["000100"],
            **{var: ["10"] for var in ACS5_VARIABLES.keys()},
        }
    )
    df.to_csv(raw_path, index=False)

    norm.normalize_acs_5yr()

    out_df = pd.read_parquet(tmp_path / "normalized" / "acs5_2024.parquet")

    expected_order = ["state", "county", "tract_code", "tract"] + list(
        ACS5_VARIABLES.values()
    )
    assert list(out_df.columns) == expected_order
