# Design: processed layer (v1)

**Status:** approved 2026-11-15
**Based on:** EDA v1 (`research/FINDINGS.md`, tag `eda-v1`), decisions D3, D10, D17

## 1. What it does and why
Turns raw FastF1 tables into **one clean table of laps**: one row per lap, with correct units, fixed data problems, and flags that describe what happened on that lap.

It keeps **every lap**. It does not decide which laps a model uses, and it does not apply model assumptions (like the fuel value). That happens in the features step, so several models can share this table.

## 2. Inputs → outputs

```text
data/raw/laps/…           ┐
data/raw/weather/…        ├─→  f1-process  ─→  data/processed/v1/laps/season=YYYY/round=N/session=R/data.parquet
data/raw/metadata/…       ┘    (per race)       data/processed/v1/metadata/season=…/metadata.json
```

- **Unit of work:** one race (`season`, `round`, `session`). A new race = one new file.
- **Format:** Parquet, same folder layout as raw.
- **Not used yet:** `track_status` (the per-lap `TrackStatus` string is enough), `results`, `race_control`. They stay raw until the simulator needs them.

## 3. Output columns
One row per lap. Key: `(season, round, session, driver, lap_number)`, unique. Names in `snake_case`.

**Identity and event**
| Column | Rule | From |
|---|---|---|
| `season`, `round`, `session`, `driver`, `team` | copied | laps |
| `lap_number` | integer | `LapNumber` |
| `event_name`, `location`, `event_format` | joined | metadata |

**Times (seconds)**
| Column | Rule | From |
|---|---|---|
| `lap_time_s` | ns → s. **Never filled in** when missing | `LapTime` |
| `sector1_s`, `sector2_s`, `sector3_s` | ns → s | `Sector1–3Time` |
| `lap_start_s`, `lap_end_s` | ns → s (session clock) | `LapStartTime`, `Time` |
| `pit_in_s`, `pit_out_s` | ns → s (session clock) | `PitInTime`, `PitOutTime` |

**Tyres**
| Column | Rule | From |
|---|---|---|
| `compound` | `"None"` / `"nan"` text → missing | `Compound` |
| `tyre_life`, `stint` | integer, missing stays missing | `TyreLife`, `Stint` |
| `fresh_tyre` | copied | `FreshTyre` |

**What happened on the lap (flags)**
| Column | Rule |
|---|---|
| `is_first_lap` | `lap_number == 1` |
| `has_lap_time` | `lap_time_s` not missing |
| `has_tyre_info` | `tyre_life` and `compound` not missing |
| `is_wet_compound` | compound is INTERMEDIATE or WET |
| `is_pit_in_lap`, `is_pit_out_lap` | pit time present |
| `pit_type` | on the in-lap: `red_flag` if the lap's status contains 5, `under_sc_vsc` if it contains 4, 6 or 7, else `normal`. The out-lap takes the type of the stop it ends |
| `is_green` | `TrackStatus == "1"` |
| `yellow_in_lap`, `sc_in_lap`, `red_in_lap`, `vsc_in_lap` | the digit appears in `TrackStatus` (2 / 4 / 5 / 6 or 7) |
| `laps_since_neutralisation` | laps since this driver's last lap with SC, VSC or red flag (missing if none yet) |
| `is_restart_lap` | within the first **3 laps after a SC / VSC** or the first **4 laps after a red flag** (both in config). Measured: these laps are +0.7, +0.35, +0.16 s slower after SC/VSC, and +33, +2.1, +1.2 s after a red flag |
| `is_deleted`, `is_accurate` | copied from `Deleted`, `IsAccurate` |
| `position` | copied |

**Traffic**
| Column | Rule |
|---|---|
| `gap_ahead_s` | `lap_end_s` minus that of the car one position ahead, same lap. Negative → missing. Leader → missing |
| `in_traffic` | `gap_ahead_s < 1.0` (threshold in config). Leader = not in traffic |

**Weather**
| Column | Rule |
|---|---|
| `track_temp_c`, `air_temp_c`, `humidity_pct`, `rainfall` | the last valid weather reading at or before `lap_start_s`, same race |

Before joining: keep only readings from the race itself (first lap start → last lap end), and drop a reading if track temperature jumps more than 5 °C from the previous one (sensor error).

**Summary flag**
| Column | Rule |
|---|---|
| `is_clean` | not first lap, has lap time, has tyre info, not a pit in/out lap, green, not a restart lap, not deleted, dry compound |

`in_traffic` is **not** part of `is_clean`: whether to drop traffic laps is a model choice.

**Dropped:** `LapStartDate` (always empty), sector session times, speed traps, `IsPersonalBest`, `FastF1Generated`, `DeletedReason`.

## 4. Key decisions
| Decision | Why | Not chosen |
|---|---|---|
| One wide lap table | Joined once, the same way for every model | Separate laps / weather tables joined later by each model |
| Keep all laps, add flags (D10) | Other models need pit, SC and wet laps | Dropping laps here |
| Versions as folders (`v1/`, `v2/`) | A model's training data never changes under it; old and new can be compared | Overwriting in place |
| **Past-only columns (D18, new)** | The same code must work live, lap by lap. A column may use only this lap and earlier laps | Columns that look at the whole race (e.g. a driver's race median) |
| Thresholds in config | Easy to change and record (traffic 1.0 s, restart 3 / 4 laps, temp jump 5 °C) | Hard-coded numbers |
| No fuel correction, no row filtering, no target | Those are model choices (features step) | Doing it here |

## 5. How `f1-process` runs
For each race in raw:
1. Skip if the processed file exists **and** was built from the same raw version (raw `ingested_at`). Otherwise (re)build it.
2. Read the race's raw laps, weather and metadata.
3. Run the transforms (plain functions, in order).
4. Check the result against the schema (below). Stop on any failure.
5. Write the Parquet file, then the metadata file last (same safe writing as raw).

Metadata per race: processing version, raw `ingested_at`, code commit, row count, share of clean laps, checks passed.

A change to the rules = a new version folder, built from scratch. A new race = one new file in the current version.

## 6. Schema checks (stop the pipeline if broken)
- The key is unique; every required column exists with the right type.
- `lap_time_s` is either missing or between 60 and 200 s.
- `tyre_life` ≥ 1 when present; `compound` is one of the five names or missing.
- Every flag is True or False (never missing).
- `gap_ahead_s` ≥ 0 when present.

## 7. Tests
- One test per transform with small hand-made laps.
- Real cases from the EDA, e.g. Melbourne 2023 (VER laps 8–10, 55–58: red-flag pit entries, `pit_type = red_flag`, restart laps not clean; HAM lap 10 not clean).
- **Past-only test:** adding later laps to a race must not change any column of the earlier laps.
- Running `f1-process` twice changes nothing.

## 8. Not in this step
Fuel correction, choosing training rows, building the target, results / race-control tables, data-versioning tools (Delta Lake, DVC).

## 9. Answers (2026-11-15)
1. Restart laps: 3 after SC / VSC, 4 after a red flag (measured, see above). They are real laps, so they stay in the table, flagged; they are left out of degradation because they would make stints start too slow.
2. Keep all weather columns: cheap, unused in v1, can be tested later.
3. Deleted laps are **not** missing: all have a lap time. They are about 0.5 s slower than normal (often a mistake), so they stay flagged and are left out of `is_clean`.

## 10. Changes made while building (2026-11-15)
- **Lap time check split in two:** real red-flag laps can take up to ~2,500 s (they include the stoppage), so any lap must be 50–3,600 s, and **clean** laps 60–200 s.
- **`track_status` kept** as a column (the raw string), so every flag can be checked by eye.
- **Weather window starts 5 minutes before the first lap** (config `weather_before_start_s`), so lap 1 also gets a reading.
- **Gap ahead is missing when the position just ahead is missing** (e.g. P5 not timed): otherwise P6 would be compared with P4.
- **First full run:** 92 races, 101,290 laps, 73.6 % clean, 5.5 % restart laps, every lap has weather, ~5 s.
