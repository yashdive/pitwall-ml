"""The data contract of the processed lap table. `f1-process` stops if a race breaks it."""

import pandera.pandas as pa

from f1_intelligence.processing.transforms import COLUMNS, DRY_COMPOUNDS, KEY, PIT_TYPES, WET_COMPOUNDS

FLAGS = [
    "fresh_tyre", "is_first_lap", "has_lap_time", "has_tyre_info", "is_wet_compound",
    "is_pit_in_lap", "is_pit_out_lap", "is_green", "yellow_in_lap", "sc_in_lap",
    "vsc_in_lap", "red_in_lap", "is_restart_lap", "is_deleted", "is_accurate",
    "in_traffic", "is_clean",
]


def _text(nullable: bool = False, **kwargs) -> pa.Column:
    return pa.Column("string", nullable=nullable, **kwargs)


def _seconds(nullable: bool = True, *checks) -> pa.Column:
    return pa.Column("float64", list(checks), nullable=nullable)


PROCESSED_LAPS_SCHEMA = pa.DataFrameSchema(
    columns={
        "season": pa.Column("int64", pa.Check.ge(2018)),
        "round": pa.Column("int64", pa.Check.ge(1)),
        "session": _text(),
        "driver": _text(),
        "lap_number": pa.Column("int64", pa.Check.ge(1)),
        "team": _text(nullable=True),
        "event_name": _text(nullable=True),
        "location": _text(nullable=True),
        "event_format": _text(nullable=True),
        # Red-flag laps can include the whole stoppage, so the overall range is wide;
        # clean laps get a tighter check below.
        "lap_time_s": _seconds(True, pa.Check.between(50, 3600)),
        "sector1_s": _seconds(True, pa.Check.ge(0)),
        "sector2_s": _seconds(True, pa.Check.ge(0)),
        "sector3_s": _seconds(True, pa.Check.ge(0)),
        "lap_start_s": _seconds(False, pa.Check.ge(0)),
        "lap_end_s": _seconds(False, pa.Check.ge(0)),
        "pit_in_s": _seconds(True, pa.Check.ge(0)),
        "pit_out_s": _seconds(True, pa.Check.ge(0)),
        "compound": _text(nullable=True, checks=pa.Check.isin(DRY_COMPOUNDS + WET_COMPOUNDS)),
        "tyre_life": pa.Column("Int64", pa.Check.ge(1), nullable=True),
        "stint": pa.Column("Int64", pa.Check.ge(1), nullable=True),
        "position": pa.Column("Int64", pa.Check.between(1, 30), nullable=True),
        "track_status": _text(checks=pa.Check.str_matches(r"^[1-7]*$")),
        "pit_type": _text(nullable=True, checks=pa.Check.isin(PIT_TYPES)),
        "laps_since_neutralisation": pa.Column("Int64", pa.Check.ge(0), nullable=True),
        "gap_ahead_s": _seconds(True, pa.Check.ge(0)),
        "track_temp_c": _seconds(True, pa.Check.between(-10, 80)),
        "air_temp_c": _seconds(True, pa.Check.between(-10, 60)),
        "humidity_pct": _seconds(True, pa.Check.between(0, 100)),
        "rainfall": pa.Column("boolean", nullable=True),
        **{flag: pa.Column("bool") for flag in FLAGS},
    },
    checks=[
        pa.Check(lambda d: d.loc[d["is_clean"], "lap_time_s"].between(60, 200).all(),
                 error="clean laps must be between 60 and 200 s"),
        pa.Check(lambda d: d["pit_type"].notna().eq(d["is_pit_in_lap"]).where(d["is_pit_in_lap"], True).all(),
                 error="every pit-in lap must have a pit_type"),
    ],
    unique=KEY,
    strict=True,
)

assert set(PROCESSED_LAPS_SCHEMA.columns) == set(COLUMNS), "schema and COLUMNS are out of sync"
