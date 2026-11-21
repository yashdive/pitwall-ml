"""Raw FastF1 tables of ONE race → the processed lap table (docs/design/processed_layer.md).

Each step is a plain function: it takes the lap table and returns it with a few
columns added. `build_processed_laps` runs them in order.

Rule (D18): a column may use only the current lap and earlier laps. That way the
same functions work on a finished race (training) and lap by lap (live).
"""

import numpy as np
import pandas as pd

from f1_intelligence.config import ProcessingRules

DRY_COMPOUNDS = ("SOFT", "MEDIUM", "HARD")
WET_COMPOUNDS = ("INTERMEDIATE", "WET")
PIT_TYPES = ("normal", "under_sc_vsc", "red_flag")

KEY = ["season", "round", "session", "driver", "lap_number"]

# Final column order of the processed table.
COLUMNS = [
    *KEY, "team", "event_name", "location", "event_format",
    "lap_time_s", "sector1_s", "sector2_s", "sector3_s",
    "lap_start_s", "lap_end_s", "pit_in_s", "pit_out_s",
    "compound", "tyre_life", "stint", "fresh_tyre", "position", "track_status",
    "is_first_lap", "has_lap_time", "has_tyre_info", "is_wet_compound",
    "is_pit_in_lap", "is_pit_out_lap", "pit_type",
    "is_green", "yellow_in_lap", "sc_in_lap", "vsc_in_lap", "red_in_lap",
    "laps_since_neutralisation", "is_restart_lap",
    "is_deleted", "is_accurate",
    "gap_ahead_s", "in_traffic",
    "track_temp_c", "air_temp_c", "humidity_pct", "rainfall",
    "is_clean",
]


def build_processed_laps(
    raw_laps: pd.DataFrame,
    raw_weather: pd.DataFrame,
    metadata: dict,
    rules: ProcessingRules,
) -> pd.DataFrame:
    """Run every step, in order, for one race."""
    df = base_columns(raw_laps)
    df = add_event_info(df, metadata)
    df = add_lap_flags(df)
    df = add_status_flags(df)
    df = add_pit_type(df)
    df = add_restart_flags(df, rules.restart_laps_after_sc_vsc, rules.restart_laps_after_red_flag)
    df = add_gap_ahead(df, rules.traffic_gap_s)
    race_start_s = df.loc[df["lap_number"] == 1, "lap_start_s"].min()
    weather = clean_weather(raw_weather, race_start_s, rules.weather_before_start_s, rules.max_track_temp_jump_c)
    df = add_weather(df, weather)
    df = add_clean_flag(df)
    return df[COLUMNS].sort_values(["driver", "lap_number"]).reset_index(drop=True)


# --------------------------------------------------------------------------- basics

def to_seconds(col: pd.Series) -> pd.Series:
    """Raw times are durations (or integer nanoseconds) → float seconds; missing stays missing."""
    if pd.api.types.is_datetime64_any_dtype(col) and col.isna().all():
        # A column that is empty everywhere (e.g. no pit stops) can lose its duration type
        # on the way through Parquet; converting it as a number would give huge negative values.
        return pd.Series(float("nan"), index=col.index, dtype="float64")
    return pd.to_timedelta(col, errors="coerce").dt.total_seconds().astype("float64")


def base_columns(raw: pd.DataFrame) -> pd.DataFrame:
    """Rename to snake_case, convert units and types, fix the compound text."""
    compound = raw["Compound"].astype("string")
    df = pd.DataFrame({
        "season": raw["Season"].astype("int64"),
        "round": raw["Round"].astype("int64"),
        "session": raw["Session"].astype("string"),
        "driver": raw["Driver"].astype("string"),
        "team": raw["Team"].astype("string"),
        "lap_number": raw["LapNumber"].round().astype("int64"),
        "lap_time_s": to_seconds(raw["LapTime"]),
        "sector1_s": to_seconds(raw["Sector1Time"]),
        "sector2_s": to_seconds(raw["Sector2Time"]),
        "sector3_s": to_seconds(raw["Sector3Time"]),
        "lap_start_s": to_seconds(raw["LapStartTime"]),
        "lap_end_s": to_seconds(raw["Time"]),
        "pit_in_s": to_seconds(raw["PitInTime"]),
        "pit_out_s": to_seconds(raw["PitOutTime"]),
        # "None" / "nan" are text in raw: anything that is not a real compound becomes missing.
        "compound": compound.where(compound.isin(DRY_COMPOUNDS + WET_COMPOUNDS)),
        "tyre_life": raw["TyreLife"].round().astype("Int64"),
        "stint": raw["Stint"].round().astype("Int64"),
        "fresh_tyre": raw["FreshTyre"].fillna(False).astype(bool),
        "position": raw["Position"].round().astype("Int64"),
        "track_status": raw["TrackStatus"].astype("string").fillna(""),
        "is_deleted": raw["Deleted"].fillna(False).astype(bool),
        "is_accurate": raw["IsAccurate"].fillna(False).astype(bool),
    })
    return df.sort_values(["driver", "lap_number"]).reset_index(drop=True)


def add_event_info(df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
    df = df.copy()
    for col in ("event_name", "location", "event_format"):
        df[col] = pd.array([metadata.get(col)] * len(df), dtype="string")
    return df


# --------------------------------------------------------------------------- flags

def add_lap_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["is_first_lap"] = df["lap_number"] == 1
    df["has_lap_time"] = df["lap_time_s"].notna()
    df["has_tyre_info"] = df["tyre_life"].notna() & df["compound"].notna()
    df["is_wet_compound"] = df["compound"].isin(WET_COMPOUNDS).fillna(False).astype(bool)
    df["is_pit_in_lap"] = df["pit_in_s"].notna()
    df["is_pit_out_lap"] = df["pit_out_s"].notna()
    return df


def add_status_flags(df: pd.DataFrame) -> pd.DataFrame:
    """TrackStatus lists every status during the lap ("1254"): one flag per kind, by digit present."""
    df = df.copy()
    status = df["track_status"]

    def has(digits: str) -> pd.Series:
        return status.str.contains(f"[{digits}]", regex=True).fillna(False).astype(bool)

    df["is_green"] = (status == "1").fillna(False).astype(bool)
    df["yellow_in_lap"] = has("2")
    df["sc_in_lap"] = has("4")
    df["red_in_lap"] = has("5")
    df["vsc_in_lap"] = has("67")
    return df


def add_pit_type(df: pd.DataFrame) -> pd.DataFrame:
    """Kind of stop, set on the in-lap; the out-lap takes the kind of the stop it ends.

    red_flag: every car enters the pit lane under a red flag (free tyre change).
    under_sc_vsc: a real stop while the field is slow (cheaper).
    """
    df = df.copy()
    kind = np.select(
        [df["red_in_lap"], df["sc_in_lap"] | df["vsc_in_lap"]],
        ["red_flag", "under_sc_vsc"],
        default="normal",
    )
    on_in_lap = pd.Series(kind, index=df.index, dtype="string").where(df["is_pit_in_lap"])
    carried = on_in_lap.groupby(df["driver"]).ffill()  # from this or an earlier lap only
    df["pit_type"] = on_in_lap.fillna(carried.where(df["is_pit_out_lap"]))
    return df


def add_restart_flags(df: pd.DataFrame, after_sc_vsc: int, after_red_flag: int) -> pd.DataFrame:
    """Laps right after a safety car, VSC or red flag: cold tyres, bunched field.

    Measured (EDA v1): +0.7 / +0.35 / +0.16 s on the 1st/2nd/3rd lap after a SC or VSC,
    and +33 / +2.1 / +1.2 s on the 2nd/3rd/4th lap after a red flag.
    """
    df = df.copy()
    neutral = df["sc_in_lap"] | df["vsc_in_lap"] | df["red_in_lap"]
    by_driver = df["driver"]
    last_neutral_lap = df["lap_number"].where(neutral).groupby(by_driver).ffill()
    since = df["lap_number"] - last_neutral_lap  # 0 on a neutralised lap, missing before the first one
    last_was_red = df["red_in_lap"].astype(float).where(neutral).groupby(by_driver).ffill()
    window = np.where(last_was_red == 1, after_red_flag, after_sc_vsc)

    df["laps_since_neutralisation"] = since.round().astype("Int64")
    df["is_restart_lap"] = ((since >= 1) & (since <= window)).fillna(False).astype(bool)
    return df


# --------------------------------------------------------------------------- traffic

def add_gap_ahead(df: pd.DataFrame, traffic_gap_s: float) -> pd.DataFrame:
    """Seconds between this car and the car one position ahead crossing the line on the same lap."""
    df = df.copy()
    ranked = df[df["position"].notna()].sort_values(["lap_number", "position"])
    per_lap = ranked.groupby("lap_number")
    gap = per_lap["lap_end_s"].diff()
    car_ahead_is_next_position = per_lap["position"].diff() == 1
    gap = gap.where(car_ahead_is_next_position & (gap >= 0))  # negative or a missing car in between → missing

    df["gap_ahead_s"] = gap.reindex(df.index)
    df["in_traffic"] = (df["gap_ahead_s"] < traffic_gap_s).fillna(False).astype(bool)  # leader = free air
    return df


# --------------------------------------------------------------------------- weather

def clean_weather(
    raw_weather: pd.DataFrame,
    race_start_s: float,
    before_start_s: float,
    max_track_temp_jump_c: float,
) -> pd.DataFrame:
    """Weather readings we trust: from just before the start, without sensor jumps.

    A track temperature that moves more than `max_track_temp_jump_c` from the last
    trusted reading is treated as a sensor error (e.g. the sensor being covered).
    """
    columns = ["time_s", "track_temp_c", "air_temp_c", "humidity_pct", "rainfall"]
    if raw_weather is None or raw_weather.empty:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in columns})

    w = pd.DataFrame({
        "time_s": to_seconds(raw_weather["Time"]),
        "track_temp_c": raw_weather["TrackTemp"].astype("float64"),
        "air_temp_c": raw_weather["AirTemp"].astype("float64"),
        "humidity_pct": raw_weather["Humidity"].astype("float64"),
        "rainfall": raw_weather["Rainfall"].astype("boolean"),
    }).sort_values("time_s")
    w = w[w["time_s"] >= race_start_s - before_start_s]

    keep, last_trusted = [], None
    for temp in w["track_temp_c"]:
        ok = pd.notna(temp) and (last_trusted is None or abs(temp - last_trusted) <= max_track_temp_jump_c)
        keep.append(ok)
        if ok:
            last_trusted = temp
    return w[keep].reset_index(drop=True)


def add_weather(df: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """Each lap gets the last trusted reading at or before the lap started (never a later one)."""
    df = df.sort_values("lap_start_s")
    merged = pd.merge_asof(
        df, weather.sort_values("time_s"),
        left_on="lap_start_s", right_on="time_s", direction="backward",
    ).drop(columns="time_s")
    merged["rainfall"] = merged["rainfall"].astype("boolean")
    return merged.sort_values(["driver", "lap_number"]).reset_index(drop=True)


# --------------------------------------------------------------------------- summary

def add_clean_flag(df: pd.DataFrame) -> pd.DataFrame:
    """A normal racing lap: no event changed its time. Traffic is left to each model."""
    df = df.copy()
    df["is_clean"] = (
        ~df["is_first_lap"]
        & df["has_lap_time"]
        & df["has_tyre_info"]
        & ~df["is_pit_in_lap"]
        & ~df["is_pit_out_lap"]
        & df["is_green"]
        & ~df["is_restart_lap"]
        & ~df["is_deleted"]
        & ~df["is_wet_compound"]
    )
    return df
