import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from comfort_index_pipeline.config.settings import settings


class NormalizationState:
    """
    Manages normalization state for all datasets.
    Backed by a JSON file defined in settings.NORMALIZATION_STATE_FILE_PATH.
    """

    def __init__(self, state_file: Path = settings.NORMALIZATION_STATE_FILE_PATH):
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
            "tiger_geospatial_tracts": {
                "raw_year_normalized": None,
                "last_normalized": None,
                "last_successful_full_run_timestamp": None,
            },
            "lcdv2_hourly": {
                "years_normalized": [],
                "last_normalized": None,
                "last_successful_full_run_timestamp": None,
            },
            # Future normalized datasets will be added here:
            # "acs_5yr_normalized": {...},
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

    def mark_normalized_now(self, dataset: str) -> None:
        """Convenience method for timestamping normalization."""
        timestamp = datetime.now(timezone.utc).isoformat()
        self.update(dataset, "last_normalized", timestamp)


# Singleton instance used throughout the pipeline
normalization_state = NormalizationState()
