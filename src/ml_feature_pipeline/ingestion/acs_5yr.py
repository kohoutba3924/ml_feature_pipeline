# src/ml_feature_pipeline/ingestion/acs_5yr.py

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from ml_feature_pipeline.config.settings import settings
from ml_feature_pipeline.ingestion.utils.http import DEFAULT_TIMEOUT, SESSION

# UPDATED: import the new metadata structure
from ml_feature_pipeline.metadata_reference.acs5_variables import ACS5_VARIABLES
from ml_feature_pipeline.state.ingestion_state import ingestion_state

GeoKey = Tuple[str, str, str]  # (state, county, tract)


def chunk_variables(variables: List[str], chunk_size: int) -> List[List[str]]:
    """
    Splits the ACS variable list into chunks of <= settings.ACS_VAR_CHUNK_SIZE
    """
    return [variables[i : i + chunk_size] for i in range(0, len(variables), chunk_size)]


def build_acs_url_for_chunk(chunk_vars: List[str]) -> str:
    """
    Builds the ACS API URL for a single chunk of variables.
    """
    year = settings.ACS_YEAR
    dataset = settings.ACS_DATASET
    state_fips = settings.ACS_STATE_FIPS

    base = f"{settings.ACS_API_BASE_URL}/{year}/{dataset}"
    var_string = ",".join(chunk_vars)

    url = (
        f"{base}?get={var_string}"
        f"&for=tract:*"
        f"&in=state:{state_fips}"
        f"&key={settings.ACS_API_KEY}"
    )

    return url


def fetch_acs_data(url: str) -> List[List[str]]:
    """
    Fetches ACS data from the Census API.
    Logs raw response text if JSON parsing fails.
    """
    response = SESSION.get(url, timeout=DEFAULT_TIMEOUT)
    print(f"ACS API status code: {response.status_code}")

    try:
        return response.json()
    except Exception as e:
        print("\n--- RAW ACS API RESPONSE START ---")
        print(response.text[:2000])
        print("--- RAW ACS API RESPONSE END ---\n")
        raise e


def merge_chunk_into_master(
    master: Dict[GeoKey, Dict[str, str]],
    chunk_data: List[List[str]],
    chunk_vars: List[str],
) -> None:
    """
    Merges a single chunk's data into the master dict keyed by (state, county, tract).
    Assumes the last three columns are: state, county, tract.
    """
    if not chunk_data:
        return

    header = chunk_data[0]
    rows = chunk_data[1:]

    state_idx = header.index("state")
    county_idx = header.index("county")
    tract_idx = header.index("tract")

    var_indices = {var: header.index(var) for var in chunk_vars}

    for row in rows:
        state = row[state_idx]
        county = row[county_idx]
        tract = row[tract_idx]
        key: GeoKey = (state, county, tract)

        if key not in master:
            master[key] = {}

        for var, idx in var_indices.items():
            master[key][var] = row[idx]


def save_merged_acs_csv(
    master: Dict[GeoKey, Dict[str, str]],
    variables: List[str],
    output_path: Path,
) -> None:
    """
    Saves the merged ACS data to a CSV file with columns:
    state, county, tract, <variables in ACS5_VARIABLES order>
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        header = ["state", "county", "tract"] + variables
        writer.writerow(header)

        for (state, county, tract), var_values in master.items():
            row = [state, county, tract] + [var_values.get(v, "") for v in variables]
            writer.writerow(row)


def ingest_acs_5yr() -> dict:
    """
    Ingests ACS 5-year demographic data for the configured state and year.

    Steps:
    - Chunk variables based on ACS_VAR_CHUNK_SIZE
    - For each chunk:
        - Build URL
        - Fetch data
        - Merge into master dict keyed by (state, county, tract)
    - After all chunks succeed:
        - Update last_ingested_year, last_ingested_variables, last_ingested
    - Save merged CSV
    - Update last_successful_full_run_timestamp
    """

    year = settings.ACS_YEAR
    state_fips = settings.ACS_STATE_FIPS

    # UPDATED: use metadata_reference instead of settings.ACS_VARIABLES
    variables = list(ACS5_VARIABLES.keys())

    chunk_size = settings.ACS_VAR_CHUNK_SIZE

    print(f"\n=== Processing ACS 5-year data for {year} (state {state_fips}) ===")

    output_dir = settings.RAW_DATA_DIR / "acs_5yr" / str(year)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"acs_{year}_tracts_state_{state_fips}.csv"

    # Idempotency check
    if output_path.exists():
        print(f"ACS file already exists at {output_path}, skipping ingestion.")
        return {
            "status": "skipped",
            "reason": "already_ingested",
            "year": year,
            "state": state_fips,
            "output_path": str(output_path),
        }

    # Chunk variables
    var_chunks = chunk_variables(variables, chunk_size)
    print(
        f"Variable list split into {len(var_chunks)} chunk(s) (size <= {chunk_size})."
    )

    master: Dict[GeoKey, Dict[str, str]] = {}

    # Fetch and merge each chunk
    for i, chunk_vars in enumerate(var_chunks, start=1):
        print(
            f"\n--- Fetching chunk {i}/{len(var_chunks)} ({len(chunk_vars)} variables) ---"
        )
        url = build_acs_url_for_chunk(chunk_vars)
        print(f"Requesting ACS data from: {url}")

        try:
            chunk_data = fetch_acs_data(url)
            print(f"Fetched {len(chunk_data) - 1} tract rows for chunk {i}.")
        except Exception as e:
            print(f"Failed to fetch ACS data for chunk {i}: {e}")
            return {"status": "failed", "error": str(e), "chunk": i}

        try:
            merge_chunk_into_master(master, chunk_data, chunk_vars)
            print(f"Merged chunk {i} into master dataset.")
        except Exception as e:
            print(f"Failed to merge ACS data for chunk {i}: {e}")
            return {"status": "failed", "error": str(e), "chunk": i}

    # All chunks fetched and merged in memory
    ingestion_state.update("acs_5yr", "last_ingested_year", year)

    # UPDATED: store the raw variable list from metadata_reference
    ingestion_state.update("acs_5yr", "last_ingested_variables", variables)

    ingestion_state.mark_ingested_now("acs_5yr")

    # Save merged CSV
    try:
        save_merged_acs_csv(master, variables, output_path)
        print(f"\nSaved merged ACS data to {output_path}")
    except Exception as e:
        print(f"Failed to save merged ACS CSV: {e}")
        return {"status": "failed", "error": str(e)}

    # Full run success timestamp
    ingestion_state.update(
        "acs_5yr",
        "last_successful_full_run_timestamp",
        datetime.now(timezone.utc).isoformat(),
    )

    return {
        "status": "success",
        "year": year,
        "state": state_fips,
        "output_path": str(output_path),
        "chunks": len(var_chunks),
        "tracts": len(master),
    }
