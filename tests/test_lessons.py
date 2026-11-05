"""The daily lessons: structure and the checker's helpers. Executing the SQL needs the
Building 50 database, so that runs in CI's `lessons` job (`lessons/course.py check`)."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

LESSONS = Path(__file__).resolve().parents[1] / "lessons"


def course():
    spec = importlib.util.spec_from_file_location("course", LESSONS / "course.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_syllabus_links_exist():
    readme = (LESSONS / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\]\((unit[^)]+\.md)\)", readme)
    assert len(links) == 15
    for link in links:
        assert (LESSONS / link).is_file(), link


def test_every_lesson_has_its_sections_and_sql():
    for path in sorted(LESSONS.glob("unit1-sqlite/day*.md")):
        text = path.read_text(encoding="utf-8")
        assert text.startswith(f"# Day {int(path.stem[3:])} "), path.name
        for section in ("**Goal:**", "## Read", "## Run"):
            assert section in text, (path.name, section)
        # each lesson ends with an exercise and either "why it matters" or a challenge
        assert "## Try it" in text or "challenge" in text, path.name
        assert "## Why it matters" in text or "challenge" in text, path.name
        assert "```sql" in text, path.name
        assert "lessons/sql" not in text, path.name


def test_statement_splitter():
    c = course()
    sql = "DROP VIEW IF EXISTS v;\nCREATE VIEW v AS SELECT 1;\n\nSELECT * FROM v;\n-- expect: 1\n"
    assert c.statements(sql) == [
        "DROP VIEW IF EXISTS v;",
        "CREATE VIEW v AS SELECT 1;",
        "SELECT * FROM v;",
    ]


def test_expected_values_compare_at_lesson_precision():
    c = course()
    assert c.same(98.8608, "98.8608")
    assert c.same(1.34712, "1.347")
    assert not c.same(1.34712, "1.36")
    assert c.same(35536, "35536")
    assert c.same("AHU_1", "AHU_1")
    assert not c.same(None, "0")
