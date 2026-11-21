# src/f1_intelligence/

**What this folder is:** the main Python package. Each subfolder is one step of the pipeline; the two files at the top are shared by all steps.

```text
FastF1 ──ingestion──→ data/raw ──processing──→ data/processed/<version>
                    (orchestration runs both, per race, with Dagster)
```

## Contents

| Item | What it is |
|---|---|
| `ingestion/` | Downloads races from FastF1 and stores them as raw Parquet files (see its README) |
| `processing/` | Turns a raw race into one clean table of laps with flags (see its README) |
| `orchestration/` | Runs the steps with Dagster: finds new races, rebuilds data that is out of date, records history (see its README) |
| `config.py` | Reads the YAML files in `configs/` into typed Python objects. Rejects unknown or wrong settings, and turns relative paths into full paths from the project root |
| `storage.py` | Two small helpers every step uses: `atomic_write` (write to a temporary file, then rename, so nobody ever sees a half-written file) and `partition_dir` (the `table/season=…/round=…/session=…` folder layout) |
| `__init__.py` | Marks the folder as a Python package (empty) |

## Good to know
- Next folders to come: `features/` and `models/` (the degradation model), then `serving/` (the API).
