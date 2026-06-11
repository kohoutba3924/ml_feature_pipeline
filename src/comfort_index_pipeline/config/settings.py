# src/comfort_index_pipeline/config/settings.py

from pathlib import Path

from pydantic import Field
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

    STATE_FILE_PATH: Path = (
        PROJECT_ROOT
        / "src"
        / "comfort_index_pipeline"
        / "state"
        / "ingestion_state.json"
    )

    # -----------------------------
    # Secrets (defaults overwritten from .env)
    # -----------------------------
    ACS_API_KEY: str | None = None
    NOAA_API_KEY: str | None = None

    # -----------------------------
    # LCDv2 Weather (Daily + Hourly)
    # -----------------------------

    # CDO API station metadata retrieval
    LCDV2_STATIONS_ENDPOINT: str = "/stations"
    LCDV2_LOCATION_FILTER: str = "FIPS:55"  # Wisconsin (derived from TIGER_STATE_FIPS)

    # Bulk file access url (historical data by station and year)
    LCDV2_PRIOR_YEAR_BASE_URL: str = (
        "https://www.ncei.noaa.gov/data/local-climatological-data/access"
    )
    # Sets the number of years prior year historical data to retrieve
    LCDV2_HISTORICAL_YEARS: int = 1

    # Daily file access url (used for pulling current year data by station & date range)
    LCDV2_CURRENT_YEAR_BASE_URL: str = "https://www.ncei.noaa.gov/cdo-web/api/v2"
    LCDV2_DATA_ENDPOINT: str = "/data"
    LCDV2_DATASET_ID: str = "LCD"

    # LCDv2 daily fields
    LCDV2_DAILY_FIELDS: list[str] = Field(
        default_factory=lambda: [
            # Temperature
            "DailyMaximumDryBulbTemperature",
            "DailyMinimumDryBulbTemperature",
            "DailyAverageDryBulbTemperature",
            "DailyDepartureFromNormalAverageTemperature",
            # Dew point / humidity
            "DailyAverageDewPointTemperature",
            "DailyAverageRelativeHumidity",
            # Wind
            "DailyPeakWindSpeed",
            "DailyPeakWindDirection",
            # Precipitation / snow
            "DailyPrecipitation",
            "DailySnowfall",
            "DailySnowDepth",
            # Visibility
            "DailyMinimumVisibility",
            # Pressure
            "DailyAverageStationPressure",
            # Weather codes / sky condition
            "DailyWeatherCodes",
            "DailySkyCondition",
        ]
    )

    # LCDv2 hourly fields (source of deriving daily when daily value is NULL)
    LCDV2_HOURLY_FIELDS: list[str] = Field(
        default_factory=lambda: [
            # Temperature
            "HourlyDryBulbTemperature",
            # Dew point / humidity
            "HourlyDewPointTemperature",
            "HourlyRelativeHumidity",
            # Wind
            "HourlyWindSpeed",
            "HourlyWindDirection",
            "HourlyWindGustSpeed",
            # Precipitation
            "HourlyPrecipitation",
            # Visibility
            "HourlyVisibility",
            # Pressure
            "HourlyStationPressure",
        ]
    )

    # -----------------------------
    # Census Tracts (TIGER/Line)
    # -----------------------------
    TIGER_TRACT_BASE_URL: str = "https://www2.census.gov/geo/tiger/TIGER2024/TRACT"
    TIGER_STATE_FIPS: str = "55"  # Wisconsin
    TIGER_YEAR: int = 2024

    # -----------------------------
    # ACS Demographics
    # -----------------------------
    ACS_API_BASE_URL: str = "https://api.census.gov/data"
    ACS_YEAR: int = 2024
    ACS_DATASET: str = "acs/acs5"

    ACS_VARIABLES: list[str] = Field(
        default_factory=lambda: [
            # -------------------------
            # Core Demographics
            # -------------------------
            "B01001_001E",  # Total population
            "B01001_002E",  # Male population
            "B01001_026E",  # Female population
            # -------------------------
            # Household Composition
            # -------------------------
            "B01001_020E",  # Male 65-66
            "B01001_021E",  # Male 67-69
            "B01001_022E",  # Male 70-74
            "B01001_023E",  # Male 75-79
            "B01001_024E",  # Male 80-84
            "B01001_025E",  # Male 85+
            "B01001_044E",  # Female 65-66
            "B01001_045E",  # Female 67-69
            "B01001_046E",  # Female 70-74
            "B01001_047E",  # Female 75-79
            "B01001_048E",  # Female 80-84
            "B01001_049E",  # Female 85+
            "B01001_003E",  # Male under 5
            "B01001_027E",  # Female under 5
            "B01002_001E",  # Median age (total)
            "C18102_001E",  # Disability universe
            "C18102_002E",  # With disability
            # -------------------------
            # Education
            # -------------------------
            "B15003_017E",  # High school graduate
            "B15003_022E",  # Bachelor's degree
            "B15003_023E",  # Master's degree
            "B15003_024E",  # Professional school degree
            "B15003_025E",  # Doctorate degree
            # -------------------------
            # Socioeconomic Status
            # -------------------------
            "B17001_001E",  # Poverty universe
            "B17001_002E",  # Below poverty line
            "B19013_001E",  # Median household income
            "B23025_003E",  # Labor force participation
            "B23025_002E",  # Civilian labor force (denominator)
            "B23025_005E",  # Unemployment count
            "B23025_006E",  # Unemployment rate (denominator)
            "B25002_001E",  # Housing unit universe
            "B25002_002E",  # Occupied
            "B25002_003E",  # Vacant
            "B25077_001E",  # Median home value
            "B25064_001E",  # Median gross rent
            # -------------------------
            # Minority Status & Language
            # -------------------------
            "B03002_001E",  # Race universe
            "B03002_003E",  # Black
            "B03002_004E",  # American Indian
            "B03002_005E",  # Asian
            "B03002_006E",  # Pacific Islander
            "B03002_007E",  # Other race
            "B03002_008E",  # Two or more races
            "B03002_012E",  # Hispanic or Latino
            "B16004_001E",  # Language universe
            "B16004_007E",  # Limited English proficiency (male)
            "B16004_014E",  # Limited English proficiency (female)
            # -------------------------
            # Housing & Transportation
            # -------------------------
            "B08201_001E",  # Vehicle availability universe
            "B08201_002E",  # No vehicle available
            "B25024_001E",  # Housing structure universe
            "B25024_003E",  # 3-4 unit structures
            "B25024_004E",  # 5-9 unit structures
            "B25024_005E",  # 10-19 unit structures
            "B25024_006E",  # 20-49 unit structures
            "B25024_007E",  # 50+ unit structures
            "B25024_010E",  # Mobile homes
        ]
    )

    # -----------------------------
    # Elevation (USGS)
    # -----------------------------
    USGS_ELEVATION_API_URL: str = "https://nationalmap.gov/epqs/pqs.php"
    ELEVATION_BATCH_SIZE: int = 100

    # -----------------------------
    # Pydantic v2 Settings Config
    # -----------------------------
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()
