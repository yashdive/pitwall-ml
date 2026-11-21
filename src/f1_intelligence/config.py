"""Typed project configuration loaded from YAML.

Relative paths in the YAML are resolved against the project root (the parent
of the `configs/` directory), so the same config works from the CLI, from
notebooks in `research/`, and inside a container.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class StorageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_uri: Path
    cache_uri: Path
    compression: str = "zstd"
    overwrite: bool = False


class BackfillConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sessions: list[str] | None = None  # session codes; None = all
    seasons: list[int] = []  # seasons the scheduler keeps up to date (2026 deferred, D14)
    rate_limit_wait_minutes: float = Field(default=61, gt=0)


class IngestionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage: StorageConfig
    backfill: BackfillConfig = BackfillConfig()


def load_ingestion_config(path: str | Path = "configs/ingestion.yaml") -> IngestionConfig:
    path = Path(path).resolve()
    with path.open() as f:
        config = IngestionConfig.model_validate(yaml.safe_load(f))

    root = path.parent.parent
    storage = config.storage
    storage.raw_uri = _resolve(root, storage.raw_uri)
    storage.cache_uri = _resolve(root, storage.cache_uri)
    return config


class ProcessingRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    traffic_gap_s: float = Field(gt=0)
    restart_laps_after_sc_vsc: int = Field(ge=0)
    restart_laps_after_red_flag: int = Field(ge=0)
    max_track_temp_jump_c: float = Field(gt=0)
    weather_before_start_s: float = Field(ge=0)


class ProcessingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    raw_uri: Path
    processed_uri: Path
    compression: str = "zstd"
    sessions: list[str] = ["R"]
    rules: ProcessingRules


def load_processing_config(path: str | Path = "configs/processing.yaml") -> ProcessingConfig:
    path = Path(path).resolve()
    with path.open() as f:
        config = ProcessingConfig.model_validate(yaml.safe_load(f))

    root = path.parent.parent
    config.raw_uri = _resolve(root, config.raw_uri)
    config.processed_uri = _resolve(root, config.processed_uri)
    return config


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p).resolve()
