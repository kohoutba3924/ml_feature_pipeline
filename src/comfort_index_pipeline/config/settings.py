# src/comfort_index_pipeline/config/settings.py

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Central configuration for all ingestion and transformation steps.
    Uses Pydantic v2 (pydantic-settings) for environment-driven configuration.
    """

    # -----------------------------
    # Project Paths
    # -----------------------------
    PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
    DATA_DIR: Path = PROJECT_ROOT / "data"

    RAW_DATA_DIR: Path = DATA_DIR / "raw"
    NORMALIZED_DATA_DIR: Path = DATA_DIR / "normalized"
    EXTERNAL_DATA_DIR: Path = DATA_DIR / "external"
    FEATURE_STORE_DIR: Path = DATA_DIR / "feature_store"

    INGESTION_STATE_FILE_PATH: Path = (
        PROJECT_ROOT
        / "src"
        / "comfort_index_pipeline"
        / "state"
        / "ingestion_state.json"
    )

    NORMALIZATION_STATE_FILE_PATH: Path = (
        PROJECT_ROOT
        / "src"
        / "comfort_index_pipeline"
        / "state"
        / "normalization_state.json"
    )

    # -----------------------------
    # Secrets (defaults overwritten from .env)
    # -----------------------------
    ACS_API_KEY: str | None = None

    # -----------------------------
    # LCDv2 Weather (Daily + Hourly)
    # -----------------------------

    # Bulk file access url (historical data by station and year)
    LCDV2_PRIOR_YEAR_BASE_URL: str = (
        "https://www.ncei.noaa.gov/data/local-climatological-data/access"
    )
    # NOAA API station metadata retrieval
    LCDV2_STATIONS_ENDPOINT: str = "/stations"
    LCDV2_LOCATION_FILTER: str = "FIPS:55"  # Wisconsin (derived from TIGER_STATE_FIPS)
    # Sets the length of the historical data pull, non-inclusive of the current year
    LCDV2_HISTORICAL_YEARS: int = 2

    # -----------------------------
    # Census Tracts (TIGER/Line)
    # -----------------------------
    TIGER_TRACT_YEAR: int = 2024
    TIGER_TRACT_BASE_URL: str = "https://www2.census.gov/geo/tiger/TIGER{year}/TRACT"
    TIGER_STATE_FIPS: str = "55"

    # -----------------------------
    # ACS Demographics
    # -----------------------------
    ACS_YEAR: int = 2024
    ACS_API_BASE_URL: str = "https://api.census.gov/data"
    ACS_DATASET: str = "acs/acs5"
    ACS_STATE_FIPS: str = "55"  # Wisconsin by default
    ACS_VAR_CHUNK_SIZE: int = 50

    # -----------------------------
    # Elevation (USGS)
    # -----------------------------
    USGS_ELEVATION_API_BASE_URL: str = "https://epqs.nationalmap.gov/v1/json"

    # -----------------------------
    # Pydantic v2 Settings Config
    # -----------------------------
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()
