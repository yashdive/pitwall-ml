"""Fetch one F1 session from FastF1 and return it as plain, self-describing tables.

Sessions are identified by (season, round, session code)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import fastf1
import pandas as pd
from fastf1.exceptions import DataNotLoadedError, RateLimitExceededError

# Schedule session names -> FastF1 session codes.
SESSION_CODES = {
    "Practice 1": "FP1",
    "Practice 2": "FP2",
    "Practice 3": "FP3",
    "Qualifying": "Q",
    "Sprint Shootout": "SS",
    "Sprint Qualifying": "SQ",
    "Sprint": "S",
    "Race": "R",
}

# Columns stamped on every table so rows stay identifiable once sessions are combined.
KEY_COLUMNS = ["Season", "Round", "Session"]

REQUIRED_TABLES = ("laps",)
OPTIONAL_TABLES = ("weather", "results", "track_status", "race_control")


class IngestionError(Exception):
    """Session could not be ingested; not expected to fix itself."""


class SessionNotFound(IngestionError):
    """The session does not exist (bad round, or e.g. no sprint that weekend)."""


class DataNotAvailable(IngestionError):
    """The session exists but its data is not published yet; retry later."""


class RateLimited(IngestionError):
    """FastF1 / F1 timing API rate limit hit; retry later."""


@dataclass(frozen=True)
class SessionKey:
    season: int
    round: int
    session: str  # FastF1 session code, see SESSION_CODES

    def __str__(self) -> str:
        return f"{self.season}-R{self.round:02d}-{self.session}"


@dataclass
class SessionData:
    key: SessionKey
    laps: pd.DataFrame
    weather: pd.DataFrame
    results: pd.DataFrame
    track_status: pd.DataFrame
    race_control: pd.DataFrame
    metadata: dict = field(default_factory=dict)

    def tables(self) -> dict[str, pd.DataFrame]:
        return {name: getattr(self, name) for name in REQUIRED_TABLES + OPTIONAL_TABLES}


def enable_cache(cache_dir: str | Path) -> None:
    """Use a project-controlled HTTP cache so re-runs and resumed backfills are cheap."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))


def list_sessions(
    season: int,
    sessions: list[str] | None = None,
    now: datetime | None = None,
) -> list[SessionKey]:
    """Sessions of a season that have already started, from the official schedule.

    `sessions` filters by code (e.g. ["Q", "R"]); `now` is injectable for tests.
    Testing events (round 0) are excluded.
    """
    now = now or datetime.now(timezone.utc)
    schedule = fastf1.get_event_schedule(season, include_testing=False)

    keys = []
    for _, event in schedule.iterrows():
        for i in range(1, 6):
            code = SESSION_CODES.get(event[f"Session{i}"])
            start = event[f"Session{i}DateUtc"]
            if code is None or pd.isna(start):
                continue
            if sessions is not None and code not in sessions:
                continue
            if start.tz_localize(timezone.utc) > now:
                continue
            keys.append(SessionKey(season, int(event["RoundNumber"]), code))
    return keys


def load_session(key: SessionKey) -> SessionData:
    """Load laps, weather, results, track status and race control messages for one session.

    Raises SessionNotFound, DataNotAvailable or RateLimited so callers (the
    orchestrator) can decide between skip, retry later, and alert.
    """
    try:
        session = fastf1.get_session(key.season, key.round, key.session)
    except ValueError as e:
        raise SessionNotFound(f"{key}: {e}") from e

    if session.date is not None and session.date > datetime.now(timezone.utc).replace(tzinfo=None):
        raise DataNotAvailable(f"{key}: session starts at {session.date} UTC")

    try:
        # load() does not raise when data is missing; it logs warnings and the
        # error only surfaces when accessing the attribute (DataNotLoadedError).
        session.load(laps=True, weather=True, messages=True, telemetry=False)
    except RateLimitExceededError as e:
        raise RateLimited(f"{key}: {e}") from e
    except Exception as e:
        raise IngestionError(f"{key}: FastF1 failed to load session: {e}") from e

    laps = _read_table(session, "laps")
    if laps is None or laps.empty:
        raise DataNotAvailable(f"{key}: no lap data available")

    raw = {
        "weather": _read_table(session, "weather_data"),
        "results": _read_table(session, "results"),
        "track_status": _read_table(session, "track_status"),
        "race_control": _read_table(session, "race_control_messages"),
    }
    missing = [name for name, df in raw.items() if df is None or df.empty]

    return SessionData(
        key=key,
        laps=_with_key(laps, key),
        **{name: _with_key(df, key) for name, df in raw.items()},
        metadata=_build_metadata(session, key, missing),
    )


def _read_table(session, attr: str) -> pd.DataFrame | None:
    try:
        # FastF1 returns its own DataFrame subclasses (e.g. Laps); store plain pandas.
        return pd.DataFrame(getattr(session, attr)).reset_index(drop=True)
    except DataNotLoadedError:
        return None


def _with_key(df: pd.DataFrame | None, key: SessionKey) -> pd.DataFrame:
    df = pd.DataFrame() if df is None else df.copy()
    df.insert(0, "Session", key.session)
    df.insert(0, "Round", key.round)
    df.insert(0, "Season", key.season)
    return df


def _build_metadata(session, key: SessionKey, missing_tables: list[str]) -> dict:
    event = session.event
    return {
        "season": key.season,
        "round": key.round,
        "session": key.session,
        "session_name": session.name,
        "session_start_utc": session.date.isoformat() if session.date is not None else None,
        "event_name": event["EventName"],
        "official_event_name": event["OfficialEventName"],
        "country": event["Country"],
        "location": event["Location"],
        "event_format": event["EventFormat"],
        "missing_tables": missing_tables,
        # Lineage: which library version produced this data, and when.
        "fastf1_version": fastf1.__version__,
        "ingested_at_utc": datetime.now(timezone.utc).isoformat(),
    }
