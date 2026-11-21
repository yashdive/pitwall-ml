# data/

**What this folder is:** all the data of the project, stored as files. It is **not in git** (too big, and it can always be rebuilt), only this README is.

## Folders

| Folder | What it holds | Made by | Can I delete it? |
|---|---|---|---|
| `raw/` | The race data exactly as FastF1 gives it, one Parquet file per table per race: `raw/<table>/season=2024/round=3/session=R/data.parquet`. Tables: `laps`, `weather`, `results`, `track_status`, `race_control`, plus a `metadata/…/metadata.json` per race | `f1-backfill` or Dagster `raw_race` | Only if you are ready to download it again (about 3.5 hours for 92 races, because of the FastF1 rate limit) |
| `processed/` | One clean table of laps per race, with flags (`is_clean`, `pit_type`, …). Each version has its own folder, e.g. `processed/v1-1d39cdd8/laps/season=2024/round=3/session=R/data.parquet` | `f1-process` or Dagster `processed_laps` | Yes: rebuilds from raw in about 5 seconds |
| `cache/` | FastF1's download cache (raw web responses). Makes repeat downloads instant | FastF1 | Yes: you only lose speed |

## Good to know
- **Raw is never changed** by any later step. Everything else is built from it.
- **A processed version folder is never changed after it is built.** A new rule or code change gives a new folder. This keeps the exact data a model was trained on.
- Folder names like `season=2024` are on purpose: tools like DuckDB and pandas read them as columns, so all races can be queried as one table:
  ```python
  import duckdb
  duckdb.sql("SELECT * FROM read_parquet('data/processed/v1-1d39cdd8/laps/**/*.parquet')").df()
  ```
- Column meanings of the processed table: `docs/design/processed_layer.md`.
