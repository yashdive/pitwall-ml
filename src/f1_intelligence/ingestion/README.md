# src/f1_intelligence/ingestion/

**What this folder is:** step 1 of the pipeline. It downloads race data from FastF1 and stores it, unchanged, as Parquet files in `data/raw/`.

```text
FastF1 API ──fastf1_loader──→ SessionData (5 tables + metadata) ──data_writer──→ data/raw/…
                    backfill.py loops over many races and handles errors
```

## Files

| File | What it does |
|---|---|
| `fastf1_loader.py` | Fetches **one** race. A race is identified by `SessionKey(season, round, session)`, never by its name (names are ambiguous: "Spain" is two different races in 2026). Returns `SessionData`: the tables `laps`, `weather`, `results`, `track_status`, `race_control`, each with `Season`, `Round`, `Session` columns added, plus metadata (event name, download time, FastF1 version). Raises a clear error type for each kind of problem: `SessionNotFound` (skip it), `DataNotAvailable` (not published yet, try later), `RateLimited` (too many requests, wait), `IngestionError` (anything else). Also: `list_sessions(season)` (finished races of a season, from the official schedule) and `enable_cache` (where FastF1 keeps its download cache) |
| `data_writer.py` | Saves `SessionData` to `data/raw/<table>/season=…/round=…/session=…/data.parquet`. Writes each file safely (temporary file, then rename) and writes `metadata.json` **last**: a race only counts as stored once its metadata exists, so a crash never leaves a half-saved race that looks complete. Running it again skips races that are already stored |
| `backfill.py` | The `f1-backfill` command: downloads many races in one go (e.g. `f1-backfill --seasons 2022 2023 2024 2025`). Skips races already stored, so it can be stopped and restarted. Handles each error type differently and, with `--wait-on-rate-limit`, sleeps through the FastF1 limit (500 requests per hour) and carries on. Exit codes: 0 all done, 1 some failed, 2 stopped early |
| `__init__.py` | Marks the folder as a Python package (empty) |

## Good to know
- Settings: `configs/ingestion.yaml`.
- For **one new race** Dagster's `raw_race` asset calls this code. For **whole seasons** use `f1-backfill`: it runs in one process, so FastF1's rate limiter works properly.
- Tests: `tests/ingestion/`.
