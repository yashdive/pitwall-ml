# Roadmap

**End product:** a monitored race strategy system that predicts lap times as tyres wear,
simulates races, recommends pit strategies, and can be backtested against real races.

Each stage must be usable and tested on its own before the next starts.
Stage 3 is a complete product even if Stage 4 slips.

Status: ✅ done · 🔨 in progress · ⬜ not started

---

## Stage 0 — Data foundation
- ✅ FastF1 loader: sessions identified by `(season, round, session)`, typed `SessionData`, classified errors
- ✅ Raw writer: Hive-partitioned Parquet, atomic writes, metadata as commit marker, idempotent
- ✅ `f1-backfill` CLI: resumable, waits out the API rate limit, exit codes for schedulers
- ✅ Backfill 2022–2025 races (92 races, ~101k laps)
- ⬜ Exercise: add `--dry-run` to `f1-backfill` (learning catch-up)

## Stage 1 — Lap-time / degradation model + walking skeleton
**Output:** `predict_lap_time(state) -> seconds`, callable by the simulator.

Data and model:
- 🔨 EDA of raw race laps → processed-layer spec (`research/02_raw_race_eda.ipynb`)
- ⬜ Processed layer: types, flags (pit in/out, lap 1, SC/VSC/red/yellow, traffic, wet, deleted), weather join; flags kept, not dropped
- ⬜ Data contract (pandera schema) + processed writer with lineage; `f1-process` CLI
- ⬜ Fuel correction (per-lap fuel effect; estimated or a config parameter)
- ⬜ Base model: parametric degradation curve per stint (linear, then quadratic in tyre age) on fuel-corrected times; must extrapolate sensibly
- ⬜ Conditions model: gradient boosting (LightGBM) predicting curve parameters or residuals from track, compound, temperature
- ⬜ Validation: hide the last N laps of held-out real stints and predict them; error per compound and track; train on earlier races, test on later ones
- ⬜ Later: hierarchical/Bayesian version (track → compound → stint)

Walking skeleton (thin MLOps slice, D12):
- ⬜ MLflow tracking for every training run (params, metrics, artefacts) from the first model
- ⬜ MLflow model registry: register the model; promote only if it beats the current one on held-out races
- ⬜ One pipeline command: ingest new race → process → retrain → evaluate → register
- ⬜ Scheduled run after each race weekend
- ⬜ Minimal FastAPI service serving `predict_lap_time`, in Docker
- ⬜ CI: GitHub Actions running lint + tests

## Stage 2 — Race simulator
- ⬜ Lap-by-lap simulation using the Stage 1 model
- ⬜ Pit-stop time loss per track (estimated from in/out laps)
- ⬜ Starting fuel; traffic / overtaking (must be X s/lap faster to pass)
- ⬜ Random safety cars / VSCs, probabilities per track from historical `track_status`
- ⬜ Single car vs "ghost" field on real strategies → full field later
- ⬜ Fast: thousands of races in reasonable time (vectorised)
- ⬜ Per-track config files: `configs/tracks/<circuit>.yaml` (D13)
- ⬜ Ingest 2026 races; regulation era as a feature or separate evaluation (D14)
- ⬜ Validation: replay real races with the strategies teams used; compare finishing order and race time

## Stage 3 — Monte Carlo strategy optimiser
- ⬜ Candidate strategies: 1-stop, 2-stop, compound orders, pit-lap windows; legality (two dry compounds)
- ⬜ Simulate each many times; rank by expected result and risk (spread of outcomes)
- ⬜ Re-run mid-race from the current state ("SC on lap 23: pit now or not?")
- ⬜ Backtest: recommended vs actual team strategies; log cases where the system would have done better

## Stage 4 — Reinforcement learning agent (stretch)
- ⬜ Simulator as a Gymnasium environment (state, actions: stay out / pit for S/M/H, reward, illegal-strategy penalty)
- ⬜ Single car, PPO or DQN (Stable-Baselines3), then more complexity
- ⬜ Compare with the Stage 3 baseline on the same races; check the simulator first if results look too good

## Stage 5 — Live mode + full MLOps
- ⬜ Race replay mode: feed past races lap by lap as if live (free; used for development and backtesting)
- ⬜ Live data source: verify what is free in real time (FastF1 live-timing recorder; OpenF1 real-time may be paid) (D15)
- ⬜ Each lap: update degradation estimates, re-run optimiser/agent, output a pit window
- ⬜ API + dashboard: current recommendation, predicted vs actual lap times
- ⬜ Monitoring: per-lap prediction error, data drift (new track, temperature, compound behaviour), latency, alerts on sharp degradation changes
- ⬜ Hosting on a free tier (Oracle Cloud Always Free VM, Cloudflare R2)

## Later models (from earlier planning)
- ⬜ Will this driver pit in the next N laps (classification, logistic regression first)
- ⬜ Race winner prediction for a new race (needs Q/FP2 ingestion; pre-race features only)
