from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd

from ml_feature_pipeline.config.settings import settings
from ml_feature_pipeline.state.normalization_state import normalization_state


def _get_shapefile_path() -> Path:
    """
    Returns the deterministic path to the TIGER tract shapefile for the configured year.

    Expected structure:
        RAW_DATA_DIR / "tiger_geospatial_tracts" / <year> / tl_<year>_<state>_tract.shp
    """
    year = settings.TIGER_TRACT_YEAR
    state_fips = settings.TIGER_STATE_FIPS

    base_dir = settings.RAW_DATA_DIR / "tiger_geospatial_tracts" / str(year)

    # Allow flexibility in filename pattern (Census uses tl_<year>_<state>_tract.shp)
    candidates = list(base_dir.glob(f"tl_{year}_{state_fips}_tract.shp"))

    if not candidates:
        raise FileNotFoundError(
            f"No TIGER tract shapefile found for year {year} and state {state_fips} "
            f"under {base_dir}"
        )

    if len(candidates) > 1:
        print(
            f"Warning: multiple tract shapefiles found for year {year} in {base_dir}, "
            f"using {candidates[0].name}"
        )

    return candidates[0]


def normalize_tiger_tracts() -> dict:
    """
    Normalizes TIGER tract shapefiles into a single Parquet file with:
    - tract identifiers
    - centroids (lat/lon)
    - bounding boxes
    - land/water area
    - WKB geometry

    Uses the configured TIGER_TRACT_YEAR from settings.py.
    """
    year = settings.TIGER_TRACT_YEAR
    state_fips = settings.TIGER_STATE_FIPS

    print(f"\n=== Normalizing TIGER tracts for {year} (state {state_fips}) ===")

    shapefile_path = _get_shapefile_path()
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

    # Convert centroids back to WGS84 for lat/lon
    centroids_geo = projected.set_geometry("centroid").to_crs(epsg=4326)
    gdf["centroid_lat"] = centroids_geo.geometry.y
    gdf["centroid_lon"] = centroids_geo.geometry.x

    # Accurate area
    gdf["area_m2"] = projected.geometry.area

    # Bounding box
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
            "area_m2": gdf["area_m2"],
            "geometry_wkb": gdf["geometry_wkb"],
        }
    )

    # Output path
    output_path = settings.NORMALIZED_DATA_DIR / f"tiger_tracts_{year}.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save to Parquet
    df_norm.to_parquet(output_path, index=False)
    print(f"Saved normalized TIGER tracts to {output_path}")

    # Update normalization state
    normalization_state.mark_normalized_now("tiger_geospatial_tracts")
    normalization_state.update("tiger_geospatial_tracts", "normalized_year", year)
    normalization_state.update(
        "tiger_geospatial_tracts",
        "last_successful_full_run_timestamp",
        datetime.now(timezone.utc).isoformat(),
    )

    return {
        "status": "success",
        "year": year,
        "path": str(output_path),
        "tract_count": len(df_norm),
    }
