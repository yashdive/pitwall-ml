# configs/

**What this folder is:** the settings of the pipeline, in YAML files. The code reads its numbers and paths from here instead of having them written inside the code, so a setting can be changed (and recorded) without touching the code.

Relative paths in these files (like `data/raw`) are read from the project root, so the same file works from the command line, a notebook or Dagster.

## Files

| File | Used by | What it sets |
|---|---|---|
| `ingestion.yaml` | `f1-backfill`, Dagster `raw_race` and `new_races_sensor` | Where raw data and the FastF1 download cache go; which session types to download (only races, `R`, for now); which seasons the scheduler keeps up to date (2022–2025); how long to wait when the FastF1 rate limit is hit |
| `processing.yaml` | `f1-process`, Dagster `processed_laps` | Where the processed data goes; the version label (`v1`); the processing rules: traffic gap (1.0 s), how many laps after a safety car / red flag count as restart laps (3 / 4), the weather sensor jump limit (5 °C) |

## Good to know
- **Changing a rule in `processing.yaml` creates a new data version by itself.** The real version is `v1-<fingerprint>`, a short code computed from these rules plus the processing code. A new fingerprint means a new folder in `data/processed/`, and Dagster rebuilds every race there. The old version is never overwritten. See `docs/design/orchestration.md`.
- A typo in a setting name is rejected when the file is loaded (the code checks every key), instead of being silently ignored.
- The code that reads these files is `src/f1_intelligence/config.py`.
