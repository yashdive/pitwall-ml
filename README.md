# F1 Intelligence

**Building a machine-learning foundation for understanding Formula 1 pace, tyre degradation, and race strategy.**

F1 Intelligence is an early-stage data and ML project that turns Formula 1 session data into analysis-ready datasets. The project currently retrieves lap and weather data through [FastF1](https://github.com/theOehrly/Fast-F1), explores the factors that shape lap time, and establishes the data layer for future predictive models.

The long-term goal is to move from describing a race to answering useful questions about it:

- How quickly is each tyre compound degrading?
- How much pace does a driver have after accounting for tyre age and track conditions?
- When is the best pit window—and how does traffic change it?
- What is the likely outcome of an alternative race strategy?

> This repository is under active development. It contains the ingestion foundation and initial exploratory work; production ML models and strategy simulation are the next milestones.

## Why this project?

Raw timing data shows *what* happened. F1 Intelligence aims to estimate *why* it happened and *what could happen next*.

Race pace is affected by interacting variables such as tyre compound and age, fuel burn, track evolution, temperature, traffic, safety cars, and driver or car performance. This project is being built as a reproducible pipeline that can separate those effects and eventually support data-driven race predictions.

## Current progress

- FastF1-based session loading by season, Grand Prix, and session type
- Selective ingestion of lap and weather datasets
- Local, columnar storage using Parquet with Zstandard compression
- Session metadata capture for traceability
- Exploratory lap-quality filtering to remove pit laps, deleted laps, and abnormal track states
- Investigation of tyre age, stint-level degradation, compound performance, track temperature, and previous-lap pace
- Initial feature design for lap-time modelling

The included research uses the 2024 Spanish Grand Prix as an initial case study.

## Where it is going

```text
FastF1 timing data
        │
        ▼
Validated session datasets
        │
        ▼
Race-context feature engineering
        │
        ├──► Lap-time prediction
        ├──► Tyre-degradation estimation
        └──► Driver and team pace comparison
                     │
                     ▼
             Strategy simulation
                     │
                     ▼
        Explainable race intelligence
```

Planned development is organized around four stages:

1. **Data foundation** — reliable ingestion, validation, storage, and multi-race datasets.
2. **Pace modelling** — predict representative lap time from tyre, stint, weather, driver, team, and race-context features.
3. **Strategy modelling** — model pit-stop loss, traffic, compound choices, and alternative pit windows.
4. **Decision layer** — expose predictions and scenario comparisons through an API or interactive application.

## Repository structure

```text
F1/
├── configs/
│   └── ingestion.yaml          # Storage and ingestion settings
├── data/raw/                   # Example session data and local raw datasets
├── research/
│   ├── data_ingestion.ipynb    # Ingestion experiments
│   └── FastAPI_testing.ipynb   # Pace and tyre-degradation exploration
├── src/f1_intelligence/
│   └── ingestion/
│       ├── fastf1_loader.py    # FastF1 session and dataset loader
│       └── data_writer.py      # Parquet/metadata persistence
└── requirements.txt
```

## Getting started

### 1. Create an environment

Python 3.10 or newer is recommended.

```bash
git clone <repository-url>
cd F1
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Load a session

Run Python from the project root with `src` on the module path:

```bash
export PYTHONPATH="$PWD/src"
```

```python
from f1_intelligence.ingestion.fastf1_loader import FastF1Loader

loader = FastF1Loader(
    season=2024,
    event="Spain",
    session_type="R",
    datasets=["laps", "weather"],
)

session = loader.load_session()
data = loader.load_datasets(session)

print(data["metadata"])
print(data["laps"].head())
```

FastF1 downloads timing data on first use, so the initial run may take a few minutes.

### 3. Explore the research

Open the notebooks in `research/` to follow the ingestion experiments and the first analysis of clean race laps, tyre-life effects, stint slopes, compound differences, and track temperature.

## Modelling principles

As the ML layer develops, the project will emphasize:

- **No future information:** features must be available at the moment a prediction is made.
- **Time-aware evaluation:** train and test splits should follow race chronology rather than randomly mixing laps.
- **Race-context controls:** pit laps, safety-car periods, traffic, and invalid laps must not distort clean-air pace.
- **Uncertainty over false precision:** strategy outputs should communicate a range of plausible outcomes.
- **Explainability:** predictions should connect back to understandable racing factors.

## Roadmap

- [x] Prototype FastF1 ingestion
- [x] Store lap, weather, and session metadata
- [x] Explore lap filtering and tyre-degradation signals
- [ ] Harden the ingestion API and add automated tests
- [ ] Build multi-event, multi-season training datasets
- [ ] Add validation schemas and data-quality reporting
- [ ] Establish leakage-safe baseline models
- [ ] Estimate stint-level tyre degradation with uncertainty
- [ ] Add pit-loss, traffic, and safety-car context
- [ ] Build a race-strategy simulator
- [ ] Serve scenario analysis through an API/dashboard

## Data and attribution

Timing data is accessed through the community-maintained [FastF1](https://github.com/theOehrly/Fast-F1) Python package. Formula 1, F1, and related marks are trademarks of Formula One Licensing B.V. This is an independent educational project and is not associated with Formula 1, the FIA, or any Formula 1 team.

## Contributing

Ideas, issues, and pull requests are welcome—especially around feature engineering, time-aware validation, tyre modelling, and strategy simulation.
