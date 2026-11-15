"""The pipeline as Dagster assets (docs/design/orchestration.md).

    DAGSTER_HOME=$PWD/.dagster dagster dev      # from the project root; UI at http://localhost:3000

Assets (each partition = one race, e.g. "2024-03-R"):

    raw_race  ──→  processed_laps  ──→  (next: features → model)

- `new_races_sensor` adds a partition for every finished race in the configured
  seasons and asks for its raw download.
- `processed_laps` rebuilds a race by itself when its raw data changes (new data
  version) or when the processing rules/code change (new code version).
"""

import json
from pathlib import Path

import dagster as dg

from f1_intelligence.config import load_ingestion_config, load_processing_config
from f1_intelligence.ingestion.data_writer import ParquetWriter
from f1_intelligence.ingestion.fastf1_loader import (
    DataNotAvailable,
    RateLimited,
    SessionKey,
    enable_cache,
    list_sessions,
    load_session,
)
from f1_intelligence.processing.pipeline import process_race
from f1_intelligence.processing.version import processed_version

PROJECT_ROOT = Path(__file__).resolve().parents[3]

RACES = dg.DynamicPartitionsDefinition(name="races")


def race_partition(key: SessionKey) -> str:
    return f"{key.season}-{key.round:02d}-{key.session}"


def session_key(partition: str) -> SessionKey:
    season, rnd, session = partition.split("-")
    return SessionKey(int(season), int(rnd), session)


class ProjectConfig(dg.ConfigurableResource):
    """Where the YAML configs live. Tests point these at temporary folders."""

    ingestion_config: str = str(PROJECT_ROOT / "configs/ingestion.yaml")
    processing_config: str = str(PROJECT_ROOT / "configs/processing.yaml")

    def ingestion(self):
        return load_ingestion_config(self.ingestion_config)

    def processing(self):
        return load_processing_config(self.processing_config)


# --------------------------------------------------------------------------- assets

@dg.asset(
    partitions_def=RACES,
    group_name="ingestion",
    code_version="raw-1",
    pool="fastf1_api",  # at most one download at a time (pool limit set in .dagster/dagster.yaml)
)
def raw_race(context: dg.AssetExecutionContext, project: ProjectConfig) -> dg.MaterializeResult:
    """Raw FastF1 tables of one race. Downloads only if the race is not stored yet."""
    key = session_key(context.partition_key)
    config = project.ingestion()
    writer = ParquetWriter(config.storage.raw_uri, config.storage.compression)

    downloaded = False
    if not writer.exists(key):
        enable_cache(config.storage.cache_uri)
        try:
            writer.write(load_session(key))
        except (RateLimited, DataNotAvailable) as e:
            # Only these two are worth waiting for (D5). Any other error fails straight
            # away, so a bug is never retried as if it were a rate limit.
            raise dg.RetryRequested(max_retries=3, seconds_to_wait=3600) from e
        downloaded = True

    meta = json.loads(writer.metadata_path(key).read_text(encoding="utf-8"))
    return dg.MaterializeResult(
        # The raw data's version is when it was downloaded: a re-download makes
        # everything built from it out of date.
        data_version=dg.DataVersion(meta["ingested_at_utc"]),
        metadata={
            "event": meta.get("event_name", "unknown"),
            "downloaded_now": downloaded,
            "ingested_at_utc": meta["ingested_at_utc"],
            "missing_tables": ", ".join(meta.get("missing_tables", [])) or "none",
            "fastf1_version": meta.get("fastf1_version", "unknown"),
        },
    )


@dg.asset(
    partitions_def=RACES,
    deps=[raw_race],
    group_name="processing",
    # The fingerprint of the rules + processing code: when it changes, Dagster marks
    # every race as out of date and rebuilds it into the new version folder.
    code_version=processed_version(load_processing_config(PROJECT_ROOT / "configs/processing.yaml")),
    automation_condition=dg.AutomationCondition.eager() | dg.AutomationCondition.code_version_changed(),
)
def processed_laps(context: dg.AssetExecutionContext, project: ProjectConfig) -> dg.MaterializeResult:
    """One clean row per lap for one race, with flags (docs/design/processed_layer.md)."""
    config = project.processing()
    result = process_race(session_key(context.partition_key), config)
    return dg.MaterializeResult(
        metadata={
            "status": result["status"],
            "processing_version": result["processing_version"],
            "rows": result["rows"],
            "clean_share": result["clean_share"],
            "in_traffic_share": result["in_traffic_share"],
            "laps_without_weather": result["laps_without_weather"],
            "raw_ingested_at_utc": result["raw_ingested_at_utc"],
            "code_commit": result["code_commit"] or "unknown",
            "rules": dg.MetadataValue.json(result["rules"]),
        },
    )


# --------------------------------------------------------------------------- new races

@dg.sensor(
    asset_selection=[raw_race],
    minimum_interval_seconds=3600,
    default_status=dg.DefaultSensorStatus.RUNNING,
)
def new_races_sensor(context: dg.SensorEvaluationContext, project: ProjectConfig) -> dg.SensorResult:
    """Every hour: any finished race in the configured seasons without a partition gets one and a run."""
    config = project.ingestion()
    enable_cache(config.storage.cache_uri)
    finished = [
        race_partition(key)
        for season in config.backfill.seasons
        for key in list_sessions(season, config.backfill.sessions)
    ]
    known = set(context.instance.get_dynamic_partitions(RACES.name))
    new = [p for p in finished if p not in known]
    return dg.SensorResult(
        run_requests=[dg.RunRequest(partition_key=p, asset_selection=[raw_race.key]) for p in new],
        dynamic_partitions_requests=[RACES.build_add_request(new)] if new else [],
    )


defs = dg.Definitions(
    assets=[raw_race, processed_laps],
    sensors=[new_races_sensor],
    resources={"project": ProjectConfig()},
)
