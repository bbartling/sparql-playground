#!/usr/bin/env python3
"""Lesson 2 — find the three AHU points FC1 needs (via SPARQL).

Builds on lesson 1 helpers. Still no CLI args.

  uv run python scripts/lesson_02_fc1_points.py

FC1 needs:
  duct-static-pressure      → Supply_Air_Static_Pressure_Sensor
  duct-static-pressure-sp   → Supply_Air_Static_Pressure_Setpoint
  fan-cmd                   → Fan_Speed_Command on a Supply_Fan
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lesson_01_mech_summary import bindings_to_rows, client, post_sparql, print_rows  # noqa: E402
from lesson_config import BASE_URL, EQUIPMENT  # noqa: E402

# One query: bind equipment + three Brick classes → point ids (+ timeseries ids)
FC1_POINTS = f"""
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>

SELECT ?role ?brickClass ?point ?label ?timeseriesId WHERE {{
  BIND(bldg:{EQUIPMENT} AS ?ahu)

  VALUES (?role ?brickClass ?needSupplyFan) {{
    ("duct-static-pressure" brick:Supply_Air_Static_Pressure_Sensor false)
    ("duct-static-pressure-sp" brick:Supply_Air_Static_Pressure_Setpoint false)
    ("fan-cmd" brick:Fan_Speed_Command true)
  }}

  ?point brick:isPointOf ?owner .
  ?owner (brick:isPartOf|^brick:hasPart)* ?ahu .
  ?point a/(rdfs:subClassOf|owl:equivalentClass|^owl:equivalentClass)* ?brickClass .

  # Fan speed command must live on a Supply_Fan part of the AHU
  OPTIONAL {{
    ?owner a/(rdfs:subClassOf|owl:equivalentClass)* brick:Supply_Fan .
    BIND(true AS ?ownerIsSupplyFan)
  }}
  FILTER(!?needSupplyFan || BOUND(?ownerIsSupplyFan))

  OPTIONAL {{ ?point rdfs:label ?label }}
  OPTIONAL {{
    ?point ref:hasExternalReference ?ref .
    ?ref ref:hasTimeseriesId ?timeseriesId .
  }}
}}
ORDER BY ?role
"""


def point_id_from_iri(iri: str) -> str:
    """bldg:AHU_1_DA_P IRI → AHU_1_DA_P local name."""
    return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def find_fc1_points(http) -> dict[str, dict[str, str]]:
    """Return {role: {point_id, timeseries_id, brick_class, label}}."""
    rows = bindings_to_rows(post_sparql(http, FC1_POINTS))
    print_rows(f"FC1 role points on {EQUIPMENT}", rows)

    by_role: dict[str, dict[str, str]] = {}
    for row in rows:
        role = row["role"]
        # Prefer the first match per role
        if role in by_role:
            continue
        by_role[role] = {
            "point_id": point_id_from_iri(row["point"]),
            "timeseries_id": row.get("timeseriesId") or "",
            "brick_class": row.get("brickClass", "").rsplit("#", 1)[-1],
            "label": row.get("label") or "",
        }

    needed = ("duct-static-pressure", "duct-static-pressure-sp", "fan-cmd")
    missing = [r for r in needed if r not in by_role]
    if missing:
        raise SystemExit(f"SPARQL did not find roles: {missing}")
    return by_role


def main() -> None:
    print(f"BASE_URL = {BASE_URL}")
    print(f"EQUIPMENT = {EQUIPMENT}")

    with client() as http:
        points = find_fc1_points(http)

    print("\nResolved local point ids (use these in lesson 3):")
    for role, info in points.items():
        print(f"  {role:28s} → {info['point_id']}  ({info['brick_class']})")

    print("\nNext: uv run python scripts/lesson_03_fc1_dataframe.py")


if __name__ == "__main__":
    main()
