# research/

**What this folder is:** exploration of the F1 data: notebooks where we look at the data, and the conclusions we drew. System decisions live in `docs/`, not here.

**Flow:** notebook → `FINDINGS.md` → `docs/DECISIONS.md` (if it changes the system) → code.

## Files

| File | What it is | Status |
|---|---|---|
| `02_raw_race_eda.ipynb` | The main exploration of the raw race laps (questions Q1–Q10): what each column means, missing data, track status, pit stops, tyres, weather, fuel, traffic, and how tyre degradation shows up. Starts with a column guide and a summary | Done, **frozen** (EDA v1, 2026-11-14, git tag `eda-v1`). New exploration goes in a new notebook |
| `FINDINGS.md` | The final conclusions of the exploration, one line each, written as "what we will do about it", with the notebook question it came from | Frozen with EDA v1 |
| `fuel_correction.md` | Reference note: why lap times must be corrected for fuel and how (with symbols and a worked example) | Reference |
| `LITERATURE.md` | Prior work worth learning from (TU Munich race simulation, RSRL), with space for reading notes | Open |
| `data_ingestion.ipynb` | Small notebook trying out the ingestion code (load a race, write it, query it) | Done |
| `FastAPI_testing.ipynb` | The very first look at pace and degradation, from before the pipeline existed | Old, kept for history |
| `archive/` | Older working copies of notebooks, kept so nothing is lost (see `archive/README.md`) | Archive |

## Good to know
- Notebooks run from this folder: paths like `../configs/ingestion.yaml` point to the project root.
- To see the notebook exactly as it was when frozen: `git checkout eda-v1 -- research/02_raw_race_eda.ipynb`.
