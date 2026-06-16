import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from comfort_index_pipeline.config.settings import settings


class IngestionState:
    """
    Manages ingestion state for all datasets.
    Backed by a JSON file defined in settings.STATE_FILE_PATH.
    """

    def __init__(self, state_file: Path = settings.INGESTION_STATE_FILE_PATH):
        self.state_file = state_file
        self.state: Dict[str, Any] = self._load_state()

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _load_state(self) -> Dict[str, Any]:
        if not self.state_file.exists():
            return self._initialize_state()

        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # Corrupted state file → reset
            return self._initialize_state()

    def _initialize_state(self) -> Dict[str, Any]:
        state = {
            "lcdv2_station_metadata": {
                "last_ingested": None,
                "last_successful_full_run_timestamp": None,
            },
            "lcdv2_daily_prior_years": {
                "last_ingested_year": None,
                "last_ingested_file": None,
                "last_ingested": None,
                "last_successful_full_run_timestamp": None,
            },
            "acs_5yr": {
                "last_ingested_year": None,
                "last_ingested_variables": [],
                "last_ingested": None,
                "last_successful_full_run_timestamp": None,
            },
            "tiger_geospatial_tracts": {
                "last_ingested_year": None,
                "last_ingested_file": None,
                "last_ingested": None,
                "last_successful_full_run_timestamp": None,
            },
            "elevation_stations": {
                "last_ingested": None,
                "last_successful_full_run_timestamp": None,
                "last_ingested_count": None,
            },
            "elevation_tracts": {
                "last_ingested": None,
                "last_successful_full_run_timestamp": None,
                "last_ingested_count": None,
            },
        }
        self._write_state(state)
        return state

    def _write_state(self, state: Dict[str, Any]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=4)

    # -----------------------------
    # Public API
    # -----------------------------
    def get(self, dataset: str, key: str) -> Optional[Any]:
        return self.state.get(dataset, {}).get(key)

    def update(self, dataset: str, key: str, value: Any) -> None:
        if dataset not in self.state:
            self.state[dataset] = {}

        self.state[dataset][key] = value
        self._write_state(self.state)

    def mark_ingested_now(self, dataset: str) -> None:
        """Convenience method for timestamping ingestion."""
        timestamp = datetime.now(timezone.utc).isoformat()
        self.update(dataset, "last_ingested", timestamp)


# Singleton instance used throughout the pipeline
ingestion_state = IngestionState()
