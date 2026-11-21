# tests/orchestration/

**What this folder is:** tests for `src/f1_intelligence/orchestration/` (the Dagster setup).

## Files

| File | What it checks |
|---|---|
| `test_definitions.py` | Dagster can load all the definitions; race partition names convert both ways (`2024-03-R` ↔ season 2024, round 3, race); a real Dagster run, in a temporary Dagster instance with temporary folders, builds `raw_race` (without downloading, since the race is already stored) and then `processed_laps`, and records the right data version and details |
| `__init__.py` | Marks the folder as a Python package (empty) |
