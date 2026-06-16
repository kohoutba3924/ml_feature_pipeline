from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd

from comfort_index_pipeline.config.settings import settings
from comfort_index_pipeline.state.normalization_state import normalization_state


def _get_latest_tiger_tracts_year(raw_base_dir: Path) -> Optional[int]:
    """
    Returns the latest available year for TIGER tracts in the raw directory,
    or None if no year directories are found.
    """
    if not raw_base_dir.exists():
        return None

    years = []
    for child in raw_base_dir.iterdir():
        if child.is_dir():
            try:
                years.append(int(child.name))
            except ValueError:
                continue

    return max(years) if years else None


def _get_shapefile_path_for_year(raw_base_dir: Path, year: int) -> Path:
    """
    Returns the path to the TIGER tract shapefile for the given year.
    Assumes files are under: raw_base_dir / <year> / tl_<year>_<state>_tract.shp
    """
    year_dir = raw_base_dir / str(year)
    # We expect exactly one tract shapefile in that directory
    candidates = list(year_dir.glob("tl_*_tract.shp"))
    if not candidates:
        raise FileNotFoundError(f"No tract shapefile found in {year_dir}")
    if len(candidates) > 1:
        # If multiple, take the first, but notify more found than expected
        print(
            f"Warning: multiple tract shapefiles found in {year_dir}, using {candidates[0].name}"
        )
    return candidates[0]


def normalize_tiger_tracts() -> dict:
    """
    Normalizes TIGER tract shapefiles into a single Parquet file with:
    - tract identifiers
    - centroids
    - bounding boxes
    - land/water area
    - WKB geometry

    Uses the latest available raw year under data/raw/tiger_geospatial_tracts.
    """
    raw_base_dir = settings.RAW_DATA_DIR / "tiger_geospatial_tracts"
    normalized_output_path = (
        settings.NORMALIZED_DATA_DIR
        / "tiger_geospatial_tracts"
        / "tiger_geospatial_tracts.parquet"
    )

    print("\n=== Normalizing TIGER tracts ===")

    latest_year = _get_latest_tiger_tracts_year(raw_base_dir)
    if latest_year is None:
        raise RuntimeError(f"No TIGER tract raw data found under {raw_base_dir}")

    print(f"Latest TIGER tract raw year detected: {latest_year}")

    shapefile_path = _get_shapefile_path_for_year(raw_base_dir, latest_year)
    print(f"Loading TIGER tracts from: {shapefile_path}")

    gdf = gpd.read_file(shapefile_path)

    # Basic sanity check for expected columns
    required_cols = {
        "GEOID",
        "STATEFP",
        "COUNTYFP",
        "TRACTCE",
        "NAME",
        "ALAND",
        "AWATER",
        "geometry",
    }
    missing = required_cols - set(gdf.columns)
    if missing:
        raise RuntimeError(f"Missing expected TIGER columns: {missing}")

    # Reproject to a projected CRS for accurate geometry operations

    projected = gdf.to_crs(epsg=5070)

    # Accurate centroid
    projected["centroid"] = projected.geometry.centroid
    # Bring centroids back to geographic CRS (WGS84) for lat/lon storage
    centroids_geo = projected.set_geometry("centroid").to_crs(epsg=4326)
    gdf["centroid_lat"] = centroids_geo.geometry.y
    gdf["centroid_lon"] = centroids_geo.geometry.x

    # Accurate area
    gdf["area_m2"] = projected.geometry.area

    # Compute bounding box
    bounds = gdf.geometry.bounds
    gdf["bbox_minx"] = bounds["minx"]
    gdf["bbox_miny"] = bounds["miny"]
    gdf["bbox_maxx"] = bounds["maxx"]
    gdf["bbox_maxy"] = bounds["maxy"]

    # Identifiers
    gdf["tract"] = gdf["GEOID"]
    gdf["state_fips"] = gdf["STATEFP"]
    gdf["county_fips"] = gdf["COUNTYFP"]
    gdf["tract_code"] = gdf["TRACTCE"]

    # Geometry as WKB for Parquet friendliness
    gdf["geometry_wkb"] = gdf.geometry.apply(
        lambda geom: geom.wkb if geom is not None else None
    )

    # Build normalized DataFrame
    df_norm = pd.DataFrame(
        {
            "tract": gdf["tract"],
            "state_fips": gdf["state_fips"],
            "county_fips": gdf["county_fips"],
            "tract_code": gdf["tract_code"],
            "name": gdf["NAME"],
            "aland": gdf["ALAND"],
            "awater": gdf["AWATER"],
            "centroid_lat": gdf["centroid_lat"],
            "centroid_lon": gdf["centroid_lon"],
            "bbox_minx": gdf["bbox_minx"],
            "bbox_miny": gdf["bbox_miny"],
            "bbox_maxx": gdf["bbox_maxx"],
            "bbox_maxy": gdf["bbox_maxy"],
            "geometry_wkb": gdf["geometry_wkb"],
        }
    )

    # Ensure output directory exists
    normalized_output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save to Parquet
    df_norm.to_parquet(normalized_output_path, index=False)
    print(f"Saved normalized TIGER tracts to {normalized_output_path}")

    # Update normalization state
    normalization_state.mark_normalized_now("tiger_geospatial_tracts")
    normalization_state.update(
        "tiger_geospatial_tracts", "raw_year_normalized", latest_year
    )
    normalization_state.update(
        "tiger_geospatial_tracts",
        "last_successful_full_run_timestamp",
        datetime.now(timezone.utc).isoformat(),
    )

    return {
        "status": "success",
        "year": latest_year,
        "path": str(normalized_output_path),
        "tract_count": len(df_norm),
    }
