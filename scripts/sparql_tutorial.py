#!/usr/bin/env python3
"""Hit a brickts SPARQL API (local or Render) and exercise tutorial queries.

Examples:
  uv run python scripts/sparql_tutorial.py
  uv run python scripts/sparql_tutorial.py --base-url https://sparql-playground.onrender.com
  uv run python scripts/sparql_tutorial.py --equipment AHU_2 --rule FC1
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx


def _print(title: str, payload: object, *, limit: int = 2400) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, indent=2)
    print(f"\n=== {title} ===")
    print(text if len(text) <= limit else text[:limit] + "\n… truncated …")


def run_catalog(client: httpx.Client) -> None:
    listed = client.get("/api/sparql/examples")
    listed.raise_for_status()
    examples = listed.json()["examples"]
    print(f"Catalog presets: {len(examples)}")
    for ex in examples:
        r = client.post("/api/sparql", json={"query": ex["query"]})
        r.raise_for_status()
        body = r.json()
        meta = body.get("meta", {})
        results = body.get("results", {})
        if "boolean" in results:
            summary = f"ASK={results['boolean']}"
        else:
            summary = f"rows={meta.get('row_count')} elapsed_ms={meta.get('elapsed_ms')}"
        print(f"  ✓ {ex['id']}: {summary}")


def run_fault_lessons(client: httpx.Client, equipment: str, rule: str | None) -> None:
    faults = client.get(f"/api/equipment/{equipment}/faults", params={"include_generic": False})
    faults.raise_for_status()
    applicable = [f for f in faults.json() if f["applicable"]]
    print(f"\nApplicable role-based faults on {equipment}: {len(applicable)}")
    for f in applicable[:12]:
        print(f"  {f['rule_id']}: {f['title']}")

    targets = [rule] if rule else [f["rule_id"] for f in applicable[:3]]
    for rule_id in targets:
        lesson = client.get(f"/api/equipment/{equipment}/faults/{rule_id}/lesson")
        lesson.raise_for_status()
        data = lesson.json()
        _print(
            f"lesson {rule_id}",
            {
                "title": data.get("title"),
                "roles": [
                    {
                        "role": x.get("role"),
                        "point_id": (x.get("binding") or {}).get("point_id"),
                        "brick_class": (x.get("binding") or {}).get("brick_class"),
                    }
                    for x in data.get("lessons", [])
                ],
            },
        )
        for item in data.get("lessons", []):
            q = item.get("query")
            if not q:
                print(f"  skip {item.get('role')}: {item.get('error')}")
                continue
            r = client.post("/api/sparql", json={"query": q})
            r.raise_for_status()
            meta = r.json().get("meta", {})
            print(
                f"  ✓ SPARQL role {item['role']} → "
                f"rows={meta.get('row_count')} ms={meta.get('elapsed_ms')}"
            )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--base-url",
        default="https://sparql-playground.onrender.com",
        help="brickts base URL (default: Render deploy)",
    )
    p.add_argument("--equipment", default="AHU_1")
    p.add_argument("--rule", default=None, help="Optional single Open-FDD rule id for lessons")
    p.add_argument("--skip-catalog", action="store_true")
    args = p.parse_args()

    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=120.0) as client:
        health = client.get("/health")
        health.raise_for_status()
        _print("GET /health", health.json())

        root = client.get("/", follow_redirects=False)
        print(f"\nGET / → {root.status_code} Location={root.headers.get('location')}")

        docs = client.get("/docs")
        docs.raise_for_status()
        print(f"GET /docs → {docs.status_code} ({len(docs.text)} bytes)")

        ttl = client.get("/api/model/ttl")
        ttl.raise_for_status()
        ctype = ttl.headers.get("content-type")
        print(f"GET /api/model/ttl → {ttl.status_code} ({len(ttl.text)} chars, {ctype})")

        if not args.skip_catalog:
            run_catalog(client)
        run_fault_lessons(client, args.equipment, args.rule)

    print("\nDone. Prefer the numbered lessons:")
    print("  uv run python scripts/lesson_01_mech_summary.py")
    print("Or power tool: uv run python scripts/analyst_client.py --equipment AHU_1 --rule FC1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
