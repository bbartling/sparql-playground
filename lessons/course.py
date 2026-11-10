"""Course helper for the lessons in this folder.

    uv run python lessons/course.py setup      # load the CSVs into var/lessons.sqlite
    uv run python lessons/course.py doctor     # are the CSVs and the database there?
    uv run python lessons/course.py run 14     # run Day 14's pandas script, then its SQL script
    uv run python lessons/course.py check      # pytest: pandas and SQL results agree, every day

Each day is a Markdown lesson (dayNN.md) plus two scripts next to it:

    dayNN_pandas.py   reads the CSV export into a DataFrame and computes the answer with pandas
    dayNN_sql.py      runs the same computation as SQLite queries on the same rows

Weeks 6-9 (days 26-45, unit4-rdf-by-hand/) teach RDF and ontologies on a made-up burger restaurant.
Those days have ONE script each, dayNN_rdf.py, reading small hand-written Turtle files next to it;
`run 26` runs it the same way.

Each script prints its answers at the end so you can compare them by eye. Each also keeps them in a
RESULTS dict, which tests/test_lesson_scripts.py uses to check the two agree (or, for the RDF days,
that the answers are the expected ones).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

LESSONS = Path(__file__).resolve().parent
ROOT = LESSONS.parent
sys.path.insert(0, str(LESSONS))

import setup_db  # noqa: E402


def lesson_files() -> list[Path]:
    return sorted(LESSONS.glob("unit*/day*.md"), key=lambda p: int(p.stem[3:]))


def scripts(day: int) -> list[Path]:
    """The day's scripts in run order: pandas first, then SQL (then any others)."""
    found = sorted(LESSONS.glob(f"unit*/day{day:02d}_*.py"))
    order = {"pandas": 0, "sql": 1}
    return sorted(found, key=lambda p: (order.get(p.stem.split("_", 1)[1], 2), p.name))


def doctor() -> None:
    for equip in ("AHU_1", "AHU_2"):
        csv = setup_db.DATA / equip / "history_wide.csv"
        print(f"{csv.relative_to(ROOT)}: {'ok' if csv.exists() else 'MISSING'}")
    db = setup_db.db_path()
    if not db.exists():
        print(f"{db}: missing. Run:  uv run python lessons/course.py setup")
        return
    import sqlite3  # noqa: PLC0415

    with sqlite3.connect(db) as conn:
        for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
            n = conn.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            print(f"{db.name}: {name} {n:,} rows")
    ts = ROOT / "var" / "timeseries.sqlite"
    print(f"{ts.relative_to(ROOT)} (Week 5, the API's db): {'ok' if ts.exists() else 'not built'}")


def run(day: int) -> int:
    paths = scripts(day)
    if not paths:
        raise SystemExit(f"no scripts for day {day}")
    needs_db = any(not path.stem.endswith("_rdf") for path in paths)  # RDF days read .ttl only
    if needs_db and not setup_db.db_path().exists():
        setup_db.build()
    rc = 0
    for path in paths:
        print(f"\n===== {path.relative_to(LESSONS).as_posix()} =====", flush=True)
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}  # Windows consoles: print ° and ₂
        rc |= subprocess.run([sys.executable, str(path)], cwd=ROOT, env=env, check=False).returncode
    return rc


def check() -> int:
    cmd = [sys.executable, "-m", "pytest", "-q", "-m", "lessons", "tests/test_lesson_scripts.py"]
    return subprocess.run(cmd, cwd=ROOT, check=False, env={**os.environ}).returncode


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "doctor"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    if cmd == "setup":
        print(f"wrote {setup_db.build()}")
    elif cmd == "doctor":
        doctor()
    elif cmd == "run" and arg:
        return run(int(arg))
    elif cmd == "check":
        return check()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
