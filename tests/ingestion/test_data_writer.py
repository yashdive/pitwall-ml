import json

import duckdb
import pandas as pd
import pytest

from f1_intelligence.ingestion import data_writer
from f1_intelligence.ingestion.data_writer import ParquetWriter
from f1_intelligence.ingestion.fastf1_loader import SessionData, SessionKey, _with_key

KEY = SessionKey(2024, 10, "R")


def make_session(key=KEY, weather=True, lap_time=80.0):
    empty = pd.DataFrame()
    return SessionData(
        key=key,
        laps=_with_key(pd.DataFrame({
            "Driver": ["VER", "NOR"],
            "LapTime": pd.to_timedelta([lap_time, lap_time + 0.5], unit="s"),
        }), key),
        weather=_with_key(pd.DataFrame({"AirTemp": [25.0]}) if weather else empty, key),
        results=_with_key(pd.DataFrame({"Abbreviation": ["VER", "NOR"]}), key),
        track_status=_with_key(empty, key),
        race_control=_with_key(empty, key),
        metadata={"season": key.season, "round": key.round, "session": key.session,
                  "missing_tables": ["track_status", "race_control"] + ([] if weather else ["weather"])},
    )


def test_writes_hive_partitioned_layout(tmp_path):
    writer = ParquetWriter(tmp_path)

    assert writer.write(make_session()) is True

    base = "season=2024/round=10/session=R"
    assert (tmp_path / "laps" / base / "data.parquet").exists()
    assert (tmp_path / "weather" / base / "data.parquet").exists()
    assert json.loads((tmp_path / "metadata" / base / "metadata.json").read_text())["round"] == 10
    # Empty optional tables are not written; metadata records them instead.
    assert not (tmp_path / "track_status" / base).exists()
    assert writer.exists(KEY)


def test_existing_session_is_skipped_unless_overwrite(tmp_path):
    writer = ParquetWriter(tmp_path)
    writer.write(make_session(lap_time=80.0))

    assert writer.write(make_session(lap_time=99.0)) is False
    assert _first_lap_s(tmp_path) == 80.0

    assert writer.write(make_session(lap_time=99.0), overwrite=True) is True
    assert _first_lap_s(tmp_path) == 99.0


def test_overwrite_removes_table_that_is_now_missing(tmp_path):
    writer = ParquetWriter(tmp_path)
    writer.write(make_session(weather=True))

    writer.write(make_session(weather=False), overwrite=True)

    assert not (tmp_path / "weather/season=2024/round=10/session=R/data.parquet").exists()


def test_crash_mid_write_leaves_session_uncommitted(tmp_path, monkeypatch):
    writer = ParquetWriter(tmp_path)
    calls = {"n": 0}
    real = data_writer._atomic_write

    def crash_on_second_file(path, write):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disk full")
        real(path, write)

    monkeypatch.setattr(data_writer, "_atomic_write", crash_on_second_file)
    with pytest.raises(OSError):
        writer.write(make_session())

    assert not writer.exists(KEY)  # will be retried on the next run
    assert not list(tmp_path.rglob("*.tmp"))


def test_sessions_query_as_one_table_with_duckdb(tmp_path):
    writer = ParquetWriter(tmp_path)
    writer.write(make_session(SessionKey(2024, 10, "R")))
    writer.write(make_session(SessionKey(2024, 11, "R")))
    writer.write(make_session(SessionKey(2025, 9, "Q")))

    rows = duckdb.sql(f"""
        SELECT Season, Round, Session, count(*) AS n
        FROM read_parquet('{tmp_path}/laps/**/*.parquet', hive_partitioning = true)
        WHERE Season = 2024
        GROUP BY ALL ORDER BY Round
    """).fetchall()

    assert rows == [(2024, 10, "R", 2), (2024, 11, "R", 2)]


def _first_lap_s(root):
    df = pd.read_parquet(root / "laps/season=2024/round=10/session=R/data.parquet")
    return df["LapTime"].iloc[0].total_seconds()
