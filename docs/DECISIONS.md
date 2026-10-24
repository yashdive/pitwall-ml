# Decisions

One entry per design decision: what we decided, why, and what we rejected.
Newest at the bottom. Status is `accepted`, `proposed`, or `superseded by D#`.

---

### D1 — Identify sessions by `(season, round, session)`, never by event name
**Status:** accepted
**Why:** names are fuzzy-matched by FastF1 and not unique. In 2026 `"Spain"` resolves to Madrid while Barcelona is a separate event; the same circuit can also change name between years.
**Rejected:** event name as identifier or folder name.

### D2 — Raw layer: one Parquet file per table per session, Hive-partitioned
**Status:** accepted
**Layout:** `data/raw/<table>/season=YYYY/round=N/session=X/data.parquet` + `data/raw/metadata/.../metadata.json`
**Why:** a session is the unit of ingestion, so per-session files make re-ingestion and crash recovery local. `key=value` folders let DuckDB/pandas read all sessions as one table and prune by season/round. Parquet: typed, columnar, compressed.
**Rejected:** one file per season (every new race rewrites the season; a crash can corrupt it); per-driver files (thousands of tiny files); CSV (loses types).

### D3 — Layered data: raw → processed → features
**Status:** accepted
**Why:** raw stays exactly as FastF1 returned it, so cleaning bugs are fixed by re-running code, not re-downloading. Cleaning (processed) and model-specific choices (features) are separate so several models can share the processed data.

### D4 — Writes are idempotent and atomic; metadata is the commit marker
**Status:** accepted
**Why:** schedulers retry. Re-running must give the same result; a crash must never leave a half-written session that looks complete. Temp file + rename for each file; metadata written last.

### D5 — Classify ingestion failures
**Status:** accepted
**Why:** the orchestrator needs different actions: `SessionNotFound` → skip, `DataNotAvailable` → retry later, `RateLimited` → back off, anything else → alert. FastF1's `load()` does not raise on missing data, so the loader checks explicitly.

### D6 — Ingest races only for v1
**Status:** accepted
**Why:** FastF1 enforces 500 API calls/hour; one session costs ~19 calls. All sessions 2022–2025 ≈ 17 h, races only ≈ 3.5 h. v1 (degradation) and v2 (pit prediction) only need races.
**Revisit:** v3 (race winner) needs Q and probably FP2 — add to `backfill.sessions` in `configs/ingestion.yaml`.

### D7 — Python 3.14
**Status:** accepted
**Why:** latest version; work around libraries that lag behind as needed.

### D8 — Everything must be free to host
**Status:** accepted
**Plan:** Oracle Cloud Always Free VM + Docker Compose, Cloudflare R2 for storage, GitHub Actions for CI. Self-hosted MLflow for tracking and model registry.

### D9 — v1 model: tyre degradation as regression
**Status:** accepted, refined by D11
**Why:** degradation is the core input to everything later (pit windows, strategy). Start with linear regression: the coefficient on tyre age is directly the degradation rate in s/lap, so the model is interpretable from day one. Then iterate (gradient boosting, uncertainty).
**Rejected for v1:** pit-next-N-laps classification (logistic regression) — planned as v2; race-winner prediction — planned as v3.

### D10 — Processed layer flags laps, does not drop them
**Status:** proposed (to confirm after EDA)
**Why:** different models need different laps — degradation wants clean green-flag laps, pit-loss needs in/out laps, a safety-car model needs SC laps. Row selection belongs in the feature layer.

### D11 — The degradation model is a component of a race strategy system
**Status:** accepted
**Why:** strategy teams decide *when to pit and which tyre to fit*; degradation is an input to that decision, not the product. Staged plan (see `docs/ROADMAP.md`): 1 degradation model → 2 race simulator → 3 Monte Carlo optimiser → 4 RL agent (stretch) → 5 live mode. Each stage usable and tested before the next; Stage 3 is a complete product on its own.
**Consequence for Stage 1:** output is `predict_lap_time(state) -> seconds` that the simulator calls; base model is a parametric curve in tyre age on fuel-corrected times (so it extrapolates to longer stints), with gradient boosting on top for conditions. Validation predicts the hidden last N laps of real stints.
**Working agreement unchanged:** the user writes core logic; Claude scaffolds, writes tests and reviews.

### D12 — Walking skeleton: a thin MLOps slice in Stage 1, not at the end
**Status:** accepted
**Why:** the project's original goal is learning end-to-end ML system design. If all MLOps waits until after the simulator, optimiser and RL agent, it may never happen. A minimal end-to-end pipeline early (MLflow tracking + registry, ingest → process → retrain → register command, scheduled run, minimal API in Docker, CI) means later stages plug into something that already runs.
**Rejected:** MLOps only in Stage 5.

### D13 — Simulator parameters live in per-track config files
**Status:** accepted
**Why:** pit loss, safety-car probability and fuel effect differ per circuit and are estimated from data; hard-coding them hides assumptions and makes re-estimation painful. `configs/tracks/<circuit>.yaml`.

### D14 — 2026 regulation era deferred to the simulator stage
**Status:** accepted
**Why:** 2026 is a new regulation set (new cars and tyres behave differently). Stage 1 is built and validated on 2022–2025. 2026 races are ingested when Stage 2 starts; era is then a feature or evaluated separately.

### D15 — Live mode starts as race replay
**Status:** proposed
**Why:** replaying past races lap by lap behaves like live mode for development and backtesting, and is free. Real-time sources need checking against D8 (free hosting): FastF1 can record the official live-timing feed; OpenF1 real-time access may be a paid tier.
