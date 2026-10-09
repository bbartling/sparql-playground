import asyncio
from pathlib import Path

from brickts.store.base import Sample
from brickts.store.sqlite import SqliteTimeseriesStore


async def _wal_pk_roundtrip(db: Path) -> None:
    store = SqliteTimeseriesStore(db)
    async with store._lock:
        conn = await store._open_if_needed()
        cur = await conn.execute("PRAGMA journal_mode")
        mode = (await cur.fetchone())[0]
    assert str(mode).lower() == "wal"
    tid = "abc'; DROP TABLE samples;--"
    await store.write(tid, [Sample(ts=1, value=1.0), Sample(ts=2, value=2.0)])
    out = await store.read(tid, start=1, end=2)
    assert len(out) == 2
    await store.write(tid, [Sample(ts=1, value=9.0)])
    assert (await store.read(tid))[0].value == 9.0
    await store.close()


def test_wal_pk_roundtrip(tmp_path: Path):
    asyncio.run(_wal_pk_roundtrip(tmp_path / "t.sqlite"))


async def _read_limits(db: Path) -> None:
    store = SqliteTimeseriesStore(db)
    tid = "x"
    await store.write(tid, [Sample(ts=i, value=float(i)) for i in range(10)])
    assert len(await store.read(tid, limit=3)) == 3
    await store.close()


def test_read_limits(tmp_path: Path):
    asyncio.run(_read_limits(tmp_path / "t.sqlite"))
