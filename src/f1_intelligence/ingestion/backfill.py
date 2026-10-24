"""Ingest every finished session of one or more seasons into the raw layer.

    f1-backfill --seasons 2022 2023 2024 2025 --wait-on-rate-limit
    f1-backfill --seasons 2026 --sessions R Q FP2

Session types default to `backfill.sessions` in the config.
Safe to re-run: sessions already in the raw layer are skipped (unless
--overwrite), so an interrupted run resumes where it stopped.

Exit codes: 0 = complete, 1 = some sessions failed, 2 = stopped early on rate limit.
"""

import argparse
import logging
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

import fastf1

from f1_intelligence.config import load_ingestion_config
from f1_intelligence.ingestion.data_writer import ParquetWriter
from f1_intelligence.ingestion.fastf1_loader import (
    SESSION_CODES,
    DataNotAvailable,
    RateLimited,
    SessionKey,
    SessionNotFound,
    enable_cache,
    list_sessions,
    load_session,
)

log = logging.getLogger("f1_intelligence.backfill")


@dataclass
class BackfillReport:
    counts: Counter = field(default_factory=Counter)
    failed: list[SessionKey] = field(default_factory=list)
    pending: list[SessionKey] = field(default_factory=list)
    stopped_early: bool = False

    def __str__(self) -> str:
        lines = [", ".join(f"{k}={v}" for k, v in sorted(self.counts.items())) or "nothing to do"]
        if self.pending:
            lines.append(f"not available yet: {', '.join(map(str, self.pending))}")
        if self.failed:
            lines.append(f"FAILED: {', '.join(map(str, self.failed))}")
        if self.stopped_early:
            lines.append("stopped early on rate limit; re-run later to resume")
        return "\n".join(lines)


def backfill(
    keys: list[SessionKey],
    writer: ParquetWriter,
    overwrite: bool = False,
    rate_limit_wait_s: float | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> BackfillReport:
    """Ingest `keys` in order.

    On a rate limit: stop if `rate_limit_wait_s` is None, otherwise sleep that
    long and retry the same session. FastF1's limiter counts calls in-process,
    so waiting inside this process is the only correct way to resume; starting
    a fresh process would just bypass the courtesy limit.
    """
    report = BackfillReport()
    for i, key in enumerate(keys, start=1):
        prefix = f"[{i}/{len(keys)}] {key}"
        if writer.exists(key) and not overwrite:
            report.counts["skipped_existing"] += 1
            continue
        while True:
            try:
                writer.write(load_session(key), overwrite=overwrite)
                report.counts["written"] += 1
                log.info("%s written", prefix)
            except SessionNotFound as e:
                report.counts["not_found"] += 1
                log.warning("%s not found: %s", prefix, e)
            except DataNotAvailable as e:
                report.counts["not_available"] += 1
                report.pending.append(key)
                log.warning("%s not available: %s", prefix, e)
            except RateLimited as e:
                report.counts["rate_limited"] += 1
                if rate_limit_wait_s is None:
                    # Hammering the API makes it worse; stop and let the next run resume.
                    report.stopped_early = True
                    log.error("%s rate limited, stopping: %s", prefix, e)
                    return report
                log.warning("%s rate limited, sleeping %.0f min before retrying", prefix, rate_limit_wait_s / 60)
                sleep(rate_limit_wait_s)
                continue
            except Exception:
                report.counts["failed"] += 1
                report.failed.append(key)
                log.exception("%s failed", prefix)
            break
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seasons", type=int, nargs="+", required=True)
    parser.add_argument("--rounds", type=int, nargs="+", help="round numbers to ingest (default: all)")
    parser.add_argument("--sessions", nargs="+", choices=sorted(set(SESSION_CODES.values())),
                        help="session codes to ingest (default: backfill.sessions from config)")
    parser.add_argument("--config", default="configs/ingestion.yaml")
    parser.add_argument("--overwrite", action="store_true", default=None,
                        help="re-ingest sessions that already exist (default: from config)")
    parser.add_argument("--wait-on-rate-limit", action="store_true",
                        help="sleep and resume when the API rate limit is hit instead of stopping")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # set_log_level only affects FastF1's own handler; also stop its DEBUG records
    # propagating to our root handler, or every cache hit gets logged twice.
    fastf1.set_log_level("ERROR")
    logging.getLogger("fastf1").setLevel(logging.ERROR)
    logging.getLogger("fastf1").propagate = False

    config = load_ingestion_config(args.config)
    storage = config.storage
    overwrite = storage.overwrite if args.overwrite is None else args.overwrite
    sessions = args.sessions or config.backfill.sessions
    enable_cache(storage.cache_uri)
    writer = ParquetWriter(storage.raw_uri, storage.compression)

    keys = [
        key
        for season in args.seasons
        for key in list_sessions(season, sessions)
        if args.rounds is None or key.round in args.rounds
    ]
    log.info("%d sessions to consider (%s), raw layer at %s",
             len(keys), ", ".join(sessions) if sessions else "all types", storage.raw_uri)

    wait_s = config.backfill.rate_limit_wait_minutes * 60 if args.wait_on_rate_limit else None
    report = backfill(keys, writer, overwrite=overwrite, rate_limit_wait_s=wait_s)
    log.info("done: %s", report)
    if report.failed:
        return 1
    return 2 if report.stopped_early else 0


if __name__ == "__main__":
    raise SystemExit(main())
