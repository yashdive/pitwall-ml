"""Small file helpers shared by every layer that writes data."""

import os
from pathlib import Path


def atomic_write(path: Path, write) -> None:
    """Write to a temp file then rename: readers never see a partially written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        write(tmp)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def partition_dir(root: Path, table: str, season: int, round: int, session: str) -> Path:
    """Hive-style folder for one session, e.g. {root}/laps/season=2024/round=3/session=R."""
    return Path(root) / table / f"season={season}" / f"round={round}" / f"session={session}"
