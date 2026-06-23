import pytest
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon

from comfort_index_pipeline.normalization import raw_to_norm_tiger_tracts as norm

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
        TIGER_TRACT_YEAR = 2024
        TIGER_STATE_FIPS = "55"

    monkeypatch.setattr(norm, "settings", DummySettings())


@pytest.fixture
def mock_normalization_state(monkeypatch):
    """
    Replace normalization_state with a dummy object that records calls.
    """

    class DummyState:
        def __init__(self):
            self.calls = []

        def update(self, *args, **kwargs):
            self.calls.append(("update", args, kwargs))

        def mark_normalized_now(self, *args, **kwargs):
            self.calls.append(("mark", args, kwargs))

    dummy = DummyState()
    monkeypatch.setattr(norm, "normalization_state", dummy)
    return dummy


# ------------------------------------------------------------
# TEST: Missing shapefile
# ------------------------------------------------------------


def test_missing_shapefile(mock_settings):
    with pytest.raises(FileNotFoundError):
        norm.normalize_tiger_tracts()


# ------------------------------------------------------------
# TEST: Skip logic is not needed (TIGER always overwrites)
# ------------------------------------------------------------
# (No skip test — TIGER normalization always writes a new file)


# ------------------------------------------------------------
# TEST: Successful normalization
# ------------------------------------------------------------


def test_normalize_success(
    monkeypatch, mock_settings, mock_normalization_state, tmp_path
):
    # Create fake shapefile directory
    year_dir = tmp_path / "raw" / "tiger_geospatial_tracts" / "2024"
    year_dir.mkdir(parents=True, exist_ok=True)

    shapefile_path = year_dir / "tl_2024_55_tract.shp"
    shapefile_path.write_text("placeholder")  # existence only

    # Fake GeoDataFrame
    fake_gdf = gpd.GeoDataFrame(
        {
            "GEOID": ["55001000100"],
            "STATEFP": ["55"],
            "COUNTYFP": ["001"],
            "TRACTCE": ["000100"],
            "NAME": ["Tract 100"],
            "ALAND": [12345],
            "AWATER": [678],
            "geometry": [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        },
        crs="EPSG:4326",
    )

    # Monkeypatch geopandas.read_file
    monkeypatch.setattr(gpd, "read_file", lambda path: fake_gdf)

    # Monkeypatch CRS transformations
    def fake_to_crs(self, epsg):
        if epsg == 5070:
            # projected CRS: geometry area = 1.0
            projected = self.copy()
            projected["geometry"] = self["geometry"]
            return projected
        if epsg == 4326:
            return self
        return self

    monkeypatch.setattr(gpd.GeoDataFrame, "to_crs", fake_to_crs)

    result = norm.normalize_tiger_tracts()

    assert result["status"] == "success"
    assert result["year"] == 2024

    # Output parquet exists
    output_path = tmp_path / "normalized" / "tiger_tracts_2024.parquet"
    assert output_path.exists()

    df = pd.read_parquet(output_path)

    # Validate identifiers
    assert df.loc[0, "tract"] == "55001000100"
    assert df.loc[0, "state_fips"] == "55"
    assert df.loc[0, "county_fips"] == "001"
    assert df.loc[0, "tract_code"] == "000100"

    # Validate centroid fields exist
    assert "centroid_lat" in df.columns
    assert "centroid_lon" in df.columns

    # Validate bounding box fields exist
    assert "bbox_minx" in df.columns
    assert "bbox_maxx" in df.columns

    # Validate WKB geometry exists
    assert df.loc[0, "geometry_wkb"] is not None

    # Validate normalization_state calls
    assert any(call[0] == "mark" for call in mock_normalization_state.calls)
    assert any(call[0] == "update" for call in mock_normalization_state.calls)


# ------------------------------------------------------------
# TEST: Missing required TIGER columns
# ------------------------------------------------------------


def test_missing_required_columns(monkeypatch, mock_settings, tmp_path):
    year_dir = tmp_path / "raw" / "tiger_geospatial_tracts" / "2024"
    year_dir.mkdir(parents=True, exist_ok=True)

    shapefile_path = year_dir / "tl_2024_55_tract.shp"
    shapefile_path.write_text("placeholder")

    # Missing GEOID
    fake_gdf = gpd.GeoDataFrame(
        {
            "STATEFP": ["55"],
            "COUNTYFP": ["001"],
            "TRACTCE": ["000100"],
            "NAME": ["Tract 100"],
            "ALAND": [12345],
            "AWATER": [678],
            "geometry": [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        },
        crs="EPSG:4326",
    )

    monkeypatch.setattr(gpd, "read_file", lambda path: fake_gdf)

    with pytest.raises(RuntimeError) as exc:
        norm.normalize_tiger_tracts()

    assert "Missing expected TIGER columns" in str(exc.value)
