"""Course helper for the lessons in this folder.

    uv run python lessons/course.py doctor        # is the Building 50 database there?
    uv run python lessons/course.py run 14        # run lesson 14's Python, on a temp copy of the db
    uv run python lessons/course.py extract 14    # print lesson 14's Python as one script
    uv run python lessons/course.py check         # run every lesson; all parity checks must pass
    uv run python lessons/course.py check 11-15   # ... or a range of days
    uv run python lessons/course.py load-points   # lab_point in the real db (for DB Browser)
    uv run python lessons/course.py load-events   # lab_fdd_event in the real db
    uv run python lessons/course.py reset         # drop every lab_* table and view in the real db

Each lesson is a Markdown file whose ```python blocks, run top to bottom, are the lesson's code.
The SQL lives in those blocks as SQLite strings (stdlib ``sqlite3``), next to the same computation
in pandas, with ``lab.assert_parity`` checking they agree. ``run`` and ``check`` work on a
temporary copy of var/timeseries.sqlite, so a lesson never changes your database.
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
import tempfile
import time
import traceback
from pathlib import Path

LESSONS = Path(__file__).resolve().parent
sys.path.insert(0, str(LESSONS))

import lab  # noqa: E402

DB = lab.DB
PY_BLOCK = re.compile(r"^```python\n(.*?)^```", re.S | re.M)
# A block whose first line is this comment is shown but not run (e.g. a deliberately slow loop).
NO_RUN = "# no-run"


def connect(path: Path = DB) -> sqlite3.Connection:
    return lab.connect(path)


def load_points(conn: sqlite3.Connection) -> int:
    return lab.load_points(conn)


def load_events(conn: sqlite3.Connection) -> int:
    return lab.load_events(conn)


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


# ---------------------------------------------------------------- lessons as code
def lesson_files() -> list[Path]:
    return sorted(LESSONS.glob("unit*/day*.md"), key=lambda p: int(p.stem[3:]))


def lesson_file(day: int) -> Path:
    for path in lesson_files():
        if int(path.stem[3:]) == day:
            return path
    raise SystemExit(f"no lesson for day {day}")


def blocks(path: Path) -> list[str]:
    """The lesson's runnable ```python blocks, in order."""
    found = PY_BLOCK.findall(path.read_text(encoding="utf-8"))
    return [b for b in found if not b.lstrip().startswith(NO_RUN)]


def script(path: Path) -> str:
    rel = path.relative_to(LESSONS).as_posix()
    parts = [f"# {rel}, extracted by lessons/course.py\n"]
    for i, block in enumerate(blocks(path), 1):
        parts.append(f"\n# --- block {i}\n{block}")
    return "".join(parts)


def exec_lesson(path: Path) -> None:
    """Run every python block of one lesson in a fresh namespace, like one script."""
    ns: dict = {"__name__": "__lesson__"}
    rel = path.relative_to(LESSONS).as_posix()
    for i, block in enumerate(blocks(path), 1):
        code = compile(block, f"{rel} [block {i}]", "exec")
        exec(code, ns)  # noqa: S102 - running our own lesson code is the point
    conn = ns.get("conn")
    if isinstance(conn, sqlite3.Connection):
        conn.close()


class TempCopy:
    """A throwaway copy of the course database; lessons find it through $COURSE_DB."""

    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        copy = Path(self._tmp.name) / "course.sqlite"
        src = connect()
        dst = sqlite3.connect(copy)
        src.backup(dst)
        src.close()
        reset(dst)
        dst.close()
        self._old = os.environ.get("COURSE_DB")
        os.environ["COURSE_DB"] = str(copy)
        return copy

    def __exit__(self, *exc) -> None:
        if self._old is None:
            os.environ.pop("COURSE_DB", None)
        else:
            os.environ["COURSE_DB"] = self._old
        self._tmp.cleanup()


def days_arg(arg: str | None) -> list[Path]:
    files = lesson_files()
    if not arg:
        return files
    lo, _, hi = arg.partition("-")
    lo_i, hi_i = int(lo), int(hi or lo)
    return [p for p in files if lo_i <= int(p.stem[3:]) <= hi_i]


def run(day: int) -> int:
    with TempCopy():
        exec_lesson(lesson_file(day))
    return 0


def check(arg: str | None = None) -> int:
    """Run the chosen lessons in order on one temp copy; any exception or failed parity fails."""
    os.environ["COURSE_QUICK"] = "1"
    lab.QUICK = True
    failures = 0
    files = days_arg(arg)
    with TempCopy():
        for path in files:
            rel = path.relative_to(LESSONS).as_posix()
            t = time.perf_counter()
            print(f"=== {rel}", flush=True)
            try:
                exec_lesson(path)
            except Exception:  # noqa: BLE001 - report every lesson, then fail
                failures += 1
                print(f"FAIL {rel}\n{traceback.format_exc()}")
            else:
                print(f"ok   {rel} ({time.perf_counter() - t:.1f} s)")
    print(f"{len(files)} lessons, {failures} failures")
    return 1 if failures else 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "doctor"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    if cmd == "doctor":
        doctor()
    elif cmd == "run" and arg:
        return run(int(arg))
    elif cmd == "extract" and arg:
        sys.stdout.write(script(lesson_file(int(arg))))
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
        return check(arg)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
