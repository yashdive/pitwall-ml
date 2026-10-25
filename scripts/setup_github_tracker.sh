#!/usr/bin/env bash
# Create labels, milestones and issues for the project on GitHub.
#
#   gh auth login                       # once
#   bash scripts/setup_github_tracker.sh
#
# Safe to re-run: labels are updated, and milestones / issues that already
# exist (same title) are skipped. Edit the due dates below before running.
set -euo pipefail

REPO="yashdive/pitwall-ml"

# ---------------------------------------------------------------- milestones
M_PROCESSED="v0.2 Processed layer"
M_MODEL="v0.3 Degradation model v0"
M_SKELETON="v0.4 Walking skeleton"
M_SIM="v0.5 Race simulator"
M_STRATEGY="v0.6 Strategy optimiser"
M_DEMO="v1.0 Public demo + writeup"

milestone() {  # title, due date (YYYY-MM-DD), description
  if gh api "repos/$REPO/milestones?state=all&per_page=100" --jq '.[].title' | grep -qxF "$1"; then
    echo "milestone exists: $1"
  else
    gh api "repos/$REPO/milestones" -f title="$1" -f due_on="$2T23:59:59Z" -f description="$3" --silent
    echo "milestone created: $1"
  fi
}

milestone "$M_PROCESSED" 2026-11-08 "Raw laps → cleaned, flagged, validated processed table (Stage 1, data)."
milestone "$M_MODEL"     2026-11-22 "Evaluation protocol + first degradation model, beating baselines (Stage 1, model)."
milestone "$M_SKELETON"  2026-12-06 "MLflow tracking/registry, one pipeline command, API in Docker, CI, schedule (D12)."
milestone "$M_SIM"       2027-01-10 "Lap-by-lap race simulator validated by replaying real races (Stage 2)."
milestone "$M_STRATEGY"  2027-02-07 "Monte Carlo strategy optimiser, backtested against real strategies (Stage 3)."
milestone "$M_DEMO"      2027-03-07 "Hosted demo, dashboard and project writeup."

# -------------------------------------------------------------------- labels
label() { gh label create "$1" --repo "$REPO" --color "$2" --description "$3" --force >/dev/null; echo "label: $1"; }

label data     1d76db "Ingestion, processing, data quality"
label model    5319e7 "Features, training, evaluation"
label infra    0e8a16 "Pipelines, serving, CI, hosting"
label docs     c5def5 "Docs, decisions, writeups"
label bug      d73a4a "Something is wrong"
label idea     fbca04 "Not planned yet; worth exploring"
label learning f9d0c4 "Core logic the user writes (working agreement)"

# -------------------------------------------------------------------- issues
issue() {  # title, labels (comma-separated), milestone ("" for none), body
  if gh issue list --repo "$REPO" --state all --limit 500 --json title --jq '.[].title' | grep -qxF "$1"; then
    echo "issue exists: $1"
    return
  fi
  args=(--repo "$REPO" --title "$1" --label "$2" --body "$4")
  [[ -n "$3" ]] && args+=(--milestone "$3")
  gh issue create "${args[@]}" >/dev/null
  echo "issue created: $1"
}

# --- v0.2 Processed layer
issue "EDA: degradation on two more tracks" "data,learning" "$M_PROCESSED" \
"Run the Q10 recipe (clean → traffic → fuel → stint delta → slopes) on one cool, low-wear track (e.g. Silverstone) and one hot one.

**Done when:** median slope per compound for each track is in the notebook, with one line on whether track/temperature must be model features."

issue "Processed-layer spec from EDA findings" "data,docs" "$M_PROCESSED" \
"Turn the 'decided' column of the EDA summary into a list of output columns, flags and rules. Confirm D10 (flag, don't drop).

**Done when:** spec is in \`docs/\` and D10 is marked accepted in DECISIONS.md."

issue "Transform: seconds, types and compound cleanup" "data,learning" "$M_PROCESSED" \
"Nanoseconds → \`*_sec\`; LapNumber/Stint/TyreLife to int; \`\"None\"\`/\`\"nan\"\` compound strings → missing; drop LapStartDate.

**Done when:** function + unit tests pass (tests prepared by Claude, function written by you)."

issue "Transform: track-status flags" "data,learning" "$M_PROCESSED" \
"From the TrackStatus string: \`yellow_in_lap\`, \`sc_in_lap\`, \`vsc_in_lap\`, \`red_in_lap\`, \`is_green\`.

**Done when:** function + unit tests pass, including multi-digit strings like \`\"1254\"\`."

issue "Transform: lap flags and is_clean" "data,learning" "$M_PROCESSED" \
"\`is_pit_in_lap\`, \`is_pit_out_lap\`, \`is_first_lap\`, \`has_lap_time\`, \`is_wet_compound\`, \`is_deleted\`, and \`is_clean\` combining them.

**Done when:** function + unit tests pass; ~79% of race laps are clean on the full data."

issue "Transform: gap ahead and traffic flag" "data,learning" "$M_PROCESSED" \
"\`gap_ahead_sec\` per (season, round, lap) by position; negative gaps → missing; \`in_traffic\` = gap < threshold (config, default 1.0 s); leader = free air.

**Done when:** function + unit tests pass, including the leader and negative-gap cases."

issue "Transform: weather join" "data,learning" "$M_PROCESSED" \
"Attach the latest weather reading at or before each lap's start (same session clock, same session only). Never use a later reading.

**Done when:** function + unit tests pass, including a test that a reading after lap start is never used."

issue "Processed writer, schema and lineage" "infra" "$M_PROCESSED" \
"Write processed laps per session (same layout and atomic writes as raw). Pandera schema checked before writing. Metadata records raw ingested_at + TRANSFORM_VERSION.

**Done when:** tests pass; bad data fails loudly; re-running is idempotent."

issue "f1-process CLI" "infra" "$M_PROCESSED" \
"Like f1-backfill: process all raw sessions that are new or changed (raw version or transform version).

**Done when:** one command builds data/processed for all 92 races; second run does nothing."

issue "Exercise: --dry-run for f1-backfill" "infra,learning" "" \
"Learning catch-up on the ingestion code: list what would be ingested or skipped, without downloading.

**Done when:** flag works and has a test (test prepared by Claude)."

issue "Why do some green-flag laps have no lap time?" "bug,data" "" \
"2022 R18 (Japan) and 2023 R3 (Australia) have missing LapTime on TrackStatus '1' laps. Find the cause; decide whether the processed layer needs a rule.

**Done when:** cause is written in the EDA notes and, if needed, a rule is added to the spec."

# --- v0.3 Degradation model v0
issue "D16: how we judge models" "model,docs" "$M_MODEL" \
"Evaluation protocol before modelling: metric (error on hidden last N laps of a stint), time-based split, baselines (flat: 0.61 s), noise floor (0.35 s), error-analysis slices, stop rule.

**Done when:** D16 is in DECISIONS.md."

issue "Evaluation harness with baselines" "model" "$M_MODEL" \
"Hide the last N laps of held-out stints; train on earlier races, test on later ones. Report MAE overall and per compound / track. Include the flat and per-stint-line baselines.

**Done when:** one function evaluates any model; baselines appear in the README results log."

issue "Fuel effect per track" "model,learning" "$M_MODEL" \
"Estimate the race-progress (fuel) effect per circuit from all races; store in \`configs/tracks/<circuit>.yaml\` (D13).

**Done when:** a value per circuit exists, with how it was estimated."

issue "Model v0: per-compound linear degradation" "model,learning" "$M_MODEL" \
"Stint start + per-compound slope × tyre age, on fuel-corrected laps. Output: \`predict_lap_time(state)\`.

**Done when:** evaluated with the harness; result in the README results log."

issue "Error analysis of model v0" "model,learning" "$M_MODEL" \
"Slice v0 errors by track, compound, tyre age, temperature, season; look at the 20 worst predictions.

**Done when:** a short report lists the top 2–3 problems, each turned into an issue."

# --- v0.4 Walking skeleton
issue "MLflow experiment tracking" "infra" "$M_SKELETON" \
"Every training run logs params, metrics and artefacts to a local MLflow server.

**Done when:** v0 training appears in the MLflow UI."

issue "MLflow model registry + promotion rule" "infra" "$M_SKELETON" \
"Register models; promote to 'champion' only if it beats the current champion on the held-out races.

**Done when:** promotion is automatic and logged."

issue "Pipeline command: ingest → process → train → register" "infra" "$M_SKELETON" \
"One command for a new race weekend.

**Done when:** running it after a race updates the data and, if better, the champion model."

issue "FastAPI service for predict_lap_time" "infra" "$M_SKELETON" \
"Minimal API loading the champion model; Dockerfile; docker-compose with MLflow.

**Done when:** \`docker compose up\` serves predictions locally."

issue "CI: lint and tests on every push" "infra" "$M_SKELETON" \
"GitHub Actions running ruff and pytest (offline tests only).

**Done when:** a failing test blocks a PR."

issue "Scheduled run after each race weekend" "infra" "$M_SKELETON" \
"Run the pipeline command automatically after each race (cron / scheduler on the free VM, D8).

**Done when:** it runs unattended for one race weekend."

# --- Later stages (one issue each for now; split when the stage starts)
issue "Plan Stage 2: race simulator" "model" "$M_SIM" \
"Break Stage 2 (docs/ROADMAP.md) into ~2-hour issues: pit loss per track, SC/VSC probabilities, traffic model, ghost field, replay validation. Ingest 2026 races (D14).

**Done when:** Stage 2 issues exist in this milestone."

issue "Plan Stage 3: strategy optimiser" "model" "$M_STRATEGY" \
"Break Stage 3 into issues: candidate strategies + legality, Monte Carlo ranking, mid-race re-run, backtest.

**Done when:** Stage 3 issues exist in this milestone."

issue "Plan v1.0: hosting, dashboard, writeup" "infra,docs" "$M_DEMO" \
"Free hosting (D8), dashboard, public writeup of the project and results.

**Done when:** v1.0 issues exist in this milestone."

# --- Ideas
issue "Idea: safety-car laps on a tyre as a feature" "idea,model" "" \
"TyreLife counts SC laps as full laps, but the tyre barely wears. Count SC/VSC laps per tyre set as a feature."

issue "Idea: used vs new tyre sets" "idea,model" "" \
"Used sets start older (median 4 laps). Check whether they degrade differently from new sets at the same TyreLife."

issue "Idea: pit-in-next-N-laps classifier" "idea,model" "" \
"Later model: will this driver pit in the next N laps (logistic regression first)."

issue "Idea: race-winner prediction" "idea,model" "" \
"Later model: needs Q/FP2 ingestion; pre-race features only."

issue "Check free live-data options (D15)" "idea,infra" "" \
"What real-time F1 data is free: FastF1 live-timing recorder, OpenF1 tiers. Decide for Stage 5."

echo
echo "Done. Create the board yourself: repo → Projects → New project → Board (Backlog, This Week, In Progress, Done)."
