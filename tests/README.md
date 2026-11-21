# tests/

**What this folder is:** automatic checks that the code does what it should. Each subfolder tests the matching folder in `src/f1_intelligence/`.

## Run them
```bash
cd ~/users/yash/personal/F1
pytest -q                    # all fast tests (no internet, ~2 s)
pytest -q -m integration     # also the tests that use real data (FastF1 cache or data/raw)
pytest -q tests/processing   # only one folder
```

## Contents

| Item | What it is |
|---|---|
| `ingestion/` | Tests for downloading and storing raw races (see its README) |
| `processing/` | Tests for the processed lap table (see its README) |
| `orchestration/` | Tests for the Dagster setup (see its README) |
| `test_config.py` | The YAML configs load correctly, relative paths become full paths, and a typo in a setting is rejected |
| `conftest.py` | Shared helpers used by many tests: builders for small **hand-made raw races** (a few laps with chosen track statuses, pit stops, weather…) and a fixture that writes such a race into a temporary raw folder. pytest loads this file automatically |
| `__init__.py` | Marks the folder as a Python package (empty) |

## Good to know
- Fast tests never use the internet or the real `data/` folder: they build tiny fake races in temporary folders.
- Tests marked `integration` use real data and are skipped by default.
- A test name says what it proves, e.g. `test_adding_later_laps_does_not_change_earlier_rows`.
