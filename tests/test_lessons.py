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
    assert len(links) == 45
    for link in links:
        assert (LESSONS / link).is_file(), link


def test_every_lesson_has_its_sections_and_scripts():
    files = sorted(LESSONS.glob("unit*/day*.md"), key=lambda p: int(p.stem[3:]))
    assert [int(p.stem[3:]) for p in files] == list(range(1, 46))
    for path in files:
        text = path.read_text(encoding="utf-8")
        day = int(path.stem[3:])
        assert text.startswith(f"# Day {day} "), path.name
        for section in ("**Goal:**", "## Read", "## Run"):
            assert section in text, (path.name, section)
        # each lesson ends with an exercise and either "why it matters" or a challenge
        assert "## Try it" in text or "challenge" in text, path.name
        assert "## Why it matters" in text or "challenge" in text, path.name
        # Weeks 6-9 (days 26-45): one RDF script, a buildings box and a burger mini challenge
        kinds = ("rdf",) if day >= 26 else ("pandas", "sql")
        if day >= 26:
            assert "## How this maps to buildings" in text, path.name
            assert "**Mini challenge (Burger Barn):**" in text, path.name
        for kind in kinds:
            script = path.with_name(f"day{day:02d}_{kind}.py")
            assert script.is_file(), script.name
            code = script.read_text(encoding="utf-8")
            assert script.name in text, (path.name, f"doesn't mention {script.name}")
            # scripts print for a human to compare; the parity test does the checking
            assert "RESULTS" in code and "print(" in code, script.name
            assert not re.search(r"^\s*assert", code, re.M), (script.name, "uses assert")


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


def test_si_conversions():
    lab = load("lab")
    assert round(lab.f_to_c(212.0), 9) == 100.0
    assert round(lab.inh2o_to_pa(1.0), 5) == 249.08891
