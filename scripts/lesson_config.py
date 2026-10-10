"""Shared knobs + tiny helpers for lesson_01 … lesson_04.

Edit BASE_URL (Render or local). Dataset window ≈ 2026-03-16 → 2026-07-17 UTC.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

# Make `import lesson_*` work when run as: uv run python scripts/lesson_0N_….py
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# --- edit these -------------------------------------------------------------
BASE_URL = "https://sparql-playground.onrender.com"
# BASE_URL = "http://127.0.0.1:8000"

EQUIPMENT = "AHU_1"

# One month inside the loaded CSV range
START_ISO = "2026-06-01T00:00:00+00:00"
END_ISO = "2026-07-01T00:00:00+00:00"
# ----------------------------------------------------------------------------

POLL_SECONDS = 300  # 5-minute samples in this dataset

PREFIXES = """\
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>
"""


def short(value: str) -> str:
    """https://…#AHU_1 → AHU_1"""
    if not value:
        return ""
    return value.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL.rstrip("/"), timeout=120.0)


def post_sparql(http: httpx.Client, query: str) -> list[dict[str, str]]:
    """POST /api/sparql → list of {var: value} rows (plain strings)."""
    r = http.post("/api/sparql", json={"query": query})
    r.raise_for_status()
    body = r.json().get("results") or {}
    if "boolean" in body:
        return [{"ask": str(body["boolean"])}]
    bindings = (body.get("results") or {}).get("bindings") or []
    rows = []
    for b in bindings:
        rows.append({k: (v.get("value") if isinstance(v, dict) else v) for k, v in b.items()})
    return rows


def print_table(title: str, rows: list[dict[str, str]], *, limit: int = 20) -> None:
    """Compact aligned table; shortens IRIs for readability."""
    print(f"\n{title}  ({len(rows)} rows)")
    if not rows:
        print("  (empty)")
        return
    keys = list(rows[0].keys())
    shown = rows[:limit]
    cells = [[short(str(row.get(k, ""))) for k in keys] for row in shown]
    widths = [max(len(k), *(len(r[i]) for r in cells)) for i, k in enumerate(keys)]
    header = "  ".join(k.ljust(widths[i]) for i, k in enumerate(keys))
    print("  " + header)
    print("  " + "  ".join("-" * w for w in widths))
    for row in cells:
        print("  " + "  ".join(row[i].ljust(widths[i]) for i in range(len(keys))))
    if len(rows) > limit:
        print(f"  … +{len(rows) - limit} more")


def banner(lesson: str) -> None:
    print(f"{lesson}")
    print(f"  server    {BASE_URL}")
    print(f"  equipment {EQUIPMENT}")
    print(f"  docs      {BASE_URL.rstrip('/')}/docs")
