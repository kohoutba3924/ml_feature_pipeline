# src/ml_feature_pipeline/ingestion/lcdv2/hourly_prior_years.py

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from ml_feature_pipeline.config.settings import settings
from ml_feature_pipeline.ingestion.utils.http import DEFAULT_TIMEOUT, SESSION
from ml_feature_pipeline.state.ingestion_state import ingestion_state

# ------------------------------------------------------------
# Load target-state station list
# (WBAN-based filtering)
# ------------------------------------------------------------
STATION_METADATA_PATH = settings.EXTERNAL_DATA_DIR / "lcdv2_stations.parquet"

df_stations = pd.read_parquet(STATION_METADATA_PATH)

# Normalize WBAN IDs: "WBAN:04803" → "04803"
TARGET_STATION_WBANS = set(df_stations["station"].str.replace("WBAN:", "", regex=False))


# ------------------------------------------------------------
# Determine completed years to ingest
# ------------------------------------------------------------
def get_years_to_ingest() -> list[int]:
    current_year = date.today().year
    years_back = settings.LCDV2_HISTORICAL_YEARS
    return list(range(current_year - years_back, current_year))


# ------------------------------------------------------------
# Extract WBAN from bulk filename
# Example: "01001099999.csv" → "99999"
# ------------------------------------------------------------
def extract_wban_from_filename(filename: str) -> str:
    core = filename.replace(".csv", "")
    return core[-5:]  # last 5 digits = WBAN


# ------------------------------------------------------------
# Scrape NOAA directory for hourly files (regex-based)
# ------------------------------------------------------------
def list_hourly_files_for_year(year: int) -> list[str]:

    print("Please wait: Collecting list of files for download.")

    base_url = settings.LCDV2_PRIOR_YEAR_BASE_URL
    url = f"{base_url}/{year}/"

    response = SESSION.get(url, timeout=DEFAULT_TIMEOUT)

    if response.status_code == 404:
        print(f"  → Year {year} not available on NOAA (skipping).")
        return []

    response.raise_for_status()

    # Extract *.csv filenames from directory listing
    return re.findall(r'href="([^"]+\.csv)"', response.text)


# ------------------------------------------------------------
# Worker: Download a single file
# ------------------------------------------------------------
def _download_worker(year: int, scraped_filename: str, output_dir: Path) -> str:
    """
    Downloads a single LCDv2 hourly file and saves it with the normalized filename:
        NOAA: 01001099999.csv
        Saved: 01001099999-2025.csv
    Returns the saved filename.
    """
    station_id = scraped_filename.replace(".csv", "")
    correct_filename = f"{station_id}-{year}.csv"

    base_url = settings.LCDV2_PRIOR_YEAR_BASE_URL
    url = f"{base_url}/{year}/{scraped_filename}"

    output_path = output_dir / correct_filename

    response = SESSION.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

    return correct_filename


# ------------------------------------------------------------
# Main ingestion entry point
# ------------------------------------------------------------
def ingest_hourly_raw() -> dict:
    years = get_years_to_ingest()
    results = {}

    print(f"\n=== Retrieving LCDv2 hourly files for years: {years} ===")

    for year in years:
        print(f"\n=== Processing LCDv2 hourly files for year {year} ===")

        output_dir = settings.RAW_DATA_DIR / "lcdv2" / "hourly" / str(year)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Discover available files
        scraped_files = list_hourly_files_for_year(year)

        # Filter to stations for the configured state (WBAN match)
        target_files = [
            f
            for f in scraped_files
            if extract_wban_from_filename(f) in TARGET_STATION_WBANS
        ]

        print(
            f"Found {len(scraped_files)} total files, {len(target_files)} target files."
        )

        # Determine missing files based on corrected filename format
        expected_filenames = [
            f"{f.replace('.csv', '')}-{year}.csv" for f in target_files
        ]

        missing = [
            (scraped, expected)
            for scraped, expected in zip(target_files, expected_filenames)
            if not (output_dir / expected).exists()
        ]

        print(f"{len(missing)} target-state files missing for {year}.")

        if not missing:
            print(f"All files for {year} already exist — skipping downloads.")
            results[year] = {
                "total_files": len(target_files),
                "downloaded": [],
                "status": "already_exists",
            }
            continue

        downloaded = []
        total = len(missing)
        completed = 0

        # --------------------------------------------------------
        # Parallelized downloads
        # --------------------------------------------------------
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(_download_worker, year, scraped_filename, output_dir)
                for scraped_filename, _ in missing
            ]

            for future in as_completed(futures):
                saved_name = future.result()
                downloaded.append(saved_name)
                completed += 1

                # Progress logging every 10 files
                if completed % 10 == 0 or completed == total:
                    pct = (completed / total) * 100 if total > 0 else 100
                    print(f"Processed {completed}/{total} files ({pct:.1f}%)")

        # Update ingestion state
        if downloaded:
            ingestion_state.update(
                "lcdv2_hourly_prior_years", "last_ingested_year", year
            )
            ingestion_state.update(
                "lcdv2_hourly_prior_years", "last_ingested_file", downloaded[-1]
            )
            ingestion_state.mark_ingested_now("lcdv2_hourly_prior_years")

        results[year] = {
            "total_files": len(target_files),
            "downloaded": downloaded,
            "status": "downloaded",
        }

    ingestion_state.update(
        "lcdv2_hourly_prior_years",
        "last_successful_full_run_timestamp",
        datetime.now(timezone.utc).isoformat(),
    )

    return results
