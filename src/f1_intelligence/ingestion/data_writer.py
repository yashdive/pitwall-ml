"""Persist SessionData to the raw layer as Hive-partitioned Parquet.

Layout (one file per table per session):

    {raw_uri}/{table}/season=2024/round=10/session=R/data.parquet
    {raw_uri}/metadata/season=2024/round=10/session=R/metadata.json

The metadata file is written last and acts as the commit marker: a session
counts as ingested only if its metadata exists, so a crash mid-write is
retried on the next run instead of leaving a half-written session behind.
"""

import json
import os
from pathlib import Path

from f1_intelligence.ingestion.fastf1_loader import KEY_COLUMNS, SessionData, SessionKey

METADATA_TABLE = "metadata"


class ParquetWriter:
    def __init__(self, raw_uri: str | Path, compression: str = "zstd"):
        self.raw_uri = Path(raw_uri)
        self.compression = compression

    def partition_dir(self, table: str, key: SessionKey) -> Path:
        return self.raw_uri / table / f"season={key.season}" / f"round={key.round}" / f"session={key.session}"

    def metadata_path(self, key: SessionKey) -> Path:
        return self.partition_dir(METADATA_TABLE, key) / "metadata.json"

    def exists(self, key: SessionKey) -> bool:
        return self.metadata_path(key).exists()

    def write(self, data: SessionData, overwrite: bool = False) -> bool:
        """Write all tables of a session. Returns False if skipped because it already exists."""
        key = data.key
        if self.exists(key) and not overwrite:
            return False

        # Un-commit first so an interrupted overwrite is never mistaken for a complete session.
        self.metadata_path(key).unlink(missing_ok=True)

        for table, df in data.tables().items():
            path = self.partition_dir(table, key) / "data.parquet"
            if df.drop(columns=KEY_COLUMNS).empty:
                # Optional table missing for this session (recorded in metadata["missing_tables"]);
                # remove any stale file from a previous ingestion.
                path.unlink(missing_ok=True)
                continue
            _atomic_write(path, lambda tmp: df.to_parquet(tmp, index=False, compression=self.compression))

        metadata_json = json.dumps(data.metadata, indent=2, ensure_ascii=False, default=str)
        _atomic_write(self.metadata_path(key), lambda tmp: tmp.write_text(metadata_json, encoding="utf-8"))
        return True


def _atomic_write(path: Path, write) -> None:
    """Write to a temp file then rename: readers never see a partially written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        write(tmp)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
