from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite

from brickts.store.base import Sample, SeriesStats

_SAMPLES_DDL = """
CREATE TABLE IF NOT EXISTS samples (
    timeseries_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    value REAL,
    PRIMARY KEY (timeseries_id, ts)
) WITHOUT ROWID
"""
_INGEST_LOG_DDL = """
CREATE TABLE IF NOT EXISTS ingest_log (
    dataset_key TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    ingested_at TEXT NOT NULL
)
"""


class SqliteTimeseriesStore:
    """Async SQLite TSDB stand-in (aiosqlite, WAL, one connection + lock)."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    @property
    def path(self) -> Path:
        return self._path

    async def _open_if_needed(self) -> aiosqlite.Connection:
        """Caller must hold ``self._lock``."""
        if self._conn is not None:
            return self._conn
        conn = await aiosqlite.connect(self._path)
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute(_SAMPLES_DDL)
        await conn.execute(_INGEST_LOG_DDL)
        await conn.commit()
        self._conn = conn
        return conn

    async def read(
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
        async with self._lock:
            conn = await self._open_if_needed()
            cur = await conn.execute(sql, params)
            rows = await cur.fetchall()
        return [
            Sample(ts=int(r[0]), value=float(r[1]) if r[1] is not None else float("nan"))
            for r in rows
        ]

    async def write(self, timeseries_id: str, samples: list[Sample]) -> int:
        if not samples:
            return 0
        rows = [(timeseries_id, s.ts, s.value) for s in samples]
        async with self._lock:
            conn = await self._open_if_needed()
            await conn.executemany(
                "INSERT INTO samples (timeseries_id, ts, value) VALUES (?, ?, ?)"
                " ON CONFLICT(timeseries_id, ts) DO UPDATE SET value = excluded.value",
                rows,
            )
            await conn.commit()
        return len(samples)

    async def exists(self, timeseries_id: str) -> bool:
        async with self._lock:
            conn = await self._open_if_needed()
            cur = await conn.execute(
                "SELECT 1 FROM samples WHERE timeseries_id = ? LIMIT 1", (timeseries_id,)
            )
            row = await cur.fetchone()
        return row is not None

    async def series_ids(self) -> set[str]:
        async with self._lock:
            conn = await self._open_if_needed()
            cur = await conn.execute("SELECT DISTINCT timeseries_id FROM samples")
            rows = await cur.fetchall()
        return {str(r[0]) for r in rows}

    async def stats(self, timeseries_id: str) -> SeriesStats | None:
        async with self._lock:
            conn = await self._open_if_needed()
            cur = await conn.execute(
                "SELECT COUNT(*), MIN(ts), MAX(ts) FROM samples WHERE timeseries_id = ?",
                (timeseries_id,),
            )
            row = await cur.fetchone()
        if row is None or row[0] == 0:
            return None
        return SeriesStats(
            timeseries_id=timeseries_id,
            count=int(row[0]),
            min_ts=int(row[1]) if row[1] is not None else None,
            max_ts=int(row[2]) if row[2] is not None else None,
        )

    async def ingest_log_get(self, dataset_key: str) -> tuple[str, int] | None:
        async with self._lock:
            conn = await self._open_if_needed()
            cur = await conn.execute(
                "SELECT sha256, row_count FROM ingest_log WHERE dataset_key = ?", (dataset_key,)
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return str(row[0]), int(row[1])

    async def ingest_log_set(
        self, dataset_key: str, sha256: str, row_count: int, ingested_at: str
    ) -> None:
        async with self._lock:
            conn = await self._open_if_needed()
            await conn.execute(
                "INSERT INTO ingest_log (dataset_key, sha256, row_count, ingested_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(dataset_key) DO UPDATE SET"
                " sha256 = excluded.sha256, row_count = excluded.row_count,"
                " ingested_at = excluded.ingested_at",
                (dataset_key, sha256, row_count, ingested_at),
            )
            await conn.commit()

    async def close(self) -> None:
        async with self._lock:
            if self._conn is not None:
                await self._conn.close()
                self._conn = None
