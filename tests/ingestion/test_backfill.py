from f1_intelligence.ingestion import backfill as backfill_module
from f1_intelligence.ingestion.backfill import backfill
from f1_intelligence.ingestion.data_writer import ParquetWriter
from f1_intelligence.ingestion.fastf1_loader import (
    DataNotAvailable,
    RateLimited,
    SessionKey,
    SessionNotFound,
)
from tests.ingestion.test_data_writer import make_session

K1, K2, K3, K4 = (SessionKey(2024, r, "R") for r in (1, 2, 3, 4))


def fake_loader(monkeypatch, outcomes):
    """outcomes: SessionKey -> exception to raise, or None to return a session."""
    loaded = []

    def load_session(key):
        loaded.append(key)
        if outcomes.get(key):
            raise outcomes[key]
        return make_session(key)

    monkeypatch.setattr(backfill_module, "load_session", load_session)
    return loaded


def test_resumes_by_skipping_existing_sessions(tmp_path, monkeypatch):
    writer = ParquetWriter(tmp_path)
    writer.write(make_session(K1))
    loaded = fake_loader(monkeypatch, {})

    report = backfill([K1, K2], writer)

    assert loaded == [K2]
    assert report.counts == {"skipped_existing": 1, "written": 1}


def test_classifies_errors_and_keeps_going(tmp_path, monkeypatch):
    fake_loader(monkeypatch, {
        K1: SessionNotFound("no sprint"),
        K2: DataNotAvailable("not published"),
        K3: ValueError("unexpected"),
    })

    report = backfill([K1, K2, K3, K4], ParquetWriter(tmp_path))

    assert report.counts == {"not_found": 1, "not_available": 1, "failed": 1, "written": 1}
    assert report.pending == [K2]
    assert report.failed == [K3]


def test_stops_on_rate_limit(tmp_path, monkeypatch):
    loaded = fake_loader(monkeypatch, {K2: RateLimited("slow down")})

    report = backfill([K1, K2, K3], ParquetWriter(tmp_path))

    assert loaded == [K1, K2]
    assert report.stopped_early


def test_waits_on_rate_limit_then_retries_same_session(tmp_path, monkeypatch):
    attempts = []

    def load_session(key):
        attempts.append(key)
        if key == K2 and attempts.count(K2) == 1:
            raise RateLimited("slow down")
        return make_session(key)

    monkeypatch.setattr(backfill_module, "load_session", load_session)
    sleeps = []

    report = backfill([K1, K2, K3], ParquetWriter(tmp_path), rate_limit_wait_s=3660, sleep=sleeps.append)

    assert sleeps == [3660]
    assert attempts == [K1, K2, K2, K3]
    assert report.counts["written"] == 3 and not report.stopped_early
