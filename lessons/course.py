"""Course helper for the lessons in this folder.

    uv run python lessons/course.py doctor        # is the Building 50 database there?
    uv run python lessons/course.py load-points   # lab_point: one row per point
    uv run python lessons/course.py load-events   # lab_fdd_event: Open-FDD fault episodes
    uv run python lessons/course.py reset         # drop every lab_* table and view you made
    uv run python lessons/course.py check         # run every ```sql block in the lessons

The database is the API's own SQLite file, var/timeseries.sqlite (`uv run bldgts bootstrap`).
The app only uses the `samples` and `ingest_log` tables; everything the course adds is `lab_*`.
Close the database in DB Browser for SQLite (or Write Changes) before load-* or reset.
`check` runs on a temporary copy, so it never touches your work.
"""

from __future__ import annotations

import csv
import re
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "var" / "timeseries.sqlite"
LESSONS = Path(__file__).resolve().parent
POINT_CSVS = sorted((ROOT / "model" / "points").glob("*.csv"))
EVENT_CSVS = sorted((ROOT / "data").glob("*/*/fdd_events.csv"))


def connect(path: Path = DB) -> sqlite3.Connection:
    if not path.exists():
        sys.exit(f"{path} not found. Build it first:  uv run bldgts bootstrap")
    return sqlite3.connect(path)


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
    n = 0
    for path in POINT_CSVS:
        equipment_id = path.stem.split("__", 1)[1]
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                conn.execute(
                    "INSERT INTO lab_point VALUES (?,?,?,?,?,?,?,?,?)",
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
                    ),
                )
                n += 1
    conn.commit()
    return n


def load_events(conn: sqlite3.Connection) -> int:
    """lab_fdd_event: fault episodes Open-FDD found in this data (for comparing your SQL rules).
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
    n = 0
    for path in EVENT_CSVS:
        equipment_id = path.parent.name
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                conn.execute(
                    "INSERT INTO lab_fdd_event VALUES (?,?,?,?,?,?)",
                    (
                        equipment_id,
                        r["rule_name"],
                        int(datetime.fromisoformat(r["start_time_utc"]).timestamp()),
                        int(datetime.fromisoformat(r["end_time_utc"]).timestamp()),
                        float(r["duration_min"]),
                        int(r["sample_count"]),
                    ),
                )
                n += 1
    conn.commit()
    return n


def reset(conn: sqlite3.Connection) -> list[str]:
    dropped = []
    for kind, name in conn.execute(
        "SELECT type, name FROM sqlite_master WHERE name LIKE 'lab\\_%' ESCAPE '\\' "
        "AND type IN ('view', 'table', 'index') ORDER BY type = 'table'"
    ).fetchall():
        if kind == "index":
            continue  # dropped with its table
        conn.execute(f'DROP {kind.upper()} IF EXISTS "{name}"')
        dropped.append(name)
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'lab\\_%' ESCAPE '\\'"
    ).fetchall():
        conn.execute(f'DROP INDEX IF EXISTS "{name}"')
        dropped.append(name)
    conn.commit()
    return dropped


def doctor() -> None:
    conn = connect()
    n, series, lo, hi = conn.execute(
        "SELECT count(*), count(DISTINCT timeseries_id), datetime(min(ts), 'unixepoch'),"
        " datetime(max(ts), 'unixepoch') FROM samples"
    ).fetchone()
    print(f"{DB}\n  {n:,} samples, {series} series, {lo} .. {hi} UTC")
    labs = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'lab_%'")]
    print("  lab objects:", ", ".join(labs) or "none yet")


# ---------------------------------------------------------------- check
SQL_BLOCK = re.compile(r"```sql\n(.*?)```", re.S)
EXPECT = re.compile(r"--\s*expect:\s*(.+)$", re.M)


def statements(sql: str) -> list[str]:
    out, buf = [], ""
    for line in sql.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            out.append(buf.strip())
            buf = ""
    if buf.strip() and not all(
        ln.strip().startswith("--") or not ln.strip() for ln in buf.splitlines()
    ):
        out.append(buf.strip())
    return out


def same(got: object, want: str) -> bool:
    """Compare a result cell with a lesson's text; numbers at the precision the lesson shows."""
    if isinstance(got, (int, float)) and not isinstance(got, bool):
        try:
            w = float(want)
        except ValueError:
            return False
        places = len(want.split(".")[1]) if "." in want else 0
        return round(float(got), places) == round(w, places)
    return str(got) == want


def check() -> int:
    """Run every ```sql block of every lesson, in order, on a copy of the database.
    A block containing `-- expect: X` must return X in the first column of the first row
    (`-- expect: X | Y` checks the first two columns; `-- expect rows: N` checks the row count)."""
    src = connect()
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "course.sqlite"
        dst = sqlite3.connect(copy)
        src.backup(dst)
        src.close()
        reset(dst)
        load_points(dst)
        load_events(dst)
        files = sorted(LESSONS.glob("unit*/day*.md"))
        blocks = 0
        for path in files:
            for block in SQL_BLOCK.findall(path.read_text(encoding="utf-8")):
                blocks += 1
                rows = None
                try:
                    for stmt in statements(block):
                        cur = dst.execute(stmt)
                        rows = cur.fetchall() if cur.description else rows
                    dst.commit()
                except sqlite3.Error as e:
                    failures += 1
                    print(f"FAIL {path.relative_to(LESSONS)}: {e}\n{block}")
                    continue
                rel = path.relative_to(LESSONS)
                m = re.search(r"--\s*expect rows:\s*(\d+)", block)
                if m and (rows is None or len(rows) != int(m.group(1))):
                    failures += 1
                    print(f"FAIL {rel}: expected {m.group(1)} rows, got {rows and len(rows)}")
                for exp in EXPECT.findall(block):
                    want = [w.strip() for w in exp.split("|")]
                    got = list(rows[0][: len(want)]) if rows else []
                    if len(got) != len(want) or not all(map(same, got, want)):
                        failures += 1
                        print(f"FAIL {rel}: expected {want}, got {got}\n{block}")
        dst.close()
    print(f"{len(files)} lessons, {blocks} SQL blocks, {failures} failures")
    return 1 if failures else 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "doctor"
    if cmd == "doctor":
        doctor()
    elif cmd == "load-points":
        with connect() as conn:
            print(f"lab_point: {load_points(conn)} points")
    elif cmd == "load-events":
        with connect() as conn:
            print(f"lab_fdd_event: {load_events(conn)} fault episodes")
    elif cmd == "reset":
        with connect() as conn:
            print("dropped:", ", ".join(reset(conn)) or "nothing")
    elif cmd == "check":
        return check()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
