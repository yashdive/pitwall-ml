from datetime import datetime, timezone

import fastf1
import pandas as pd
import pytest
from fastf1.exceptions import DataNotLoadedError

from f1_intelligence.ingestion import fastf1_loader as loader
from f1_intelligence.ingestion.fastf1_loader import (
    DataNotAvailable,
    SessionKey,
    SessionNotFound,
    list_sessions,
    load_session,
)

KEY = SessionKey(2024, 10, "R")


class FakeLaps(pd.DataFrame):
    """Stands in for fastf1.core.Laps, a DataFrame subclass."""

    @property
    def _constructor(self):
        return FakeLaps


class FakeSession:
    """Mimics FastF1: load() never raises, missing tables raise on attribute access."""

    def __init__(self, laps=None, weather=None, date=pd.Timestamp("2024-06-23 13:00")):
        self._laps = laps
        self._weather = weather
        self.date = date
        self.name = "Race"
        self.event = pd.Series({
            "EventName": "Spanish Grand Prix",
            "OfficialEventName": "FORMULA 1 ARAMCO GRAN PREMIO DE ESPAÑA 2024",
            "Country": "Spain",
            "Location": "Barcelona",
            "EventFormat": "conventional",
        })
        self.results = pd.DataFrame({"Abbreviation": ["VER"], "Position": [1.0]})
        self.loaded = False

    def load(self, **kwargs):
        self.loaded = True

    @property
    def laps(self):
        if self._laps is None:
            raise DataNotLoadedError("no laps")
        return self._laps

    @property
    def weather_data(self):
        if self._weather is None:
            raise DataNotLoadedError("no weather")
        return self._weather

    @property
    def track_status(self):
        raise DataNotLoadedError("no track status")

    @property
    def race_control_messages(self):
        raise DataNotLoadedError("no messages")


def sample_laps():
    return FakeLaps({
        "Driver": ["VER", "VER"],
        "LapNumber": [1.0, 2.0],
        "LapTime": pd.to_timedelta([80.1, 79.9], unit="s"),
    })


@pytest.fixture
def fake_session(monkeypatch):
    def install(session):
        monkeypatch.setattr(fastf1, "get_session", lambda *args: session)
        return session
    return install


def test_tables_are_plain_dataframes_stamped_with_key(fake_session):
    fake_session(FakeSession(laps=sample_laps(), weather=pd.DataFrame({"AirTemp": [25.0]})))

    data = load_session(KEY)

    assert type(data.laps) is pd.DataFrame
    for name, df in data.tables().items():
        assert list(df.columns[:3]) == ["Season", "Round", "Session"], name
    assert data.laps[["Season", "Round", "Session"]].drop_duplicates().values.tolist() == [[2024, 10, "R"]]
    assert len(data.laps) == 2


def test_missing_optional_tables_are_empty_and_recorded(fake_session):
    fake_session(FakeSession(laps=sample_laps(), weather=None))

    data = load_session(KEY)

    assert data.weather.drop(columns=["Season", "Round", "Session"]).empty
    assert data.metadata["missing_tables"] == ["weather", "track_status", "race_control"]


def test_missing_laps_means_data_not_available(fake_session):
    fake_session(FakeSession(laps=None))

    with pytest.raises(DataNotAvailable):
        load_session(KEY)


def test_future_session_is_not_loaded(fake_session):
    session = fake_session(FakeSession(laps=sample_laps(), date=pd.Timestamp("2099-01-01")))

    with pytest.raises(DataNotAvailable):
        load_session(KEY)
    assert not session.loaded


def test_nonexistent_session_raises_session_not_found(monkeypatch):
    def get_session(*args):
        raise ValueError("Session type 'S' does not exist for this event")
    monkeypatch.setattr(fastf1, "get_session", get_session)

    with pytest.raises(SessionNotFound):
        load_session(SessionKey(2024, 10, "S"))


def test_metadata_has_identity_and_lineage(fake_session):
    fake_session(FakeSession(laps=sample_laps()))

    meta = load_session(KEY).metadata

    assert (meta["season"], meta["round"], meta["session"]) == (2024, 10, "R")
    assert meta["event_name"] == "Spanish Grand Prix"
    assert meta["fastf1_version"] == fastf1.__version__
    assert meta["ingested_at_utc"]


def test_list_sessions_maps_codes_and_skips_future(monkeypatch):
    def ts(s):
        return pd.Timestamp(s)

    schedule = pd.DataFrame([
        {"RoundNumber": 1, **_sessions(["Practice 1", "Practice 2", "Practice 3", "Qualifying", "Race"],
                                       ts("2026-03-06"))},
        {"RoundNumber": 2, **_sessions(["Practice 1", "Sprint Qualifying", "Sprint", "Qualifying", "Race"],
                                       ts("2026-12-01"))},
    ])
    monkeypatch.setattr(fastf1, "get_event_schedule", lambda *a, **k: schedule)

    keys = list_sessions(2026, now=datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert [k.session for k in keys] == ["FP1", "FP2", "FP3", "Q", "R"]
    assert {k.round for k in keys} == {1}

    races = list_sessions(2026, sessions=["R"], now=datetime(2027, 1, 1, tzinfo=timezone.utc))
    assert races == [SessionKey(2026, 1, "R"), SessionKey(2026, 2, "R")]


def _sessions(names, start):
    row = {}
    for i, name in enumerate(names, start=1):
        row[f"Session{i}"] = name
        row[f"Session{i}DateUtc"] = start + pd.Timedelta(hours=i)
    return row


@pytest.mark.integration
def test_real_session_spain_2024():
    data = load_session(SessionKey(2024, 10, "R"))

    assert data.metadata["location"] == "Barcelona"
    assert data.laps["Driver"].nunique() == 20
    assert not data.results.empty and not data.track_status.empty
    assert data.metadata["missing_tables"] == []


@pytest.mark.integration
def test_event_identity_is_by_round_not_name():
    # The reason we never use names: in 2026 "Spain" fuzzy-matches Madrid, not Barcelona.
    barcelona = fastf1.get_session(2026, 7, "R").event
    assert barcelona["Location"] == "Barcelona"
    assert fastf1.get_session(2026, "Spain", "R").event["Location"] == "Madrid"
