"""Raw races → processed lap table, one file per race.

    f1-process                      # every raw race that is new or changed
    f1-process --seasons 2024       # only some races
    f1-process --force              # rebuild even if up to date

Output, in the folder of the current version (label + fingerprint, see version.py):

    data/processed/v1-3f9a1c2e/laps/season=2024/round=3/session=R/data.parquet
    data/processed/v1-3f9a1c2e/metadata/season=2024/round=3/session=R/metadata.json

A race is rebuilt when it has no output in this version yet or its raw data was
re-ingested. A rule or code change gives a new version folder, so every race is
built again there. The metadata file is written last: a race without it counts as
not processed.

Normally Dagster runs this (f1_intelligence.orchestration); the CLI is for manual runs.

Exit codes: 0 = all fine, 1 = some races failed.
"""

import argparse
import json
import logging
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from f1_intelligence.config import ProcessingConfig, load_processing_config
from f1_intelligence.ingestion.fastf1_loader import SessionKey
from f1_intelligence.processing.schema import PROCESSED_LAPS_SCHEMA
from f1_intelligence.processing.transforms import build_processed_laps
from f1_intelligence.processing.version import output_root, processed_version
from f1_intelligence.storage import atomic_write, partition_dir

log = logging.getLogger("f1_intelligence.process")


def list_raw_races(raw_uri: Path, sessions: list[str]) -> list[SessionKey]:
    """Every session in the raw layer (its metadata file marks it as complete)."""
    keys = []
    for path in Path(raw_uri).glob("metadata/season=*/round=*/session=*/metadata.json"):
        meta = json.loads(path.read_text(encoding="utf-8"))
        if meta["session"] in sessions:
            keys.append(SessionKey(int(meta["season"]), int(meta["round"]), meta["session"]))
    return sorted(keys, key=lambda k: (k.season, k.round, k.session))


def read_raw_race(raw_uri: Path, key: SessionKey) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    def folder(table: str) -> Path:
        return partition_dir(raw_uri, table, key.season, key.round, key.session)

    laps = pd.read_parquet(folder("laps") / "data.parquet")
    weather_file = folder("weather") / "data.parquet"
    weather = pd.read_parquet(weather_file) if weather_file.exists() else pd.DataFrame()
    metadata = json.loads((folder("metadata") / "metadata.json").read_text(encoding="utf-8"))
    return laps, weather, metadata


def output_paths(config: ProcessingConfig, key: SessionKey) -> tuple[Path, Path]:
    root = output_root(config)
    data = partition_dir(root, "laps", key.season, key.round, key.session) / "data.parquet"
    meta = partition_dir(root, "metadata", key.season, key.round, key.session) / "metadata.json"
    return data, meta


def is_up_to_date(meta_path: Path, raw_metadata: dict) -> bool:
    """Processed output exists and was built from this exact raw ingestion."""
    if not meta_path.exists():
        return False
    built_from = json.loads(meta_path.read_text(encoding="utf-8")).get("raw_ingested_at_utc")
    return built_from == raw_metadata.get("ingested_at_utc")


def process_race(key: SessionKey, config: ProcessingConfig, force: bool = False) -> dict:
    """Build, check and write one race.

    Returns the race's metadata plus "status": "written" or "up_to_date".
    """
    laps_raw, weather_raw, raw_meta = read_raw_race(config.raw_uri, key)
    data_path, meta_path = output_paths(config, key)
    if not force and is_up_to_date(meta_path, raw_meta):
        return {"status": "up_to_date", **json.loads(meta_path.read_text(encoding="utf-8"))}

    laps = build_processed_laps(laps_raw, weather_raw, raw_meta, config.rules)
    PROCESSED_LAPS_SCHEMA.validate(laps)  # raises on any broken rule: nothing is written

    meta_path.unlink(missing_ok=True)  # un-commit first, so a crash never leaves a "done" marker
    atomic_write(data_path, lambda tmp: laps.to_parquet(tmp, index=False, compression=config.compression))
    metadata = {
        "season": key.season,
        "round": key.round,
        "session": key.session,
        "processing_version": processed_version(config),
        "rules": config.rules.model_dump(),
        "raw_ingested_at_utc": raw_meta.get("ingested_at_utc"),
        "code_commit": _code_commit(),
        "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": len(laps),
        "clean_share": round(float(laps["is_clean"].mean()), 4),
        "in_traffic_share": round(float(laps["in_traffic"].mean()), 4),
        "laps_without_weather": int(laps["track_temp_c"].isna().sum()),
    }
    text = json.dumps(metadata, indent=2, ensure_ascii=False)
    atomic_write(meta_path, lambda tmp: tmp.write_text(text, encoding="utf-8"))
    return {"status": "written", **metadata}


def _code_commit() -> str | None:
    """Git commit of the code that built the data; '+dirty' if there were uncommitted changes."""
    try:
        here = Path(__file__).parent
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=here,
                                capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=here,
                               capture_output=True, text=True, check=True).stdout.strip()
        return commit + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="configs/processing.yaml")
    parser.add_argument("--seasons", type=int, nargs="+")
    parser.add_argument("--rounds", type=int, nargs="+")
    parser.add_argument("--force", action="store_true", help="rebuild races even if up to date")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    config = load_processing_config(args.config)
    keys = [
        k for k in list_raw_races(config.raw_uri, config.sessions)
        if (args.seasons is None or k.season in args.seasons) and (args.rounds is None or k.round in args.rounds)
    ]
    log.info("%d races, writing to %s", len(keys), output_root(config))

    counts, failed = Counter(), []
    for i, key in enumerate(keys, start=1):
        try:
            result = process_race(key, config, force=args.force)["status"]
            counts[result] += 1
            if result == "written":
                log.info("[%d/%d] %s written", i, len(keys), key)
        except Exception:
            counts["failed"] += 1
            failed.append(key)
            log.exception("[%d/%d] %s failed", i, len(keys), key)

    log.info("done: %s", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "nothing to do")
    if failed:
        log.error("failed: %s", ", ".join(map(str, failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
