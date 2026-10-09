from pathlib import Path

from brickts.store.base import Sample
from brickts.store.sqlite import SqliteTimeseriesStore


def test_wal_pk_roundtrip(tmp_path: Path):
    db = tmp_path / "t.sqlite"
    store = SqliteTimeseriesStore(db)
    mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"
    tid = "abc'; DROP TABLE samples;--"
    store.write(tid, [Sample(ts=1, value=1.0), Sample(ts=2, value=2.0)])
    out = store.read(tid, start=1, end=2)
    assert len(out) == 2
    store.write(tid, [Sample(ts=1, value=9.0)])
    assert store.read(tid)[0].value == 9.0
    store.close()


def test_read_limits(tmp_path: Path):
    store = SqliteTimeseriesStore(tmp_path / "t.sqlite")
    tid = "x"
    store.write(tid, [Sample(ts=i, value=float(i)) for i in range(10)])
    assert len(store.read(tid, limit=3)) == 3
    store.close()
