import json
from pathlib import Path

import pandas as pd
import pytest

from f1_intelligence.config import ProcessingConfig, load_processing_config
from f1_intelligence.ingestion.fastf1_loader import SessionKey
from f1_intelligence.processing import pipeline
from f1_intelligence.processing.pipeline import list_raw_races, output_paths, process_race
from f1_intelligence.processing.version import processed_version
from tests.conftest import METADATA, RULES, one_driver, raw_laps, raw_weather

KEY = SessionKey(2024, 3, "R")


def make_config(raw_uri, tmp_path) -> ProcessingConfig:
    return ProcessingConfig(version="v1", raw_uri=raw_uri, processed_uri=tmp_path / "processed", rules=RULES)


@pytest.fixture
def race(write_raw_race, tmp_path):
    raw_uri = write_raw_race(raw_laps(one_driver(["1"] * 5)), raw_weather([900], [30.0]))
    return make_config(raw_uri, tmp_path)


def test_writes_versioned_layout_with_metadata(race):
    assert process_race(KEY, race)["status"] == "written"

    data_path, meta_path = output_paths(race, KEY)
    assert f"processed/{processed_version(race)}/laps/season=2024/round=3/session=R" in data_path.as_posix()
    assert len(pd.read_parquet(data_path)) == 5
    meta = json.loads(meta_path.read_text())
    assert meta["processing_version"] == processed_version(race)
    assert meta["raw_ingested_at_utc"] == METADATA["ingested_at_utc"]
    assert meta["rules"]["traffic_gap_s"] == 1.0


def test_second_run_does_nothing(race):
    process_race(KEY, race)
    assert process_race(KEY, race)["status"] == "up_to_date"


def test_reingested_raw_race_is_rebuilt(race, write_raw_race):
    process_race(KEY, race)
    write_raw_race(raw_laps(one_driver(["1"] * 6)), raw_weather([900], [30.0]),
                   {**METADATA, "ingested_at_utc": "2026-02-01T00:00:00+00:00"})

    assert process_race(KEY, race)["status"] == "written"
    assert len(pd.read_parquet(output_paths(race, KEY)[0])) == 6


def test_broken_data_writes_nothing(race, monkeypatch):
    real_build = pipeline.build_processed_laps

    def build_with_a_bad_row(*args, **kwargs):
        df = real_build(*args, **kwargs)
        df.loc[0, "lap_number"] = 0  # lap 0 does not exist: breaks the schema
        return df

    monkeypatch.setattr(pipeline, "build_processed_laps", build_with_a_bad_row)
    with pytest.raises(Exception):
        process_race(KEY, race)
    data_path, meta_path = output_paths(race, KEY)
    assert not data_path.exists() and not meta_path.exists()


def test_lists_only_configured_sessions(write_raw_race, tmp_path):
    raw_uri = write_raw_race(raw_laps(one_driver(["1"] * 3)), raw_weather([900], [30.0]))
    write_raw_race(raw_laps(one_driver(["1"] * 3)), raw_weather([900], [30.0]), {**METADATA, "session": "Q"})
    assert list_raw_races(raw_uri, ["R"]) == [KEY]


def test_repo_config_is_valid():
    config = load_processing_config("configs/processing.yaml")
    assert processed_version(config).startswith(config.version + "-")


def test_rule_change_gives_a_new_version_folder(race):
    changed = race.model_copy(update={"rules": RULES.model_copy(update={"traffic_gap_s": 1.5})})
    assert processed_version(changed) != processed_version(race)
    assert processed_version(race.model_copy()) == processed_version(race)  # same rules → same version

    process_race(KEY, race)
    assert process_race(KEY, changed)["status"] == "written"   # new folder: built again
    assert output_paths(race, KEY)[0].exists()                 # old version untouched


# ------------------------------------------------------------------ real data (needs data/raw)

REAL_RAW = Path("data/raw")


@pytest.mark.integration
@pytest.mark.skipif(not (REAL_RAW / "laps/season=2023/round=3").exists(), reason="needs raw Melbourne 2023")
def test_melbourne_2023_red_flags(tmp_path):
    """The EDA's hardest race: three red flags, free tyre changes, restart laps."""
    config = load_processing_config("configs/processing.yaml").model_copy(update={"processed_uri": tmp_path})
    process_race(SessionKey(2023, 3, "R"), config)
    df = pd.read_parquet(output_paths(config, SessionKey(2023, 3, "R"))[0]).set_index(["driver", "lap_number"])

    assert df.loc[("VER", 8), "pit_type"] == "red_flag"       # red flag: into the pit lane
    assert df.loc[("VER", 9), "pit_type"] == "red_flag"       # restart from the pit lane
    assert df.loc[("VER", 10), "is_restart_lap"]
    assert not df.loc[("HAM", 10), "is_clean"]                # green, not a pit lap, but 123 s
    assert df.loc[("VER", 12), "is_restart_lap"] and not df.loc[("VER", 13), "is_restart_lap"]
