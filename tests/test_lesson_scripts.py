"""Every lesson day has a pandas script and a SQL script; they must compute the same answers.

The scripts only print (the student compares by eye). They also keep their answers in a module-level
RESULTS dict; this test runs both and checks every key they share with lessons/lab.py's
assert_parity: same rows, same values, row order and bool-vs-0/1 ignored, NaN == NULL. That's the
pattern Open-FDD's parity tests use (pandas oracle == SQL rule pack).

Run:  uv run pytest -q -m lessons        (CI's `lessons` job; a few minutes)

Weeks 1-4 need only the CSVs in data/. Week 5 (data modeling) also needs the API's database and RDF
model (`uv run bldgts model build && uv run bldgts bootstrap`); those days are skipped without them.
"""

from __future__ import annotations

import contextlib
import io
import math
import os
import runpy
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "lessons"
sys.path.insert(0, str(LESSONS))

import lab  # noqa: E402
import setup_db  # noqa: E402

pytestmark = pytest.mark.lessons
NEEDS_API_DB = ("timeseries.sqlite", "lab.Api", "lab.API_DB")


def days() -> list[int]:
    return sorted(int(p.stem[3:5]) for p in LESSONS.glob("unit*/day*_sql.py"))


@pytest.fixture(scope="session")
def lessons_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("lessons") / "lessons.sqlite"
    with contextlib.redirect_stdout(io.StringIO()):
        setup_db.build(path)
    old = os.environ.get("LESSONS_DB")
    os.environ["LESSONS_DB"] = str(path)
    os.environ["COURSE_QUICK"] = "1"  # benchmarks use their small sizes
    lab.QUICK = True
    yield path
    if old is None:
        os.environ.pop("LESSONS_DB", None)
    else:
        os.environ["LESSONS_DB"] = old


def run_script(path: Path) -> dict:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ns = runpy.run_path(str(path), run_name="__main__")
    assert out.getvalue().strip(), f"{path.name} printed nothing"
    results = ns.get("RESULTS")
    assert isinstance(results, dict) and results, f"{path.name} has no RESULTS dict"
    return results


def same(a, b, label: str) -> None:
    if isinstance(a, pd.DataFrame | pd.Series) or isinstance(b, pd.DataFrame | pd.Series):
        lab.assert_parity(a, b, label=label)
    elif isinstance(a, float | int) and isinstance(b, float | int):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), (label, a, b)
    else:
        assert str(a) == str(b), (label, a, b)


@pytest.mark.parametrize("day", days())
def test_pandas_and_sql_agree(day: int, lessons_db: Path):
    pd_path = next(LESSONS.glob(f"unit*/day{day:02d}_pandas.py"))
    sql_path = next(LESSONS.glob(f"unit*/day{day:02d}_sql.py"))
    text = pd_path.read_text(encoding="utf-8") + sql_path.read_text(encoding="utf-8")
    if any(s in text for s in NEEDS_API_DB) and not (ROOT / "var" / "timeseries.sqlite").exists():
        pytest.skip("needs the API database: uv run bldgts model build && uv run bldgts bootstrap")
    a, b = run_script(pd_path), run_script(sql_path)
    shared = sorted(set(a) & set(b))
    assert shared, f"day {day}: the two scripts share no RESULTS keys ({sorted(a)} vs {sorted(b)})"
    for key in shared:
        same(a[key], b[key], f"day {day} {key}")
