"""Check lesson structure and local links, not execution or student correctness."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
DAILY = {
    "Goal",
    "Before you start",
    "Concept",
    "Tiny example",
    "SQL challenge",
    "Experiment",
    "Acceptance checks",
    "Stretch and reflection",
}
WEEKLY = {"Project brief", "Acceptance criteria", "Deliverables"}


def validate() -> list[str]:
    errors = []
    days = sorted(HERE.glob("day[0-9][0-9].md"))
    if [p.name for p in days] != [f"day{i:02}.md" for i in range(1, 85)]:
        errors.append("expected exactly days 01 through 84")
    for day in range(1, 85):
        path = HERE / f"day{day:02}.md"
        if not path.exists():
            continue
        text = path.read_text()
        headings = set(re.findall(r"^## (.+)$", text, re.M))
        required = WEEKLY if day % 7 == 0 else DAILY
        if missing := required - headings:
            errors.append(f"{path.name}: missing sections {sorted(missing)}")
        if day % 7 == 0 and not headings.intersection({"Review questions", "Self-review"}):
            errors.append(f"{path.name}: missing independent review")
        if day % 7 == 0 and re.search(r"^```(?:sql|python|bash)", text, re.M):
            errors.append(f"{path.name}: weekly challenge contains a worked code block")
        if len(re.findall(r"^```", text, re.M)) % 2:
            errors.append(f"{path.name}: unbalanced code fence")
        if not text.startswith(f"# Day {day:02} —"):
            errors.append(f"{path.name}: incorrect title number")
        for neighbor in (day - 1, day + 1):
            if 1 <= neighbor <= 84 and f"(day{neighbor:02}.md)" not in text:
                errors.append(f"{path.name}: missing neighboring-day navigation")
    for path in HERE.rglob("*.md"):
        # Ignore links written inside fenced examples, and check repository-relative targets.
        text = re.sub(r"```[\s\S]*?```", "", path.read_text())
        for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", text):
            parsed = urlsplit(target.strip("<>"))
            if parsed.scheme or not parsed.path:
                continue
            destination = path.parent / unquote(parsed.path)
            if not destination.exists():
                errors.append(f"{path.name}: missing link target {target}")
    fixture = json.loads((HERE / "fixture.json").read_text())
    if len(fixture["points"]) != 42 or len({p["point_id"] for p in fixture["points"]}) != 42:
        errors.append("expected 42 unique, frozen point identities")
    inventory = json.loads((HERE / "openfdd_inventory.json").read_text())
    if len(inventory["rules"]) != 77 or len(inventory["analytics_queries"]) != 18:
        errors.append("pinned source inventory must contain 77 rules and 18 analytics")
    return errors


if __name__ == "__main__":
    problems = validate()
    for problem in problems:
        print(problem)
    if problems:
        raise SystemExit(1)
    print("PASS: 84 daily pages, 12 independent challenges, local links and pinned inventory")
