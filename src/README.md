# src/

**What this folder is:** all the project's Python code, as one installable package called `f1_intelligence`.

The code sits inside `src/` (instead of at the project root) on purpose: Python can then only import it once it is installed with `pip install -e .`. That way the tests and notebooks use the code exactly as it is installed, and a missing file in the package shows up straight away.

## Contents

| Folder | What it is |
|---|---|
| `f1_intelligence/` | The package: ingestion, processing, orchestration and shared helpers (see `f1_intelligence/README.md`) |

## Good to know
- Install once (from the project root): `pip install -e .` The `-e` ("editable") means code changes are picked up without reinstalling.
- Installing also creates the commands `f1-backfill` and `f1-process` (defined in `pyproject.toml`).
