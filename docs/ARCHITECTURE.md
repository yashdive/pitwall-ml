# Architecture

How the system fits together. One section per component; updated with every component.
Why things are the way they are: `DECISIONS.md`. Detailed designs: `design/`.

```text
                          Dagster (orchestration): finds new races, runs each step,
                          records versions + lineage, rebuilds stale data
FastF1 API
   │  asset raw_race          (partition = one race, e.g. 2024-03-R)
   ▼
data/raw/<table>/season=/round=/session=/                 raw tables as FastF1 gives them
   │  asset processed_laps    (code version = v1-<fingerprint>)
   ▼
data/processed/v1-<fingerprint>/laps/season=/round=/session=/   one clean row per lap, with flags
   │  (next: features → model (MLflow) → API)
   ▼
```

## 1. Ingestion — `src/f1_intelligence/ingestion/`
- **Does:** downloads races from FastF1 and stores each table per race as Parquet.
- **Reads / writes:** FastF1 API → `data/raw/`
- **Run:** `f1-backfill --seasons 2022 2023 2024 2025` (config: `configs/ingestion.yaml`)
- **Files:** `fastf1_loader.py` (fetch one race), `data_writer.py` (write it safely), `backfill.py` (loop, retries, rate limit)
- **Safe to re-run:** races already stored are skipped; metadata is written last.

## 2. Processing — `src/f1_intelligence/processing/`
- **Does:** turns a raw race into one clean lap table: seconds, fixed data problems, weather, flags (`is_clean`, `pit_type`, `is_restart_lap`, `in_traffic`…). Keeps every lap. Design: `design/processed_layer.md`.
- **Reads / writes:** `data/raw/` → `data/processed/<version>/`
- **Run:** by Dagster, or by hand: `f1-process` (config: `configs/processing.yaml`)
- **Files:** `transforms.py` (the steps, one function each), `schema.py` (checks the output), `pipeline.py` (which races to build, safe writing, metadata)
- **Safe to re-run:** a race is rebuilt only if it is new or its raw data was re-ingested. A rule or code change = new fingerprint = new version folder.
- **Rule:** every column uses only the current and earlier laps (D18), so the same code can run live later.

## 3. Orchestration — `src/f1_intelligence/orchestration/`
- **Does:** runs the steps above as Dagster assets, one partition per race. A sensor adds new races every hour; data is rebuilt automatically when its raw input or its rules/code change. Design: `design/orchestration.md` (D19).
- **Run:** `DAGSTER_HOME=$PWD/.dagster dagster dev` → UI at http://localhost:3000
- **Files:** `definitions.py` (assets, sensor, resources); instance settings in `.dagster/dagster.yaml`
- **Versions:** the processed version is `<label>-<fingerprint>` of the rules + code (`processing/version.py`); each version has its own folder and is never overwritten.

## Shared
- `config.py`: typed config loading for every component
- `storage.py`: safe file writing and the folder layout
