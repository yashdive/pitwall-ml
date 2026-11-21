# src/f1_intelligence/processing/

**What this folder is:** step 2 of the pipeline. It turns one raw race into **one clean table of laps**: times in seconds, data problems fixed, weather attached, and flags that say what happened on each lap (pit stop, safety car, restart, traffic, clean…). Every lap is kept; models choose their laps later.

```text
data/raw/<race> ──transforms (step by step)──→ schema check ──→ data/processed/<version>/laps/<race>
```

## Files

| File | What it does |
|---|---|
| `transforms.py` | The processing steps, one small function each, run in order by `build_processed_laps`: convert units and types → add race name → lap flags (first lap, pit in/out, wet tyre…) → track-status flags (safety car, VSC, red flag, yellow) → `pit_type` (normal / under SC-VSC / red flag) → restart laps (3 laps after a SC/VSC, 4 after a red flag) → gap to the car ahead and `in_traffic` → weather (last trusted reading **before** the lap started) → `is_clean`. **Rule (D18):** every column uses only the current and earlier laps, so the same code can later run live, lap by lap |
| `schema.py` | The rules the output must follow (the "data contract"): every column with its type and allowed range, e.g. clean laps between 60 and 200 s, tyre age ≥ 1, one row per driver per lap. If a race breaks a rule, the pipeline stops and writes nothing |
| `pipeline.py` | The `f1-process` command and `process_race`: finds the raw races, skips races already built from the same raw download, runs the transforms, checks the schema, writes the Parquet file and then `metadata.json` (version, rules, raw download time, code commit, row count, share of clean laps) |
| `version.py` | Works out the version of the processed data: `<label>-<fingerprint>`, e.g. `v1-1d39cdd8`. The fingerprint is a short code computed from the rules (`configs/processing.yaml`) and the code in `transforms.py` and `schema.py`. Change any of them and the version changes by itself, so the data goes to a new folder and the old one stays untouched |
| `__init__.py` | Marks the folder as a Python package (empty) |

## Good to know
- Settings: `configs/processing.yaml`. Full design with every column: `docs/design/processed_layer.md`.
- Normally Dagster runs this (asset `processed_laps`). By hand: `f1-process` (add `--force` to rebuild).
- Tests: `tests/processing/`.
