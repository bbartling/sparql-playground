"""Every lesson day has a pandas script and a SQL script; they must compute the same answers.

The scripts only print (the student compares by eye). Each one also ends with a small RESULTS dict;
this test runs both scripts of a day from the repo root (the scripts use paths like
"data/BUILDING_50/AHU_1/history_wide.csv") and checks every key they share: same rows, same
values, row order and bool-vs-0/1 ignored, NaN == NULL. That's the pattern Open-FDD's parity tests
use (pandas oracle == SQL rule pack).

Run:  uv run pytest -q -m lessons        (CI's `lessons` job; a few minutes)

Weeks 1-4 need only the CSVs in data/ (var/lessons.sqlite is built here if it's missing). Week 5
(data modeling) also needs the API's database and RDF model
(`uv run bldgts model build && uv run bldgts bootstrap`); those days are skipped without them.
"""

from __future__ import annotations

import contextlib
import io
import math
import os
import runpy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "lessons"
sys.path.insert(0, str(LESSONS))

import setup_db  # noqa: E402

pytestmark = pytest.mark.lessons
NEEDS_API_DB = ("timeseries.sqlite", "TestClient")


def days() -> list[int]:
    return sorted(int(p.stem[3:5]) for p in LESSONS.glob("unit*/day*_sql.py"))


@pytest.fixture(scope="session")
def lessons_db():
    if not setup_db.db_path().exists():
        with contextlib.redirect_stdout(io.StringIO()):
            setup_db.build()
    old_cwd = os.getcwd()
    os.chdir(ROOT)  # the scripts use paths relative to the repo root
    yield
    os.chdir(old_cwd)


def run_script(path: Path) -> dict:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ns = runpy.run_path(str(path), run_name="__main__")
    assert out.getvalue().strip(), f"{path.name} printed nothing"
    results = ns.get("RESULTS")
    assert isinstance(results, dict) and results, f"{path.name} has no RESULTS dict"
    return results


# ---------------------------------------------------------------- comparing results
def _frame(x) -> pd.DataFrame:
    if isinstance(x, pd.Series):
        x = x.to_frame()
    # a named index (e.g. after groupby) is data; an unnamed one (after a filter or sort) isn't
    unnamed = all(name is None for name in x.index.names)
    out = x.reset_index(drop=unnamed).copy()
    for col in out.columns:
        if out[col].dtype == bool:
            out[col] = out[col].astype(int)
    return out


def assert_parity(pandas_df, sql_df, *, label: str = "", atol: float = 1e-9) -> None:
    """Same columns, same rows (any order), same values; numbers within atol; NaN == NULL."""
    a, b = _frame(pandas_df), _frame(sql_df)
    assert set(a.columns) == set(b.columns), (
        f"{label} columns differ: {list(a.columns)} vs {list(b.columns)}"
    )
    b = b[list(a.columns)]
    assert len(a) == len(b), f"{label} row counts differ: pandas {len(a)} vs SQL {len(b)}"
    keys = list(a.columns)
    a = a.sort_values(keys, kind="mergesort").reset_index(drop=True)
    b = b.sort_values(keys, kind="mergesort").reset_index(drop=True)
    for col in a.columns:
        x, y = a[col], b[col]
        xn, yn = pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")
        numeric = xn.notna().sum() == x.notna().sum() and yn.notna().sum() == y.notna().sum()
        if numeric:
            ok = np.isclose(
                xn.astype(float), yn.astype(float), atol=atol, rtol=1e-9, equal_nan=True
            )
        else:
            both_null = (x.isna() & y.isna()).to_numpy()
            ok = both_null | (x.astype(str) == y.astype(str)).to_numpy()
        if not ok.all():
            i = int(np.argmin(ok))
            raise AssertionError(
                f"{label} column {col!r} differs at row {i}: "
                f"pandas {x.iloc[i]!r} vs SQL {y.iloc[i]!r}"
            )


def same(a, b, label: str) -> None:
    if isinstance(a, pd.DataFrame | pd.Series) or isinstance(b, pd.DataFrame | pd.Series):
        assert_parity(a, b, label=label)
    elif isinstance(a, int | float | np.number) and isinstance(b, int | float | np.number):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), (label, a, b)
    else:
        assert str(a) == str(b), (label, a, b)


def test_parity_helper_ignores_row_order_and_bool_vs_int():
    a = pd.DataFrame({"k": ["b", "a"], "flag": [True, False], "v": [2.0, float("nan")]})
    b = pd.DataFrame({"v": [None, 2.0 + 1e-12], "k": ["a", "b"], "flag": [0, 1]})
    assert_parity(a, b)
    with pytest.raises(AssertionError, match="column 'v' differs"):
        assert_parity(a, a.assign(v=[1.0, 2.5]))


@pytest.mark.parametrize("day", days())
def test_pandas_and_sql_agree(day: int, lessons_db):
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
