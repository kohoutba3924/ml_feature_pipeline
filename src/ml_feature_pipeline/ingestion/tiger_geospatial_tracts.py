# src/ml_feature_pipeline/ingestion/tiger_geospatial_tracts.py

import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ml_feature_pipeline.config.settings import settings
from ml_feature_pipeline.ingestion.utils.http import DEFAULT_TIMEOUT, SESSION
from ml_feature_pipeline.state.ingestion_state import ingestion_state


def build_tiger_geospatial_url(year: int) -> tuple[str, str]:
    """
    Builds the TIGER/Line URL and filename for Census tracts for the given year.
    Uses settings.TIGER_TRACT_BASE_URL and settings.TIGER_STATE_FIPS.
    """
    base = settings.TIGER_TRACT_BASE_URL.format(year=year)
    filename = f"tl_{year}_{settings.TIGER_STATE_FIPS}_tract.zip"
    url = f"{base}/{filename}"
    return url, filename


def download_tiger_geospatial_zip(url: str, dest_path: Path) -> None:
    """
    Downloads the TIGER ZIP file to the destination path.
    """
    response = SESSION.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()

    with open(dest_path, "wb") as f:
        f.write(response.content)


def extract_tiger_geospatial_zip(zip_path: Path, extract_dir: Path) -> None:
    """
    Extracts the TIGER ZIP file into the given directory.
    """
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)


def ingest_tiger_geospatial_tracts() -> dict:
    """
    Ingests TIGER geospatial Census tracts for Wisconsin.

    Steps:
    - Determine target year
    - Build URL + filename
    - Check if shapefile already exists (idempotency)
    - Download ZIP
    - Extract ZIP
    - Delete ZIP
    - Update ingestion state (correct ordering)
    """

    year = settings.TIGER_TRACT_YEAR
    print(f"\n=== Processing TIGER geospatial tracts for {year} ===")

    # Prepare directories
    output_dir = settings.RAW_DATA_DIR / "tiger_geospatial_tracts" / str(year)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build URL + filename
    url, zip_filename = build_tiger_geospatial_url(year)
    zip_path = output_dir / zip_filename

    # Determine the expected extracted .shp file
    shp_filename = f"tl_{year}_{settings.TIGER_STATE_FIPS}_tract.shp"
    shp_path = output_dir / shp_filename

    # Idempotency check: if .shp exists, ingestion already completed
    if shp_path.exists():
        print(
            f"Shapefile already exists at {shp_path}, skipping download and extraction."
        )
        return {
            "status": "skipped",
            "reason": "already_ingested",
            "year": year,
            "output_dir": str(output_dir),
        }

    print(f"Downloading: {url}")

    # Download ZIP
    try:
        download_tiger_geospatial_zip(url, zip_path)
        print(f"Downloaded ZIP to {zip_path}")
    except Exception as e:
        print(f"Failed to download TIGER ZIP: {e}")
        return {"status": "failed", "error": str(e)}

    # Update ingestion state (first 3 fields)
    ingestion_state.update("tiger_geospatial_tracts", "last_ingested_year", year)
    ingestion_state.update(
        "tiger_geospatial_tracts", "last_ingested_file", zip_filename
    )
    ingestion_state.mark_ingested_now("tiger_geospatial_tracts")

    # Extract files from ZIP
    try:
        extract_tiger_geospatial_zip(zip_path, output_dir)
        print(f"Extracted ZIP into {output_dir}")
    except Exception as e:
        print(f"Failed to extract TIGER ZIP: {e}")
        return {"status": "failed", "error": str(e)}

    # Delete ZIP after successful file extraction
    try:
        zip_path.unlink()
        print(f"Deleted ZIP file: {zip_path}")
    except Exception as e:
        print(f"Warning: Failed to delete ZIP file: {e}")

    # Final success marker
    ingestion_state.update(
        "tiger_geospatial_tracts",
        "last_successful_full_run_timestamp",
        datetime.now(timezone.utc).isoformat(),
    )

    return {
        "status": "success",
        "year": year,
        "output_dir": str(output_dir),
    }
