from __future__ import annotations

import sqlite3
from pathlib import Path

from brickts.store.base import Sample, SeriesStats


class SqliteTimeseriesStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS samples (
                timeseries_id TEXT NOT NULL,
                ts INTEGER NOT NULL,
                value REAL,
                PRIMARY KEY (timeseries_id, ts)
            ) WITHOUT ROWID
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ingest_log (
                dataset_key TEXT PRIMARY KEY,
                sha256 TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                ingested_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    @property
    def path(self) -> Path:
        return self._path

    def read(
        self,
        timeseries_id: str,
        *,
        start: int | None = None,
        end: int | None = None,
        limit: int | None = None,
    ) -> list[Sample]:
        clauses = ["timeseries_id = ?"]
        params: list[object] = [timeseries_id]
        if start is not None:
            clauses.append("ts >= ?")
            params.append(start)
        if end is not None:
            clauses.append("ts <= ?")
            params.append(end)
        sql = f"SELECT ts, value FROM samples WHERE {' AND '.join(clauses)} ORDER BY ts ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        cur = self._conn.execute(sql, params)
        return [
            Sample(ts=int(r[0]), value=float(r[1]) if r[1] is not None else float("nan"))
            for r in cur
        ]

    def write(self, timeseries_id: str, samples: list[Sample]) -> int:
        if not samples:
            return 0
        self._conn.executemany(
            "INSERT INTO samples (timeseries_id, ts, value) VALUES (?, ?, ?)"
            " ON CONFLICT(timeseries_id, ts) DO UPDATE SET value = excluded.value",
            [(timeseries_id, s.ts, s.value) for s in samples],
        )
        self._conn.commit()
        return len(samples)

    def exists(self, timeseries_id: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM samples WHERE timeseries_id = ? LIMIT 1", (timeseries_id,)
        )
        return cur.fetchone() is not None

    def series_ids(self) -> set[str]:
        cur = self._conn.execute("SELECT DISTINCT timeseries_id FROM samples")
        return {str(r[0]) for r in cur}

    def stats(self, timeseries_id: str) -> SeriesStats | None:
        cur = self._conn.execute(
            "SELECT COUNT(*), MIN(ts), MAX(ts) FROM samples WHERE timeseries_id = ?",
            (timeseries_id,),
        )
        row = cur.fetchone()
        if row is None or row[0] == 0:
            return None
        return SeriesStats(
            timeseries_id=timeseries_id,
            count=int(row[0]),
            min_ts=int(row[1]) if row[1] is not None else None,
            max_ts=int(row[2]) if row[2] is not None else None,
        )

    def ingest_log_get(self, dataset_key: str) -> tuple[str, int] | None:
        cur = self._conn.execute(
            "SELECT sha256, row_count FROM ingest_log WHERE dataset_key = ?", (dataset_key,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        return str(row[0]), int(row[1])

    def ingest_log_set(
        self, dataset_key: str, sha256: str, row_count: int, ingested_at: str
    ) -> None:
        self._conn.execute(
            "INSERT INTO ingest_log (dataset_key, sha256, row_count, ingested_at)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(dataset_key) DO UPDATE SET"
            " sha256 = excluded.sha256, row_count = excluded.row_count,"
            " ingested_at = excluded.ingested_at",
            (dataset_key, sha256, row_count, ingested_at),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
