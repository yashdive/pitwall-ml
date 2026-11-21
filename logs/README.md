# logs/

**What this folder is:** text output of long manual runs, kept so we can look back at what happened. Not in git (only this README is).

## Files

| File | What it is |
|---|---|
| `backfill_2022_2025.log` | First backfill attempt (all session types, 2022–2025) on 2026-10-08. Stopped after 30 sessions on the FastF1 limit of 500 requests per hour; this is why we switched to races only |
| `backfill_races_2022_2025.log` | The races-only backfill on 2026-10-08: 92 races, waited out the rate limit twice by itself, no failures |
