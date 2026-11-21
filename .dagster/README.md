# .dagster/

**What this folder is:** Dagster's home (`DAGSTER_HOME`). Dagster keeps its memory here: every run, every build of every race, versions, partitions, sensor checks and logs. You look at this through the Dagster web page, not by opening the files.

Only `dagster.yaml` and this README are in git; the history is local.

## Files

| Item | What it is |
|---|---|
| `dagster.yaml` | Settings of this Dagster instance: at most **one** FastF1 download at a time (pool limit 1) and telemetry off |
| `storage/`, `history/`, `schedules/`, `logs/` | Dagster's own databases (SQLite files) and logs. Created when Dagster runs |

## Good to know
- Always start Dagster with `DAGSTER_HOME=$PWD/.dagster` from the project root, otherwise it uses a temporary folder and forgets everything when it stops.
- In production this history moves to a Postgres database; only `dagster.yaml` changes.
- Deleting the history does not delete any data in `data/`; Dagster just forgets what it built (it can rebuild or re-register).
