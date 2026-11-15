# Research

Exploration of the F1 data. System decisions live in `docs/`, not here.

**Flow:** notebook → `FINDINGS.md` → `docs/DECISIONS.md` (if it changes the system) → code.

| Notebook | Question | Status |
|---|---|---|
| `02_raw_race_eda.ipynb` | What is in the raw race laps, and how do we see tyre degradation? | Done, frozen (EDA v1, 2026-11-14) |
| `data_ingestion.ipynb` | Trying the ingestion code | Done |
| `FastAPI_testing.ipynb` | First look at pace and degradation (before the pipeline) | Old |

**Reference notes:** [`fuel_correction.md`](fuel_correction.md): why and how lap times are corrected for fuel.
