import dagster as dg
import pytest
import yaml

from f1_intelligence.ingestion.fastf1_loader import SessionKey
from f1_intelligence.orchestration.definitions import (
    ProjectConfig,
    defs,
    processed_laps,
    race_partition,
    raw_race,
    session_key,
)
from tests.conftest import METADATA, RULES, one_driver, raw_laps, raw_weather

PARTITION = "2024-03-R"


def test_definitions_load():
    dg.Definitions.validate_loadable(defs)


def test_partition_names_round_trip():
    key = SessionKey(2024, 3, "R")
    assert race_partition(key) == PARTITION
    assert session_key(PARTITION) == key


@pytest.fixture
def project(tmp_path, write_raw_race):
    """Temporary configs pointing at a temporary raw layer that already holds one race."""
    raw_uri = write_raw_race(raw_laps(one_driver(["1", "1", "4", "41", "1", "1"])), raw_weather([900], [30.0]))
    ingestion = {"storage": {"raw_uri": str(raw_uri), "cache_uri": str(tmp_path / "cache")},
                 "backfill": {"sessions": ["R"], "seasons": [2024]}}
    processing = {"version": "v1", "raw_uri": str(raw_uri), "processed_uri": str(tmp_path / "processed"),
                  "rules": RULES.model_dump()}
    (tmp_path / "ingestion.yaml").write_text(yaml.safe_dump(ingestion))
    (tmp_path / "processing.yaml").write_text(yaml.safe_dump(processing))
    return ProjectConfig(ingestion_config=str(tmp_path / "ingestion.yaml"),
                         processing_config=str(tmp_path / "processing.yaml"))


def test_raw_then_processed_for_one_race(project):
    instance = dg.DagsterInstance.ephemeral()
    instance.add_dynamic_partitions("races", [PARTITION])

    result = dg.materialize([raw_race, processed_laps], partition_key=PARTITION,
                            instance=instance, resources={"project": project})
    assert result.success

    raw_event, processed_event = (result.asset_materializations_for_node(n)[0]
                                  for n in ("raw_race", "processed_laps"))
    assert raw_event.metadata["downloaded_now"].value is False        # already stored: no API call
    assert raw_event.tags["dagster/data_version"] == METADATA["ingested_at_utc"]
    assert processed_event.metadata["status"].value == "written"
    assert processed_event.metadata["rows"].value == 6
    assert processed_event.metadata["processing_version"].text.startswith("v1-")
