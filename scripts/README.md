# scripts/

**What this folder is:** one-off helper scripts that are not part of the data pipeline itself.

## Files

| File | What it does | How to run |
|---|---|---|
| `setup_github_tracker.sh` | Creates the project tracker on GitHub: labels (`data`, `model`, `infra`, …), milestones (v0.2 Processed layer … v1.0 Public demo) and the starting issues, each with a "Done when" line. Safe to run twice: anything that already exists is skipped | Needs the GitHub CLI logged in: `~/anaconda3/bin/gh auth login`, then `PATH="$HOME/anaconda3/bin:$PATH" bash scripts/setup_github_tracker.sh`, then log out again (this machine is shared) |

## Good to know
- It was run once on 2026-10-25; the issues now live on GitHub. Run it again only to add new issues added to the script.
