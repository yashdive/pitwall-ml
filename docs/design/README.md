# docs/design/

**What this folder is:** one **design note** per component. A design note is written before the code and approved first. It says what the component does, its inputs and outputs, the key decisions (and what we did not choose), what can go wrong, and how it is tested. After building, a short "changes made while building" section records anything that turned out differently.

## Files

| File | Component | In short |
|---|---|---|
| `processed_layer.md` | Processing (`src/f1_intelligence/processing/`) | How a raw race becomes one clean lap table: every output column with its rule, the schema checks, the tests, and why all laps are kept with flags |
| `orchestration.md` | Orchestration (`src/f1_intelligence/orchestration/`) | How Dagster runs the pipeline: one partition per race, the new-race sensor, versions from fingerprints, automatic rebuilds, safe retries |

## Good to know
- Decisions inside a note are also listed in `../DECISIONS.md` (e.g. D18, D19) so all decisions are in one place.
- Next notes to come: features, the degradation model, the API.
