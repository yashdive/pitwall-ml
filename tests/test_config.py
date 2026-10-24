import pytest
from pydantic import ValidationError

from f1_intelligence.config import load_ingestion_config


def write_config(tmp_path, body):
    (tmp_path / "configs").mkdir()
    path = tmp_path / "configs" / "ingestion.yaml"
    path.write_text(body)
    return path


def test_relative_paths_resolve_against_project_root(tmp_path, monkeypatch):
    path = write_config(tmp_path, "storage:\n  raw_uri: data/raw\n  cache_uri: data/cache/fastf1\n")
    monkeypatch.chdir(tmp_path / "configs")  # e.g. running from research/

    storage = load_ingestion_config(path).storage

    assert storage.raw_uri == (tmp_path / "data/raw").resolve()
    assert storage.cache_uri == (tmp_path / "data/cache/fastf1").resolve()
    assert storage.compression == "zstd" and storage.overwrite is False


def test_typo_in_config_is_rejected(tmp_path):
    path = write_config(tmp_path, "storage:\n  raw_uri: data/raw\n  cache_uri: c\n  overwite: true\n")

    with pytest.raises(ValidationError):
        load_ingestion_config(path)


def test_repo_config_is_valid():
    load_ingestion_config("configs/ingestion.yaml")
