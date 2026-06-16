import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import pandas as pd

from comfort_index_pipeline.config.settings import settings
from comfort_index_pipeline.ingestion.utils.http import DEFAULT_TIMEOUT, SESSION
from comfort_index_pipeline.state.ingestion_state import ingestion_state

EPQS_URL = settings.USGS_ELEVATION_API_BASE_URL


def _query_epqs(lat: float, lon: float) -> Optional[float]:
    """
    Query the USGS elevation service for elevation at a given lat/lon.

    SESSION handles retries, so this function:
      - Adds a courtesy delay
      - Safely parses JSON
      - Logs failures
      - Returns None if elevation cannot be extracted
    """
    params = {
        "x": lon,
        "y": lat,
        "units": "Meters",
        "output": "json",
    }

    time.sleep(0.25)

    try:
        response = SESSION.get(EPQS_URL, params=params, timeout=DEFAULT_TIMEOUT)
    except Exception as exc:
        print(f"[EPQS ERROR] Request failed for lat={lat}, lon={lon}: {exc}")
        return None

    try:
        data = response.json()
    except ValueError:
        print(f"[EPQS WARNING] Non-JSON response for lat={lat}, lon={lon}.")
        return None

    if "value" in data:
        try:
            return float(data["value"])
        except Exception:
            print(
                f"[EPQS WARNING] Could not parse 'value' field for lat={lat}, lon={lon}. "
                f"Raw value: {data.get('value')}"
            )
            return None

    print(
        f"[EPQS WARNING] Missing 'value' field for lat={lat}, lon={lon}. "
        f"Keys present: {list(data.keys())}"
    )
    return None


def _load_station_coordinates() -> List[Tuple[str, float, float]]:
    """
    Load station coordinates from external station metadata parquet.

    Returns:
        List of (station_id, latitude, longitude).
    """
    path = settings.EXTERNAL_DATA_DIR / "lcdv2_stations.parquet"
    df = pd.read_parquet(path)

    return [
        (row["station"], float(row["latitude"]), float(row["longitude"]))
        for _, row in df.iterrows()
    ]


def _load_tract_coordinates() -> List[Tuple[str, float, float]]:
    """
    Returns:
        List of (tract_geoid, centroid_lat, centroid_lon).
    """
    path = (
        settings.NORMALIZED_DATA_DIR
        / "tiger_geospatial_tracts"
        / "tiger_geospatial_tracts.parquet"
    )

    df = pd.read_parquet(path)

    required = {"tract", "centroid_lat", "centroid_lon"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(
            f"Normalized TIGER tracts parquet missing expected columns: {missing}"
        )

    coords: List[Tuple[str, float, float]] = []
    for _, row in df.iterrows():
        coords.append(
            (
                str(row["tract"]),
                float(row["centroid_lat"]),
                float(row["centroid_lon"]),
            )
        )

    return coords


# -----------------------------
# Parallel Worker Functions
# -----------------------------


def _eqps_worker_station(station_id: str, lat: float, lon: float) -> dict:
    elevation = _query_epqs(lat, lon)
    return {
        "station": station_id,
        "latitude": lat,
        "longitude": lon,
        "elevation_m": elevation,
    }


def _eqps_worker_tract(tract_id: str, lat: float, lon: float) -> dict:
    elevation = _query_epqs(lat, lon)
    return {
        "tract": tract_id,
        "centroid_lat": lat,
        "centroid_lon": lon,
        "elevation_m": elevation,
    }


# -----------------------------
# Station Elevation Ingestion
# -----------------------------


def ingest_station_elevation() -> dict:
    print("\n=== Ingesting station elevation data ===")

    output_path = settings.RAW_DATA_DIR / "elevation" / "station_elevation.parquet"

    if output_path.exists():
        print(f"Station elevation file already exists at {output_path}, skipping.")
        return {"status": "skipped", "path": str(output_path)}

    coords = _load_station_coordinates()
    total = len(coords)
    print(f"Loading {total} station coordinates.")

    rows = []
    completed = 0

    # Parallel execution
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(_eqps_worker_station, station_id, lat, lon)
            for station_id, lat, lon in coords
        ]

        for future in as_completed(futures):
            rows.append(future.result())
            completed += 1

            if completed % 10 == 0 or completed == total:
                pct = (completed / total) * 100
                print(f"Processed {completed}/{total} stations ({pct:.1f}%)")

    df = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)

    ingestion_state.mark_ingested_now("elevation_stations")
    ingestion_state.update("elevation_stations", "last_ingested_count", len(df))
    ingestion_state.update(
        "elevation_stations",
        "last_successful_full_run_timestamp",
        datetime.now(timezone.utc).isoformat(),
    )

    print(f"Saved station elevation to {output_path}")

    return {
        "status": "success",
        "count": len(df),
        "path": str(output_path),
    }


# -----------------------------
# Tract Elevation Ingestion
# -----------------------------


def ingest_tract_elevation() -> dict:
    print("\n=== Ingesting tract elevation data ===")

    output_path = settings.RAW_DATA_DIR / "elevation" / "tract_elevation.parquet"

    if output_path.exists():
        print(f"Tract elevation file already exists at {output_path}, skipping.")
        return {"status": "skipped", "path": str(output_path)}

    coords = _load_tract_coordinates()
    total = len(coords)
    print(f"Loading {total} tract centroids.")

    rows = []
    completed = 0

    # Parallel execution
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(_eqps_worker_tract, tract_id, lat, lon)
            for tract_id, lat, lon in coords
        ]

        for future in as_completed(futures):
            rows.append(future.result())
            completed += 1

            if completed % 50 == 0 or completed == total:
                pct = (completed / total) * 100
                print(f"Processed {completed}/{total} tracts ({pct:.1f}%)")

    df = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)

    ingestion_state.mark_ingested_now("elevation_tracts")
    ingestion_state.update("elevation_tracts", "last_ingested_count", len(df))
    ingestion_state.update(
        "elevation_tracts",
        "last_successful_full_run_timestamp",
        datetime.now(timezone.utc).isoformat(),
    )

    print(f"Saved tract elevation to {output_path}")

    return {
        "status": "success",
        "count": len(df),
        "path": str(output_path),
    }
