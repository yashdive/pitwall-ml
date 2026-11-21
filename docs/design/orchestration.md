# Design: orchestration, versions and lineage

**Status:** built 2026-11-15
**Decision:** D19

## 1. What and why
The pipeline runs as **Dagster assets**. Dagster decides what needs to run, records every build with its versions and inputs, finds new races, and rebuilds data by itself when the data it depends on or the code that makes it changes. MLflow (with the first model) records which data each model was trained on.

We use proven tools here because this is meant to become a live system: hand-built scheduling and version tracking is where such systems quietly break. Our own code stays the core logic (loading, transforms, schema checks); Dagster only calls it.

## 2. The graph

```text
raw_race ──→ processed_laps ──→ (next: degradation_features ──→ degradation_model)
```

- **Partition = one race**, key `"<season>-<round>-<session>"`, e.g. `2024-03-R`.
- `new_races_sensor` (every hour): every finished race in `configs/ingestion.yaml → backfill.seasons` without a partition gets one, plus a run of `raw_race`.
- `raw_race`: downloads the race only if it is not stored yet. Its **data version** is the download time (`ingested_at_utc`).
- `processed_laps`: builds the race (`process_race`). Its **code version** is the processed version (`v1-<fingerprint>`).
- Automation (`eager | code_version_changed`): a race of `processed_laps` is rebuilt when its raw race gets a new data version, or when the code version changes.

## 3. Versions
- **Processed version** = `<label>-<fingerprint>`, fingerprint = hash of the rules + `transforms.py` + `schema.py` (`processing/version.py`).
- Each version is its own folder: `data/processed/v1-1d39cdd8/…`. A rule or code change → new fingerprint → new folder; **old folders are never touched**, so a model's training data never changes under it.
- Dagster stores, for every build: code version, data version, upstream data versions, metadata (rows, clean share, rules, raw download time, code commit).

## 4. What happens when something changes

| Change | What Dagster does |
|---|---|
| New race finished | sensor adds the partition and runs `raw_race` → `processed_laps` follows automatically |
| Race re-downloaded | new data version of `raw_race` → `processed_laps` for that race is stale → rebuilt |
| Processing rule or code | new code version → every race of `processed_laps` is stale → rebuilt into the new folder |
| (later) feature rule | features stale → rebuilt; model gets a new candidate run (compared before switching, D16) |

## 5. Safety
- **Retries only for retriable errors:** `RateLimited` and `DataNotAvailable` → retry in 1 hour (up to 3 times). Any other error fails at once (D5). A bug is never retried as if it were a rate limit.
- **One FastF1 download at a time:** pool `fastf1_api` with limit 1 (`.dagster/dagster.yaml`). Bulk downloads of whole seasons still use `f1-backfill`: one process, so FastF1's own rate limiter works.
- **History is persistent:** `DAGSTER_HOME=.dagster` (SQLite locally; Postgres in production).

## 6. Run
```bash
DAGSTER_HOME=$PWD/.dagster dagster dev      # UI at http://localhost:3000
```
The CLIs `f1-backfill` and `f1-process` still work for manual runs; they use the same code and the same version folders.

## 7. Not in this step
MLflow (comes with the first model), the features and model assets, alerts, Postgres for production.
