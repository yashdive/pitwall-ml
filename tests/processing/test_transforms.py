import pandas as pd
import pytest

from f1_intelligence.processing.schema import PROCESSED_LAPS_SCHEMA
from f1_intelligence.processing.transforms import (
    add_gap_ahead,
    add_lap_flags,
    add_pit_type,
    add_restart_flags,
    add_status_flags,
    base_columns,
    build_processed_laps,
    clean_weather,
)
from tests.processing.conftest import METADATA, RULES, one_driver, raw_lap, raw_laps, raw_weather


def flagged(rows):
    return add_pit_type(add_status_flags(add_lap_flags(base_columns(raw_laps(rows)))))


# ------------------------------------------------------------------ units and types

def test_times_become_seconds_and_compound_text_becomes_missing():
    df = base_columns(raw_laps([
        raw_lap(lap=2, lap_time=83.186, compound="MEDIUM"),
        raw_lap(lap=3, compound="None"),
        raw_lap(lap=4, compound="nan"),
        raw_lap(lap=5, lap_time=None),
    ]))
    assert df.loc[0, "lap_time_s"] == pytest.approx(83.186)
    assert df["compound"].isna().tolist() == [False, True, True, False]
    assert pd.isna(df.loc[3, "lap_time_s"])  # never filled in


# ------------------------------------------------------------------ track status

@pytest.mark.parametrize("status, green, yellow, sc, vsc, red", [
    ("1",    True,  False, False, False, False),
    ("1254", False, True,  True,  False, True),
    ("671",  False, False, False, True,  False),
    ("41",   False, False, True,  False, False),
])
def test_status_flags_by_digit_present(status, green, yellow, sc, vsc, red):
    row = flagged([raw_lap(status=status)]).iloc[0]
    assert (row.is_green, row.yellow_in_lap, row.sc_in_lap, row.vsc_in_lap, row.red_in_lap) == (green, yellow, sc, vsc, red)


# ------------------------------------------------------------------ pit stops

def test_pit_type_from_in_lap_and_carried_to_out_lap():
    df = flagged([
        raw_lap(lap=8, status="451", pit_in=4600.0),    # red flag: everyone into the pit lane
        raw_lap(lap=9, status="1", pit_out=5500.0),     # restart
        raw_lap(lap=20, status="14", pit_in=6000.0),    # stop under safety car
        raw_lap(lap=21, status="1", pit_out=6030.0),
        raw_lap(lap=30, status="1", pit_in=7000.0),     # normal stop
        raw_lap(lap=31, status="1", pit_out=7030.0),
        raw_lap(lap=32, status="1"),                    # not a pit lap
    ])
    assert df["pit_type"].tolist()[:6] == ["red_flag", "red_flag", "under_sc_vsc", "under_sc_vsc", "normal", "normal"]
    assert pd.isna(df["pit_type"].iloc[6])


# ------------------------------------------------------------------ restart laps

def restart_flags(statuses):
    df = add_restart_flags(flagged(one_driver(statuses)), after_sc_vsc=3, after_red_flag=4)
    return df["is_restart_lap"].tolist(), df["laps_since_neutralisation"].tolist()


def test_three_restart_laps_after_safety_car():
    restart, since = restart_flags(["1", "1", "4", "4", "41", "1", "1", "1", "1"])
    assert since[:2] == [pd.NA, pd.NA] or all(pd.isna(s) for s in since[:2])
    assert since[2:] == [0, 0, 0, 1, 2, 3, 4]
    assert restart == [False, False, False, False, False, True, True, True, False]


def test_four_restart_laps_after_red_flag():
    restart, _ = restart_flags(["1", "451", "1", "1", "1", "1", "1"])
    assert restart == [False, False, True, True, True, True, False]


# ------------------------------------------------------------------ traffic

def test_gap_ahead_leader_negative_and_missing_position():
    rows = [
        raw_lap(driver="AAA", lap=5, start=1000.0, lap_time=90.0, position=1.0),   # crosses at 1090.0
        raw_lap(driver="BBB", lap=5, start=1000.0, lap_time=90.6, position=2.0),   # 1090.6 → gap 0.6
        raw_lap(driver="CCC", lap=5, start=1000.0, lap_time=93.0, position=3.0),   # 1093.0 → gap 2.4
        raw_lap(driver="DDD", lap=5, start=1000.0, lap_time=92.0, position=4.0),   # 1092.0 → negative
        raw_lap(driver="EEE", lap=5, start=1000.0, lap_time=95.0, position=6.0),   # P5 missing
    ]
    df = add_gap_ahead(base_columns(raw_laps(rows)), traffic_gap_s=1.0).set_index("driver")
    assert pd.isna(df.loc["AAA", "gap_ahead_s"]) and not df.loc["AAA", "in_traffic"]
    assert df.loc["BBB", "gap_ahead_s"] == pytest.approx(0.6) and df.loc["BBB", "in_traffic"]
    assert df.loc["CCC", "gap_ahead_s"] == pytest.approx(2.4) and not df.loc["CCC", "in_traffic"]
    assert pd.isna(df.loc["DDD", "gap_ahead_s"])
    assert pd.isna(df.loc["EEE", "gap_ahead_s"])


# ------------------------------------------------------------------ weather

def test_weather_window_and_sensor_jumps():
    w = clean_weather(
        raw_weather(times=[100, 2000, 2100, 2160, 2220, 2280], track_temps=[50, 35, 35.5, 20, 21, 36]),
        race_start_s=2200, before_start_s=300, max_track_temp_jump_c=5.0,
    )
    # 100 s is long before the start; 20 and 21 °C are jumps from the last trusted 35.5 °C
    assert w["time_s"].tolist() == [2000, 2100, 2280]


def test_lap_never_gets_a_later_weather_reading():
    laps = raw_laps(one_driver(["1", "1", "1"], first_start=1000.0))  # laps start at 1000, 1090, 1180
    weather = raw_weather(times=[990, 1095, 1500], track_temps=[30.0, 31.0, 40.0])
    df = build_processed_laps(laps, weather, METADATA, RULES)
    assert df["track_temp_c"].tolist() == [30.0, 30.0, 31.0]


# ------------------------------------------------------------------ clean laps and the whole build

def test_clean_lap_rules():
    rows = [
        raw_lap(lap=1, start=1000.0),                                  # first lap
        raw_lap(lap=2, start=1090.0),                                  # clean
        raw_lap(lap=3, start=1180.0, deleted=True),                    # deleted
        raw_lap(lap=4, start=1270.0, compound="INTERMEDIATE"),         # wet
        raw_lap(lap=5, start=1360.0, compound="None"),                 # no tyre info
        raw_lap(lap=6, start=1450.0, status="12"),                     # yellow
        raw_lap(lap=7, start=1540.0, lap_time=None),                   # no lap time
    ]
    df = build_processed_laps(raw_laps(rows), raw_weather([900], [30.0]), METADATA, RULES)
    assert df["is_clean"].tolist() == [False, True, False, False, False, False, False]


def test_full_build_matches_the_schema():
    rows = one_driver(["1", "1", "4", "41", "1", "1", "1"]) + one_driver(["1"] * 7, driver="HAM", lap_time=91.0)
    df = build_processed_laps(raw_laps(rows), raw_weather([900, 1300], [30.0, 31.0]), METADATA, RULES)
    PROCESSED_LAPS_SCHEMA.validate(df)


def test_schema_rejects_impossible_values():
    df = build_processed_laps(raw_laps(one_driver(["1"] * 3)), raw_weather([900], [30.0]), METADATA, RULES)
    df.loc[1, "lap_time_s"] = 300.0  # a clean lap can't take 5 minutes
    with pytest.raises(Exception):
        PROCESSED_LAPS_SCHEMA.validate(df)


# ------------------------------------------------------------------ D18: past only

def test_adding_later_laps_does_not_change_earlier_rows():
    """Every column must use only this lap and earlier laps, so live and training data match."""
    full_rows = (one_driver(["1", "1", "4", "4", "41", "1", "1", "451", "1", "1", "1", "1"], position=1.0)
                 + one_driver(["1", "1", "4", "4", "41", "1", "1", "451", "1", "1", "1", "1"],
                              driver="HAM", lap_time=90.5, position=2.0))
    weather = raw_weather(times=[900, 1200, 1500, 1800, 2100], track_temps=[30, 31, 32, 31, 30])
    full = build_processed_laps(raw_laps(full_rows), weather, METADATA, RULES)

    cut_lap = 6
    early_rows = [r for r in full_rows if r["LapNumber"] <= cut_lap]
    known_by_then = weather[weather["Time"] <= pd.Timedelta(seconds=1000 + cut_lap * 90.5)]
    partial = build_processed_laps(raw_laps(early_rows), known_by_then, METADATA, RULES)

    pd.testing.assert_frame_equal(full[full["lap_number"] <= cut_lap].reset_index(drop=True), partial)
