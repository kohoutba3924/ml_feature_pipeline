# src/ml_feature_pipeline/normalization/raw_to_norm_acs_5yr.py

from pathlib import Path

import pandas as pd

from ml_feature_pipeline.config.settings import settings

# import the authoritative metadata mapping
from ml_feature_pipeline.metadata_reference.acs5_variables import ACS5_VARIABLES
from ml_feature_pipeline.state.ingestion_state import ingestion_state


def _get_raw_acs_csv_path() -> Path:
    year = settings.ACS_YEAR
    state_fips = settings.ACS_STATE_FIPS
    return (
        settings.RAW_DATA_DIR
        / "acs_5yr"
        / str(year)
        / f"acs_{year}_tracts_state_{state_fips}.csv"
    )


def normalize_acs_5yr() -> dict:
    """
    Normalizes raw ACS 5-year CSV into a tract-level Parquet file with:
      - state, county, tract_code, tract (GEOID)
      - normalized ACS variable names
      - numeric types for all ACS variables
    """
    year = settings.ACS_YEAR
    state_fips = settings.ACS_STATE_FIPS

    raw_path = _get_raw_acs_csv_path()
    output_path = settings.NORMALIZED_DATA_DIR / "acs5.parquet"

    print(f"\n=== Normalizing ACS 5-year data for {year} (state {state_fips}) ===")
    print(f"Raw ACS CSV: {raw_path}")
    print(f"Normalized output: {output_path}")

    if not raw_path.exists():
        msg = f"Raw ACS CSV not found at {raw_path}"
        print(msg)
        return {"status": "failed", "error": msg}

    # Idempotency: if normalized file exists, skip
    if output_path.exists():
        print(f"Normalized ACS file already exists at {output_path}, skipping.")
        return {
            "status": "skipped",
            "reason": "already_normalized",
            "year": year,
            "state": state_fips,
            "output_path": str(output_path),
        }

    # Load raw CSV as all strings
    try:
        df = pd.read_csv(raw_path, dtype=str)
    except Exception as e:
        print(f"Failed to read raw ACS CSV: {e}")
        return {"status": "failed", "error": str(e)}

    # Ensure required geo columns exist
    for col in ["state", "county", "tract"]:
        if col not in df.columns:
            msg = f"Required column '{col}' missing from ACS CSV."
            print(msg)
            return {"status": "failed", "error": msg}

    # Normalize geo components
    df["state"] = df["state"].str.zfill(2)
    df["county"] = df["county"].str.zfill(3)
    df["tract_code"] = df["tract"].astype(str).str.zfill(6)
    df["tract"] = df["state"] + df["county"] + df["tract_code"]

    # Extract raw ACS variable list from metadata
    raw_vars = list(ACS5_VARIABLES.keys())

    # Validate that all configured ACS variables exist
    missing_vars = [v for v in raw_vars if v not in df.columns]
    if missing_vars:
        msg = f"Missing ACS variables in raw CSV: {missing_vars}"
        print(msg)
        return {"status": "failed", "error": msg}

    # Rename and convert ACS variables
    for raw_var, norm_name in ACS5_VARIABLES.items():
        df[norm_name] = pd.to_numeric(df[raw_var], errors="coerce")

    # Build final column order
    normalized_var_names = list(ACS5_VARIABLES.values())
    final_columns = ["state", "county", "tract_code", "tract"] + normalized_var_names

    # Select only the normalized columns
    df = df[final_columns]

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        df.to_parquet(output_path, index=False)
        print(f"Saved normalized ACS data to {output_path}")
    except Exception as e:
        print(f"Failed to write normalized ACS Parquet: {e}")
        return {"status": "failed", "error": str(e)}

    # Mark normalization in state
    ingestion_state.update("acs_5yr_normalized", "last_normalized_year", year)
    ingestion_state.mark_ingested_now("acs_5yr_normalized")

    return {
        "status": "success",
        "year": year,
        "state": state_fips,
        "rows": int(len(df)),
        "output_path": str(output_path),
    }
