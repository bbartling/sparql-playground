"""Shared helpers for the daily lessons. Every lesson starts with:

    import lab
    conn = lab.connect()

and then does each computation twice: once as SQL (a SQLite string run through stdlib ``sqlite3``)
and once in pandas, and checks the two answers are the same with ``lab.assert_parity``. That's the
pattern Open-FDD's parity tests use (``tests/parity`` there: pandas oracle == SQL rule pack).

``lessons/course.py run N`` runs lesson N's ```python blocks on a temporary copy of the database,
so nothing a lesson does touches ``var/timeseries.sqlite``. ``course.py check`` runs them all.
"""

from __future__ import annotations

import csv
import os
import sqlite3
import time
import tracemalloc
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "var" / "timeseries.sqlite"
POINT_CSVS = sorted((ROOT / "model" / "points").glob("*.csv"))
EVENT_CSVS = sorted((ROOT / "data").glob("*/*/fdd_events.csv"))

#: course.py sets this when it runs the checker, so benchmarks use their small sizes.
QUICK = os.environ.get("COURSE_QUICK") == "1"

# ---------------------------------------------------------------- units (SI for fault math)
# The historian logged US units. Fault rules work in SI, like Open-FDD: °C, Pa, fractions 0-1.
PA_PER_INH2O = 249.08891


def f_to_c(f):
    return (f - 32.0) * 5.0 / 9.0


def inh2o_to_pa(x):
    return x * PA_PER_INH2O


# ---------------------------------------------------------------- connecting
def db_path() -> Path:
    """The database a lesson uses: $COURSE_DB (a temp copy, set by course.py) or the real one."""
    return Path(os.environ.get("COURSE_DB", DB))


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path) if path else db_path()
    if not path.exists():
        raise SystemExit(f"{path} not found. Build it first:  uv run bldgts bootstrap")
    return sqlite3.connect(path)


def query(conn: sqlite3.Connection, sql: str, params: Iterable | dict = ()) -> pd.DataFrame:
    """Run one SELECT and return a DataFrame (column names from the SQL)."""
    return pd.read_sql_query(sql, conn, params=params)


# ---------------------------------------------------------------- parity
def assert_parity(
    pandas_df: pd.DataFrame | pd.Series,
    sql_df: pd.DataFrame | pd.Series,
    *,
    keys: list[str] | None = None,
    atol: float = 1e-9,
    rtol: float = 1e-9,
    label: str = "",
) -> None:
    """Fail unless the pandas result and the SQL result hold the same rows and values.

    Like Open-FDD's parity harness, it compares *values*, not types: SQLite returns 0/1 integers
    where pandas has bools, and REAL where pandas has float64. Rows are matched after sorting by
    ``keys`` (default: every column), so row order never matters. Numbers compare with a
    tolerance; NaN equals NaN (SQL NULL == pandas NaN).
    """
    a, b = _frame(pandas_df), _frame(sql_df)
    if set(a.columns) != set(b.columns):
        raise AssertionError(
            f"{label} columns differ: pandas {list(a.columns)} vs SQL {list(b.columns)}"
        )
    b = b[list(a.columns)]
    if len(a) != len(b):
        raise AssertionError(f"{label} row counts differ: pandas {len(a)} vs SQL {len(b)}")
    keys = keys or list(a.columns)
    a = a.sort_values(keys, kind="mergesort").reset_index(drop=True)
    b = b.sort_values(keys, kind="mergesort").reset_index(drop=True)
    for col in a.columns:
        x, y = a[col], b[col]
        xn, yn = pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")
        numeric = xn.notna().sum() == x.notna().sum() and yn.notna().sum() == y.notna().sum()
        if numeric:
            ok = np.isclose(
                xn.astype(float), yn.astype(float), atol=atol, rtol=rtol, equal_nan=True
            )
        else:
            both_null = (x.isna() & y.isna()).to_numpy()  # SQL NULL == None == NaN
            ok = both_null | (x.astype(str) == y.astype(str)).to_numpy()
        if not ok.all():
            i = int(np.argmin(ok))
            raise AssertionError(
                f"{label} column {col!r} differs at row {i}: "
                f"pandas {x.iloc[i]!r} vs SQL {y.iloc[i]!r} "
                f"({int((~ok).sum())} of {len(ok)} rows differ)"
            )
    print(f"parity OK{(' ' + label) if label else ''}: {len(a)} rows x {len(a.columns)} columns")


def _frame(x) -> pd.DataFrame:
    if isinstance(x, pd.Series):
        x = x.to_frame()
    # A named index (e.g. after groupby) is data; an unnamed one (after a filter or sort) isn't.
    unnamed = all(name is None for name in x.index.names)
    x = x.reset_index(drop=unnamed)
    out = x.copy()
    for col in out.columns:
        if out[col].dtype == bool:
            out[col] = out[col].astype(int)
    return out


# ---------------------------------------------------------------- lab tables
def load_points(conn: sqlite3.Connection) -> int:
    """lab_point: the point list the RDF model is built from, flattened into one table.
    equipment_id is the AHU the mapping file belongs to (BUILDING_50__AHU_1.csv -> AHU_1)."""
    conn.execute("DROP TABLE IF EXISTS lab_point")
    conn.execute(
        """CREATE TABLE lab_point (
            timeseries_id TEXT PRIMARY KEY,
            point_id      TEXT NOT NULL,
            equipment_id  TEXT NOT NULL,
            owner_id      TEXT,
            label         TEXT,
            brick_class   TEXT,
            unit          TEXT,
            openfdd_role  TEXT,
            source_column TEXT
        )"""
    )
    rows = []
    for path in POINT_CSVS:
        equipment_id = path.stem.split("__", 1)[1]
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                rows.append(
                    (
                        r["timeseries_id"],
                        r["point_id"],
                        equipment_id,
                        r["owner_id"] or None,
                        r["label"] or None,
                        r["brick_class"] or None,
                        r["unit"] or None,
                        r["openfdd_role"] or None,
                        r["source_column"],
                    )
                )
    conn.executemany("INSERT INTO lab_point VALUES (?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def load_events(conn: sqlite3.Connection) -> int:
    """lab_fdd_event: fault episodes Open-FDD found in this data (for comparing your rules).
    Times become epoch seconds, like samples.ts."""
    conn.execute("DROP TABLE IF EXISTS lab_fdd_event")
    conn.execute(
        """CREATE TABLE lab_fdd_event (
            equipment_id TEXT NOT NULL,
            rule_name    TEXT NOT NULL,
            start_ts     INTEGER NOT NULL,
            end_ts       INTEGER NOT NULL,
            duration_min REAL,
            sample_count INTEGER
        )"""
    )
    rows = []
    for path in EVENT_CSVS:
        equipment_id = path.parent.name
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                rows.append(
                    (
                        equipment_id,
                        r["rule_name"],
                        int(datetime.fromisoformat(r["start_time_utc"]).timestamp()),
                        int(datetime.fromisoformat(r["end_time_utc"]).timestamp()),
                        float(r["duration_min"]),
                        int(r["sample_count"]),
                    )
                )
    conn.executemany("INSERT INTO lab_fdd_event VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def has_table(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (name,)).fetchone()
    return row is not None


def ensure_points(conn: sqlite3.Connection) -> None:
    if not has_table(conn, "lab_point"):
        load_points(conn)


def ensure_events(conn: sqlite3.Connection) -> None:
    if not has_table(conn, "lab_fdd_event"):
        load_events(conn)


# The wide `history` table every Open-FDD rule reads: one row per (equipment, ts), one column per
# role, already in SI. Day 11 builds it step by step; later lessons call ensure_history().
HISTORY_COLUMNS = {
    # column: (openfdd_role, SQL expression on `value` that converts it to SI)
    "fan_status": ("fan-status", "value"),
    "fan_cmd": ("fan-cmd", "value / 100.0"),
    "duct_static": ("duct-static-pressure", f"value * {PA_PER_INH2O}"),
    "duct_static_sp": ("duct-static-pressure-sp", f"value * {PA_PER_INH2O}"),
    "sat": ("discharge-air-temp", "(value - 32.0) * 5.0 / 9.0"),
    "sat_sp": ("discharge-air-temp-sp", "(value - 32.0) * 5.0 / 9.0"),
    "mat": ("mixed-air-temp", "(value - 32.0) * 5.0 / 9.0"),
    "rat": ("return-air-temp", "(value - 32.0) * 5.0 / 9.0"),
    "oat": ("outside-air-temp", "(value - 32.0) * 5.0 / 9.0"),
    "oa_damper": ("outside-air-damper", "value / 100.0"),
    "clg_valve": ("cooling-valve", "value / 100.0"),
    "occupied": ("occupied", "value"),
}


def history_sql() -> str:
    cols = ",\n  ".join(
        f"MAX(CASE WHEN p.openfdd_role = '{role}' "
        f"THEN {expr.replace('value', 's.value')} END) AS {col}"
        for col, (role, expr) in HISTORY_COLUMNS.items()
    )
    return (
        "SELECT p.equipment_id, s.ts,\n  "
        + cols
        + "\nFROM samples s\nJOIN lab_point p ON p.timeseries_id = s.timeseries_id\n"
        "WHERE p.openfdd_role IS NOT NULL\nGROUP BY p.equipment_id, s.ts"
    )


def ensure_history(conn: sqlite3.Connection) -> None:
    """Create lab_history (SI units) if it isn't there yet. Takes a few seconds the first time."""
    ensure_points(conn)
    if has_table(conn, "lab_history"):
        return
    conn.execute("CREATE TABLE lab_history AS " + history_sql())
    conn.execute("CREATE INDEX IF NOT EXISTS lab_history_eq_ts ON lab_history (equipment_id, ts)")
    conn.commit()


def history(conn: sqlite3.Connection, equipment_id: str | None = None) -> pd.DataFrame:
    """lab_history as a DataFrame, sorted by (equipment_id, ts)."""
    ensure_history(conn)
    sql = "SELECT * FROM lab_history"
    params: tuple = ()
    if equipment_id:
        sql += " WHERE equipment_id = ?"
        params = (equipment_id,)
    return query(conn, sql + " ORDER BY equipment_id, ts", params)


# ---------------------------------------------------------------- the FastAPI app, offline
class Api:
    """This repo's FastAPI app (`bldgts serve`), driven in-process with FastAPI's TestClient.

    No server, no network: requests go straight into the app. It reads the same database the
    lesson uses (``db_path()``) and the RDF model ``model/building_50.ttl``
    (``uv run bldgts model build``). Graph snapshots go to a temp folder, so the repo's
    ``building.ttl`` is never rewritten. Use it as a context manager::

        with lab.Api() as api:
            pts = api.sparql(QUERY)              # DataFrame, one column per SELECT variable
            ts = api.timeseries("AHU_1_DA_P")    # DataFrame: ts, value
    """

    def __enter__(self) -> Api:
        import tempfile  # noqa: PLC0415
        import warnings  # noqa: PLC0415

        from bldgts.api.app import create_app  # noqa: PLC0415
        from bldgts.settings import Settings  # noqa: PLC0415

        with warnings.catch_warnings():  # starlette's "use httpx2" notice; not the lesson's concern
            warnings.simplefilter("ignore")
            from fastapi.testclient import TestClient  # noqa: PLC0415

        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        tmp = Path(self._tmp.name)
        settings = Settings().resolve(ROOT)
        settings = settings.model_copy(
            update={
                "db_path": db_path(),
                "snapshot_path": tmp / "graph.snapshot.ttl",
                "tutorial_ttl_path": tmp / "building.ttl",
                "bootstrap_on_startup": False,
                "serialize_interval_s": 0,
                "serialize_on_mutation": False,
                "allow_mutations": False,
                "log_level": "WARNING",
                "log_json": False,
            }
        )
        if not settings.model_path.exists():
            raise SystemExit(
                f"{settings.model_path} not found. Build it:  uv run bldgts model build"
            )
        self._client = TestClient(create_app(settings))
        self._client.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        self._client.__exit__(*exc)
        self._tmp.cleanup()

    def get(self, path: str, **params) -> dict:
        r = self._client.get(path, params=params or None)
        r.raise_for_status()
        return r.json()

    def sparql(self, query: str) -> pd.DataFrame:
        """POST /api/sparql; the SPARQL JSON results become a DataFrame of plain strings/numbers."""
        r = self._client.post("/api/sparql", json={"query": query})
        r.raise_for_status()
        payload = r.json()  # {"results": <SPARQL 1.1 JSON results>, "meta": {row_count, ...}}
        if payload["meta"].get("truncated"):
            raise ValueError("the API capped the SPARQL result rows; narrow the query")
        body = payload["results"]
        cols = body["head"]["vars"]
        rows = [{v: _sparql_value(b.get(v)) for v in cols} for b in body["results"]["bindings"]]
        return pd.DataFrame(rows, columns=cols)

    def timeseries(self, point_id: str, start: int | None = None, end: int | None = None):
        """GET /api/points/{point_id}/timeseries -> DataFrame with columns ts (epoch s), value."""
        params = {k: v for k, v in {"start": start, "end": end}.items() if v is not None}
        body = self.get(f"/api/points/{point_id}/timeseries", **params)
        if body.get("truncated"):
            raise ValueError(f"{point_id}: the API truncated the series; ask for a shorter range")
        df = pd.DataFrame(body["samples"], columns=["ts", "value"])
        df.attrs["timeseries_id"] = body["timeseries_id"]
        return df


def _sparql_value(cell: dict | None):
    if cell is None:
        return None
    value, dtype = cell.get("value"), cell.get("datatype", "")
    if dtype.endswith(("#integer", "#int", "#long")):
        return int(value)
    if dtype.endswith(("#decimal", "#double", "#float")):
        return float(value)
    return value


# ---------------------------------------------------------------- synthetic data (week 4)
def synthetic_history(
    rows_per_equip: int,
    equips: int = 1,
    *,
    step_s: int = 300,
    gap_prob: float = 0.0,
    seed: int = 7,
) -> pd.DataFrame:
    """A deterministic wide history in SI, shaped like lab_history (fewer columns).

    Daily fan schedule (on 06:00-18:00), duct static tracking its setpoint with noise, and an
    injected "weak fan" window in each equipment where static sags ~60 Pa below setpoint.
    ``gap_prob`` drops that fraction of rows at random (an offline controller), so lessons can
    practise gap handling.
    """
    rng = np.random.default_rng(seed)
    frames = []
    t0 = 1_773_619_200  # 2026-03-16 00:00 UTC, the first day of Building 50
    for e in range(equips):
        ts = t0 + np.arange(rows_per_equip, dtype=np.int64) * step_s
        hour = (ts % 86_400) / 3600.0
        fan = ((hour >= 6) & (hour < 18)).astype(float)
        sp = np.full(rows_per_equip, 375.0)
        static = np.where(
            fan == 1, sp + rng.normal(0, 8, rows_per_equip), rng.normal(0, 2, rows_per_equip)
        )
        a = rows_per_equip // 3 + e * 97
        weak = (np.arange(rows_per_equip) >= a) & (
            np.arange(rows_per_equip) < a + rows_per_equip // 10
        )
        static = np.where(weak & (fan == 1), static - 60.0, static)
        oat = 10 + 8 * np.sin((hour - 9) / 24 * 2 * np.pi) + rng.normal(0, 0.3, rows_per_equip)
        df = pd.DataFrame(
            {
                "equipment_id": f"AHU_{e + 1}",
                "ts": ts,
                "fan_status": fan,
                "duct_static": static.round(2),
                "duct_static_sp": sp,
                "oat": oat.round(2),
            }
        )
        if gap_prob:
            df = df[rng.random(rows_per_equip) >= gap_prob]
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def to_sqlite(
    df: pd.DataFrame, conn: sqlite3.Connection, table: str, index: list[str] | None = None
) -> None:
    """Write a DataFrame to a (replaced) table, with an optional index on ``index`` columns."""
    df.to_sql(table, conn, if_exists="replace", index=False)
    if index:
        conn.execute(f'CREATE INDEX "{table}_idx" ON "{table}" ({", ".join(index)})')
    conn.commit()


# ---------------------------------------------------------------- measuring
def sizes(full: list[int], quick_max: int = 20_000) -> list[int]:
    """Benchmark sizes: the full list normally, only the small ones under ``course.py check``."""
    return [n for n in full if n <= quick_max] if QUICK else full


def best_time(fn: Callable[[], object], repeat: int = 3) -> float:
    """Best wall-clock seconds over ``repeat`` runs (best-of-N hides noise from other programs)."""
    best = float("inf")
    for _ in range(repeat if not QUICK else 1):
        t = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t)
    return best


def peak_mib(fn: Callable[[], object]) -> float:
    """Peak Python-heap memory (MiB) while ``fn`` runs, via tracemalloc. numpy/pandas buffers are
    counted; memory SQLite allocates inside its C library is not."""
    tracemalloc.start()
    try:
        fn()
        return tracemalloc.get_traced_memory()[1] / 2**20
    finally:
        tracemalloc.stop()
