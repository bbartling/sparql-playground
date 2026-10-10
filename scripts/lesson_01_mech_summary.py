#!/usr/bin/env python3
"""Lesson 1 — talk to the server and summarize the mechanical system.

No CLI args. Edit BASE_URL in lesson_config.py, then:

  uv run python scripts/lesson_01_mech_summary.py

What you learn:
  - GET /health
  - POST /api/sparql with a simple inventory query (same idea as the old UI buttons)
  - How SPARQL JSON bindings become plain Python rows
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

# Allow `from lesson_config import …` when run as a script path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lesson_config import BASE_URL, EQUIPMENT  # noqa: E402

MECH_SUMMARY = """
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT ?kind (COUNT(DISTINCT ?equip) AS ?n) WHERE {
  VALUES ?kind {
    brick:Air_Handler_Unit
    brick:Variable_Air_Volume_Box
    brick:Fan_Powered_Terminal_Unit
    brick:Heat_Pump
    brick:Boiler
    brick:Chiller
    brick:Cooling_Tower
    brick:Pump
    brick:Fan
    brick:HVAC_Zone
  }
  ?equip a/(rdfs:subClassOf|owl:equivalentClass)* ?kind .
  FILTER(STRSTARTS(STR(?equip), STR(bldg:)))
}
GROUP BY ?kind
ORDER BY DESC(?n) ?kind
"""

LIST_AHUS = """
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT ?ahu ?label WHERE {
  ?ahu a/(rdfs:subClassOf|owl:equivalentClass)* brick:Air_Handler_Unit .
  FILTER(STRSTARTS(STR(?ahu), STR(bldg:)))
  OPTIONAL { ?ahu rdfs:label ?label }
}
ORDER BY ?ahu
"""

# Brick tags live on the *class* (Brick ontology), not as free text on each point
POINT_TAGS = f"""
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT ?point ?label ?cls ?tag WHERE {{
  BIND(bldg:{EQUIPMENT} AS ?ahu)
  ?point brick:isPointOf ?owner .
  ?owner (brick:isPartOf|^brick:hasPart)* ?ahu .
  ?point a ?cls .
  FILTER(STRSTARTS(STR(?cls), STR(brick:)))
  ?cls brick:hasAssociatedTag ?tag .
  OPTIONAL {{ ?point rdfs:label ?label }}
}}
ORDER BY ?point ?tag
LIMIT 40
"""


def client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL.rstrip("/"), timeout=120.0)


def post_sparql(http: httpx.Client, query: str) -> dict:
    """POST /api/sparql and return the full JSON body."""
    r = http.post("/api/sparql", json={"query": query})
    r.raise_for_status()
    return r.json()


def bindings_to_rows(payload: dict) -> list[dict[str, str]]:
    """Turn SPARQL JSON results into a list of plain dicts (var → value)."""
    body = payload.get("results") or {}
    if "boolean" in body:
        return [{"ask": str(body["boolean"])}]
    bindings = (body.get("results") or {}).get("bindings") or []
    rows = []
    for b in bindings:
        rows.append({k: (v.get("value") if isinstance(v, dict) else v) for k, v in b.items()})
    return rows


def print_rows(title: str, rows: list[dict[str, str]], *, limit: int = 25) -> None:
    print(f"\n=== {title} ({len(rows)} rows) ===")
    for row in rows[:limit]:
        print(" ", row)
    if len(rows) > limit:
        print(f"  … {len(rows) - limit} more")


def main() -> None:
    print(f"BASE_URL = {BASE_URL}")
    print(f"EQUIPMENT (used later) = {EQUIPMENT}")
    print("Interactive API docs:", BASE_URL.rstrip("/") + "/docs")

    with client() as http:
        health = http.get("/health")
        health.raise_for_status()
        print("\nGET /health →", json.dumps(health.json()))

        summary = bindings_to_rows(post_sparql(http, MECH_SUMMARY))
        print_rows("Mechanical system roll-up", summary)

        ahus = bindings_to_rows(post_sparql(http, LIST_AHUS))
        print_rows("AHUs", ahus)

        tags = bindings_to_rows(post_sparql(http, POINT_TAGS))
        print_rows(f"Sample Brick tags on {EQUIPMENT} points", tags)

    print("\nNext: uv run python scripts/lesson_02_fc1_points.py")


if __name__ == "__main__":
    main()
