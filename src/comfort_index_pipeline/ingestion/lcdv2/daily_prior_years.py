# src/comfort_index_pipeline/ingestion/lcdv2/daily_prior_years.py

import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from comfort_index_pipeline.config.settings import settings
from comfort_index_pipeline.ingestion.utils.http import SESSION, TIMEOUT
from comfort_index_pipeline.state.state import ingestion_state

# ------------------------------------------------------------
# Load target-state station list once at import time
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
# Scrape NOAA directory for daily files
# ------------------------------------------------------------
def list_daily_files_for_year(year: int) -> list[str]:
    base_url = settings.LCDV2_PRIOR_YEAR_BASE_URL
    url = f"{base_url}/{year}/"

    response = SESSION.get(url, timeout=TIMEOUT)

    # If NOAA hasn't published this year yet, skip it gracefully
    if response.status_code == 404:
        print(f"  → Year {year} not available on NOAA (skipping).")
        return []

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    files = [
        link.get("href")
        for link in soup.find_all("a")
        if link.get("href", "").endswith(".csv")
    ]

    return files


# ------------------------------------------------------------
# Download a single file with correct filename format
# ------------------------------------------------------------
def download_daily_file(year: int, scraped_filename: str, output_dir: Path) -> Path:
    """
    NOAA lists files as: 01001099999.csv
    Correct format should be: 01001099999-2025.csv
    """

    station_id = scraped_filename.replace(".csv", "")
    correct_filename = f"{station_id}-{year}.csv"

    base_url = settings.LCDV2_PRIOR_YEAR_BASE_URL
    url = f"{base_url}/{year}/{scraped_filename}"

    output_path = output_dir / correct_filename

    response = SESSION.get(url, timeout=TIMEOUT)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

    return output_path, correct_filename


# ------------------------------------------------------------
# Main ingestion entry point
# ------------------------------------------------------------
def ingest_daily_raw() -> dict:
    years = get_years_to_ingest()
    results = {}
    print(f"\n=== Retrieving LCDv2 daily files for years:  {years} ===")

    for year in years:
        print(f"\n=== Processing LCDv2 daily files for year {year} ===")

        # Prepare output directory
        output_dir = settings.RAW_DATA_DIR / "lcdv2" / "daily" / str(year)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Discover available files
        scraped_files = list_daily_files_for_year(year)

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

        downloaded = []
        start_time = time.time()

        for idx, (scraped_filename, expected_filename) in enumerate(missing, start=1):
            try:
                path, saved_name = download_daily_file(
                    year, scraped_filename, output_dir
                )
                downloaded.append(saved_name)

                # Progress logging every 20 files
                if idx % 20 == 0:
                    elapsed = time.time() - start_time
                    print(
                        f"  → {idx}/{len(missing)} downloaded ({elapsed:.1f}s elapsed)"
                    )

            except Exception as e:
                print(f"Failed to download {scraped_filename}: {e}")

        # Update ingestion state
        if downloaded:
            ingestion_state.update(
                "lcdv2_daily_prior_years", "last_ingested_year", year
            )
            ingestion_state.update(
                "lcdv2_daily_prior_years", "last_ingested_file", downloaded[-1]
            )
            ingestion_state.mark_ingested_now("lcdv2_daily_prior_years")

        results[year] = {
            "total_files": len(target_files),
            "downloaded": downloaded,
        }
    ingestion_state.update(
        "lcdv2_daily_prior_years",
        "last_successful_full_run_timestamp",
        datetime.now(timezone.utc).isoformat(),
    )
    return results
