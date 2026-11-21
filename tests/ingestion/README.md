# tests/ingestion/

**What this folder is:** tests for `src/f1_intelligence/ingestion/` (downloading and storing raw races).

## Files

| File | What it checks |
|---|---|
| `test_fastf1_loader.py` | With a fake FastF1 session: tables come back as plain tables with `Season`/`Round`/`Session` columns; missing optional tables are recorded; missing laps or a future race raise `DataNotAvailable`; a non-existent race raises `SessionNotFound`; the list of finished races is right. Two `integration` tests use real FastF1 data (Spain 2024, and that "Spain" means Madrid in 2026) |
| `test_data_writer.py` | The folder layout; an existing race is skipped unless overwrite; a crash in the middle leaves the race "not stored" with no temporary files; DuckDB can read many races as one table |
| `test_backfill.py` | Already-stored races are skipped; each error type is handled correctly and the run continues; a rate limit stops the run, or waits and retries the same race |
| `__init__.py` | Marks the folder as a Python package (empty) |
