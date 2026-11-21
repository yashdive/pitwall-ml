# tests/processing/

**What this folder is:** tests for `src/f1_intelligence/processing/` (the processed lap table).

## Files

| File | What it checks |
|---|---|
| `test_transforms.py` | Each processing step with small hand-made laps: times become seconds and `"None"` compounds become missing; track-status flags by digit (`"1254"` = yellow + SC + red); `pit_type` for red-flag, safety-car and normal stops; exactly 3 restart laps after a SC and 4 after a red flag; gap to the car ahead (leader, negative gap, missing position); weather never comes from after the lap started and sensor jumps are dropped; every reason a lap is not clean; the full table passes the schema and bad values are rejected. **Past-only test (D18):** a race cut at lap 6 gives exactly the same rows for laps 1–6 as the full race |
| `test_pipeline.py` | The versioned folder and metadata; a second run does nothing; a re-downloaded race is rebuilt; data that breaks the schema is never written; only race sessions are listed; **a rule change gives a new version folder and leaves the old one untouched**. One `integration` test on real data: Melbourne 2023 (three red flags) |
| `__init__.py` | Marks the folder as a Python package (empty) |
