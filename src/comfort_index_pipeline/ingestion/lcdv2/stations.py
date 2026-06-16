from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from comfort_index_pipeline.config.settings import settings
from comfort_index_pipeline.ingestion.utils.http import DEFAULT_TIMEOUT, SESSION
from comfort_index_pipeline.state.ingestion_state import ingestion_state


def fetch_stations() -> List[Dict[str, Any]]:
    """
    Fetches all stations for the configured LCD dataset and location filter
    using the NOAA CDO API. Handles pagination automatically.
    """
    url = settings.LCDV2_API_BASE_URL.rstrip("/") + settings.LCDV2_STATIONS_ENDPOINT

    headers = {"token": settings.NOAA_API_KEY}

    params = {
        "datasetid": settings.LCDV2_DATASET_ID,
        "locationid": settings.LCDV2_LOCATION_FILTER,
        "limit": 1000,
        "offset": 1,
    }

    all_results: List[Dict[str, Any]] = []
    more_pages = True

    while more_pages:
        response = SESSION.get(
            url, headers=headers, params=params, timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()

        data = response.json()

        if "results" in data:
            all_results.extend(data["results"])

        metadata = data.get("metadata", {})
        resultset = metadata.get("resultset", {})
        count = resultset.get("count", 0)
        limit = resultset.get("limit", params["limit"])
        offset = resultset.get("offset", params["offset"])

        if offset + limit > count:
            more_pages = False
        else:
            params["offset"] = offset + limit

    return all_results


def normalize_station_metadata(raw_stations: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Converts raw station metadata into a normalized DataFrame.
    """
    df = pd.DataFrame(raw_stations)

    keep_cols = [
        "id",
        "name",
        "latitude",
        "longitude",
        "elevation",
        "datacoverage",
        "mindate",
        "maxdate",
    ]

    df = df[[col for col in keep_cols if col in df.columns]]

    df = df.rename(
        columns={
            "id": "station",
            "datacoverage": "data_coverage",
            "mindate": "min_date",
            "maxdate": "max_date",
        }
    )

    return df


def save_station_metadata(df: pd.DataFrame) -> Path:
    """
    Saves the normalized station metadata to the external data directory.
    """
    output_path = settings.EXTERNAL_DATA_DIR / "lcdv2_stations.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_parquet(output_path, index=False)
    return output_path


def ingest_station_metadata() -> Path:
    """
    Full ingestion pipeline for LCDv2 station metadata.
    """
    raw_stations = fetch_stations()

    ingestion_state.mark_ingested_now("lcdv2_station_metadata")

    df_norm = normalize_station_metadata(raw_stations)
    output_path = save_station_metadata(df_norm)

    ingestion_state.update(
        "lcdv2_station_metadata",
        "last_successful_full_run_timestamp",
        datetime.now(timezone.utc).isoformat(),
    )

    return output_path
