# src/f1_intelligence/orchestration/

**What this folder is:** the part that **runs** the pipeline, using Dagster. Dagster treats each step's output as an **asset** (a piece of data that should exist), knows which asset is made from which, and keeps track of what is built, what is out of date and what happened in every run.

```text
raw_race ──→ processed_laps ──→ (next: features → model)
   one partition per race, e.g. "2024-03-R"
```

## Files

| File | What it does |
|---|---|
| `definitions.py` | Everything Dagster needs: **`raw_race`** (asset: the raw data of one race; downloads only if not stored yet; its *data version* is the download time), **`processed_laps`** (asset: the clean lap table of one race; its *code version* is the processed version `v1-<fingerprint>`; rebuilds by itself when its raw race is re-downloaded or the rules/code change), **`new_races_sensor`** (every hour: adds any newly finished race of the configured seasons and starts its download), **`automation_sensor`** (every ~30 s: checks each asset's automatic-rebuild rule and starts the runs; switched on from the code, because Dagster ships it switched off), **`ProjectConfig`** (tells the assets where the config files are; tests point it at temporary folders) |
| `__init__.py` | Marks the folder as a Python package (empty) |

## How to run
```bash
cd ~/users/yash/personal/F1
DAGSTER_HOME=$PWD/.dagster dagster dev      # then open http://localhost:3000
```
- **Assets** page: `raw_race`, `processed_laps`, each with a grid of 92 races; click a race to see every build and its details.
- **Lineage**: the graph of which asset is made from which.

## Good to know
- Only "rate limited" and "data not published yet" are retried (after 1 hour). Any other error fails at once, so bugs are not hidden.
- One FastF1 download at a time (pool `fastf1_api`, set in `.dagster/dagster.yaml`).
- Dagster's history (runs, versions, partitions) is stored in `.dagster/` (see its README).
- Full explanation: `docs/design/orchestration.md`, decision D19.
- Tests: `tests/orchestration/`.
