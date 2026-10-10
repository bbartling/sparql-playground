"""Small helpers shared by lesson_01 … lesson_04 (HTTP + pretty print)."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def short(value: str) -> str:
    """https://…#AHU_1 → AHU_1"""
    if not value:
        return ""
    return value.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url.rstrip("/"), timeout=120.0)


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


def banner(lesson: str, *, base_url: str, equipment: str) -> None:
    print(lesson)
    print(f"  server    {base_url}")
    print(f"  equipment {equipment}")
    print(f"  docs      {base_url.rstrip('/')}/docs")
