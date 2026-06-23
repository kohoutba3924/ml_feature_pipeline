# src/comfort_index_pipeline/normalization/raw_to_norm_lcdv2_hourly.py

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import polars as pl

from comfort_index_pipeline.config.settings import settings
from comfort_index_pipeline.metadata_reference.lcdv2_variables import (
    LCDV2_HOURLY_VARIABLES,
)
from comfort_index_pipeline.state.normalization_state import normalization_state

# =====================================================================
# Station ID Normalization
# =====================================================================


def normalize_station_id(raw_station: str) -> str:
    if raw_station is None:
        raise ValueError("raw_station cannot be None")

    raw_station = raw_station.strip()
    wban = raw_station[-5:].zfill(5)
    return f"WBAN:{wban}"


# =====================================================================
# Quality Check Helpers
# =====================================================================

WBAN_REGEX = re.compile(r"^WBAN:\d{5}$")
LCDV2_SENTINELS = {"9999", "999", "99", "M", ""}


def _clean_sentinel_values(df: pl.DataFrame) -> pl.DataFrame:
    numeric_fields = [
        "dry_bulb_temp",
        "wet_bulb_temp",
        "dew_point_temp",
        "relative_humidity",
        "wind_speed",
        "wind_direction",
        "wind_gust_speed",
        "precipitation",
        "visibility",
        "station_pressure",
        "barometric_pressure",
    ]

    return df.with_columns(
        [
            pl.when(pl.col(f).is_in(LCDV2_SENTINELS))
            .then(None)
            .otherwise(pl.col(f))
            .alias(f)
            for f in numeric_fields
        ]
    )


def _validate_timestamp_not_null(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        pl.when(pl.col("timestamp").is_null())
        .then(None)
        .otherwise(pl.col("timestamp"))
        .alias("timestamp")
    )


def _validate_station(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        pl.when(
            pl.col("station").is_null()
            | (~pl.col("station").str.contains(r"^WBAN:\d{5}$"))
        )
        .then(None)
        .otherwise(pl.col("station"))
        .alias("station")
    )


def _apply_quality_checks(df: pl.DataFrame) -> pl.DataFrame:
    df = _clean_sentinel_values(df)
    df = _validate_timestamp_not_null(df)
    df = _validate_station(df)
    return df


# =====================================================================
# Core Normalization Helpers
# =====================================================================


def _select_and_rename(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(list(LCDV2_HOURLY_VARIABLES.keys())).rename(LCDV2_HOURLY_VARIABLES)


def _normalize_station_column(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        pl.col("station").map_elements(normalize_station_id, return_dtype=pl.Utf8)
    )


def _parse_timestamp(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(pl.col("timestamp").str.strptime(pl.Datetime, strict=False))


def _cast_numeric_fields(df: pl.DataFrame) -> pl.DataFrame:
    numeric_fields = [
        "dry_bulb_temp",
        "wet_bulb_temp",
        "dew_point_temp",
        "relative_humidity",
        "wind_speed",
        "wind_direction",
        "wind_gust_speed",
        "precipitation",
        "visibility",
        "station_pressure",
        "barometric_pressure",
    ]

    return df.with_columns(
        [pl.col(f).cast(pl.Float64, strict=False) for f in numeric_fields]
    )


# =====================================================================
# File-Level Normalization
# =====================================================================


def normalize_lcdv2_hourly_file(csv_path: Path) -> pl.DataFrame:
    df = pl.read_csv(
        csv_path,
        infer_schema_length=0,
        schema_overrides={"DATE": pl.Utf8, "STATION": pl.Utf8},
    )

    df = _select_and_rename(df)
    df = _normalize_station_column(df)
    df = _parse_timestamp(df)
    df = _apply_quality_checks(df)
    df = _cast_numeric_fields(df)

    return df


# =====================================================================
# IO Helpers
# =====================================================================


def _iter_lcdv2_raw_files(years: Iterable[int]) -> Iterable[tuple[int, Path]]:
    base_dir = settings.RAW_DATA_DIR / "lcdv2" / "daily"

    for year in years:
        year_dir = base_dir / str(year)
        if not year_dir.exists():
            continue

        for csv_path in sorted(year_dir.glob("*.csv")):
            yield year, csv_path


def _write_normalized_parquet(df: pl.DataFrame, station: str, year: int) -> None:
    base_dir = settings.NORMALIZED_DATA_DIR / "lcdv2"
    safe_station = station.replace(":", "_")
    station_dir = base_dir / f"station_id={safe_station}" / f"year={year}"
    station_dir.mkdir(parents=True, exist_ok=True)

    output_path = station_dir / "part.parquet"
    df.write_parquet(output_path)


# =====================================================================
# Pipeline Entrypoint
# =====================================================================


def run_lcdv2_hourly_normalization(years: Iterable[int]) -> None:
    """
    Normalize all LCDv2 raw CSV files for the given years.
    """
    for year, csv_path in _iter_lcdv2_raw_files(years):
        df = normalize_lcdv2_hourly_file(csv_path)

        station_value = df.select("station").unique().item()

        _write_normalized_parquet(df, station=station_value, year=year)

    # -----------------------------
    # Update normalization state
    # -----------------------------

    # Merge years into existing list
    existing_years = normalization_state.get("lcdv2_hourly", "years_normalized") or []
    updated_years = sorted(set(existing_years).union(set(years)))

    normalization_state.update("lcdv2_hourly", "years_normalized", updated_years)

    # Timestamp updates
    timestamp = datetime.now(timezone.utc).isoformat()
    normalization_state.update("lcdv2_hourly", "last_normalized", timestamp)
    normalization_state.update(
        "lcdv2_hourly", "last_successful_full_run_timestamp", timestamp
    )
