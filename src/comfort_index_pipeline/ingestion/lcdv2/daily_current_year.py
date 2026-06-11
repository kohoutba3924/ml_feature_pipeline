# src/comfort_index_pipeline/ingestion/lcdv2/daily_current_year.py

import time
from datetime import date, datetime, timezone

import pandas as pd

from comfort_index_pipeline.config.settings import settings
from comfort_index_pipeline.ingestion.utils.http import SESSION, TIMEOUT
from comfort_index_pipeline.state.state import ingestion_state

# ------------------------------------------------------------
# Load target-state station list (WBAN-based)
# ------------------------------------------------------------
STATION_METADATA_PATH = settings.EXTERNAL_DATA_DIR / "lcdv2_stations.parquet"

df_stations = pd.read_parquet(STATION_METADATA_PATH)

# Normalize WBAN IDs: "WBAN:04803" → "04803"
TARGET_STATIONS = set(df_stations["station"].str.replace("WBAN:", "", regex=False))


# ------------------------------------------------------------
# Fetch daily summaries for a single station
# ------------------------------------------------------------
def fetch_daily_api_for_station(wban: str, year: int) -> pd.DataFrame:
    """
    Fetches daily summaries for a single station for the current year.
    Handles pagination automatically.
    """

    url = (
        settings.LCDV2_CURRENT_YEAR_BASE_URL.rstrip("/") + settings.LCDV2_DATA_ENDPOINT
    )

    headers = {"token": settings.NOAA_API_KEY}

    params = {
        "datasetid": settings.LCDV2_DATASET_ID,
        "stationid": f"WBAN:{wban}",
        "startdate": f"{year}-01-01",
        "enddate": date.today().isoformat(),
        "limit": 1000,
        "offset": 1,
    }

    all_results = []
    more_pages = True

    while more_pages:
        response = SESSION.get(url, headers=headers, params=params, timeout=TIMEOUT)

        # Handle rate limiting gracefully, update later for handling
        if response.status_code == 429:
            print(f"Rate limited for WBAN {wban}, sleeping 2s...")
            time.sleep(2)
            continue

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

    if not all_results:
        return pd.DataFrame()

    return pd.DataFrame(all_results)


# ------------------------------------------------------------
# Main ingestion entry point
# ------------------------------------------------------------
def ingest_daily_api() -> dict:
    current_year = date.today().year

    print(f"\n=== Processing LCDv2 daily API ingestion for {current_year} ===")

    output_dir = settings.RAW_DATA_DIR / "lcdv2" / "daily" / str(current_year)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    start_time = time.time()

    # Track how many stations were successfully processed
    successful_stations = 0
    expected_stations = len(TARGET_STATIONS)

    for idx, wban in enumerate(sorted(TARGET_STATIONS), start=1):
        try:
            df = fetch_daily_api_for_station(wban, current_year)

            if df.empty:
                print(f"  → No data for WBAN {wban} (skipping).")
                continue

            # Save raw CSV (overwrite to capture late-arriving data)
            filename = f"{wban}-{current_year}.csv"
            output_path = output_dir / filename
            df.to_csv(output_path, index=False)

            # PROGRESS TRACKING (inside loop)
            ingestion_state.update(
                "lcdv2_daily_current_year", "last_ingested_station", wban
            )
            ingestion_state.mark_ingested_now("lcdv2_daily_current_year")

            results[wban] = len(df)
            successful_stations += 1

            # Progress logging every 10 stations
            if idx % 10 == 0:
                elapsed = time.time() - start_time
                print(
                    f"  → {idx}/{expected_stations} stations processed ({elapsed:.1f}s elapsed)"
                )

        except Exception as e:
            print(f"Failed to ingest WBAN {wban}: {e}")

    # --------------------------------------------------------
    # RUN SUMMARY (always updated)
    # --------------------------------------------------------
    ingestion_state.update(
        "lcdv2_daily_current_year", "last_run_station_count", successful_stations
    )

    # --------------------------------------------------------
    # SUCCESS MARKER (only if full run completed)
    # --------------------------------------------------------
    if successful_stations == expected_stations:
        ingestion_state.update(
            "lcdv2_daily_current_year",
            "last_successful_full_run_timestamp",
            datetime.now(timezone.utc).isoformat(),
        )

    return results
