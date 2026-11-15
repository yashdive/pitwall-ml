"""Hand-made raw races, shaped like FastF1 raw tables, for processing tests."""

import json

import pandas as pd
import pytest

from f1_intelligence.config import ProcessingRules

RULES = ProcessingRules(
    traffic_gap_s=1.0,
    restart_laps_after_sc_vsc=3,
    restart_laps_after_red_flag=4,
    max_track_temp_jump_c=5.0,
    weather_before_start_s=300,
)

METADATA = {"season": 2024, "round": 3, "session": "R", "event_name": "Test Grand Prix",
            "location": "Testville", "event_format": "conventional",
            "ingested_at_utc": "2026-01-01T00:00:00+00:00"}


def td(seconds):
    return pd.to_timedelta(seconds, unit="s")


def raw_lap(driver="VER", lap=2, lap_time=90.0, start=1000.0, status="1", compound="MEDIUM",
            tyre_life=5.0, stint=1.0, position=1.0, pit_in=None, pit_out=None,
            deleted=False, fresh=True, team="Team A"):
    """One raw lap with FastF1 column names; times in seconds become durations like in raw."""
    return {
        "Season": 2024, "Round": 3, "Session": "R", "Driver": driver, "Team": team,
        "LapNumber": float(lap),
        "LapTime": td(lap_time) if lap_time is not None else pd.NaT,
        "Sector1Time": td(30.0), "Sector2Time": td(30.0), "Sector3Time": td(30.0),
        "LapStartTime": td(start),
        "Time": td(start + (lap_time if lap_time is not None else 90.0)),
        "PitInTime": td(pit_in) if pit_in is not None else pd.NaT,
        "PitOutTime": td(pit_out) if pit_out is not None else pd.NaT,
        "Compound": compound, "TyreLife": tyre_life, "Stint": stint, "FreshTyre": fresh,
        "Position": position, "TrackStatus": status, "Deleted": deleted, "IsAccurate": True,
    }


def raw_laps(rows):
    df = pd.DataFrame(rows)
    df["Compound"] = df["Compound"].astype("string")
    df["TrackStatus"] = df["TrackStatus"].astype("string")
    return df


def one_driver(statuses, driver="VER", lap_time=90.0, first_start=1000.0, **kwargs):
    """Consecutive laps 1..n for one driver, one status string per lap."""
    rows = []
    for i, status in enumerate(statuses, start=1):
        rows.append(raw_lap(driver=driver, lap=i, lap_time=lap_time, start=first_start + (i - 1) * lap_time,
                            status=status, tyre_life=float(i), **kwargs))
    return rows


def raw_weather(times, track_temps, rainfall=False):
    return pd.DataFrame({
        "Time": td(pd.Series(times, dtype="float64")),
        "AirTemp": 20.0, "Humidity": 50.0, "Pressure": 1013.0,
        "Rainfall": rainfall, "TrackTemp": track_temps, "WindDirection": 0, "WindSpeed": 1.0,
    })


@pytest.fixture
def write_raw_race(tmp_path):
    """Write a raw race into a temporary raw layer, like f1-backfill would."""
    def write(laps: pd.DataFrame, weather: pd.DataFrame, metadata: dict = METADATA):
        base = tmp_path / "raw"
        part = f"season={metadata['season']}/round={metadata['round']}/session={metadata['session']}"
        for table, df in (("laps", laps), ("weather", weather)):
            (base / table / part).mkdir(parents=True, exist_ok=True)
            df.to_parquet(base / table / part / "data.parquet", index=False)
        (base / "metadata" / part).mkdir(parents=True, exist_ok=True)
        (base / "metadata" / part / "metadata.json").write_text(json.dumps(metadata))
        return base
    return write
