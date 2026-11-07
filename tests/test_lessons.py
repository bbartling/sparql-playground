"""The daily lessons: structure and the helpers. Running the lessons needs the Building 50
database, so that runs in CI's `lessons` job (`lessons/course.py check`)."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

LESSONS = Path(__file__).resolve().parents[1] / "lessons"


def load(name: str):
    sys.path.insert(0, str(LESSONS))
    spec = importlib.util.spec_from_file_location(name, LESSONS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_syllabus_links_exist():
    readme = (LESSONS / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\]\((unit[^)]+\.md)\)", readme)
    assert len(links) == 20
    for link in links:
        assert (LESSONS / link).is_file(), link


def test_every_lesson_has_its_sections_and_parity_checks():
    course = load("course")
    files = course.lesson_files()
    assert [int(p.stem[3:]) for p in files] == list(range(1, 21))
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert text.startswith(f"# Day {int(path.stem[3:])} "), path.name
        for section in ("**Goal:**", "## Read", "## Run"):
            assert section in text, (path.name, section)
        # each lesson ends with an exercise and either "why it matters" or a challenge
        assert "## Try it" in text or "challenge" in text, path.name
        assert "## Why it matters" in text or "challenge" in text, path.name
        # Python-driven: runnable blocks, SQL next to pandas, and a parity check
        assert course.blocks(path), path.name
        assert "lab.assert_parity(" in text, path.name
        assert "-- expect" not in text, path.name
        assert "lessons/sql" not in text, path.name


def test_block_extraction_skips_no_run_blocks(tmp_path):
    course = load("course")
    md = tmp_path / "day99.md"
    md.write_text(
        "# Day 99 — x\n\n```python\nx = 1\n```\n\n```python\n# no-run\nslow()\n```\n\n"
        "```sql\nSELECT 1;\n```\n\n```python\ny = x + 1\n```\n",
        encoding="utf-8",
    )
    assert course.blocks(md) == ["x = 1\n", "y = x + 1\n"]


def test_parity_ignores_row_order_and_bool_vs_int():
    lab = load("lab")
    a = pd.DataFrame({"k": ["b", "a"], "flag": [True, False], "v": [2.0, float("nan")]})
    b = pd.DataFrame({"v": [None, 2.0 + 1e-12], "k": ["a", "b"], "flag": [0, 1]})
    lab.assert_parity(a, b, keys=["k"])


def test_parity_catches_a_different_row():
    lab = load("lab")
    a = pd.DataFrame({"k": [1, 2], "v": [1.0, 2.0]})
    with pytest.raises(AssertionError, match="column 'v' differs"):
        lab.assert_parity(a, a.assign(v=[1.0, 2.5]), keys=["k"])
    with pytest.raises(AssertionError, match="row counts"):
        lab.assert_parity(a, a.head(1))
    with pytest.raises(AssertionError, match="columns differ"):
        lab.assert_parity(a, a.rename(columns={"v": "w"}))


def test_history_sql_converts_to_si():
    lab = load("lab")
    sql = lab.history_sql()
    assert "AS duct_static" in sql and str(lab.PA_PER_INH2O) in sql
    assert "(s.value - 32.0) * 5.0 / 9.0" in sql
    assert round(lab.f_to_c(212.0), 9) == 100.0
