#!/usr/bin/env python3
"""Lesson 1 — health check + mechanical inventory via SPARQL.

  uv run python scripts/lesson_01_mech_summary.py
"""

from __future__ import annotations

import json

from lesson_config import (  # noqa: E402
    EQUIPMENT,
    PREFIXES,
    banner,
    client,
    post_sparql,
    print_table,
)

MECH_SUMMARY = (
    PREFIXES
    + """
SELECT ?kind (COUNT(DISTINCT ?equip) AS ?n) WHERE {
  VALUES ?kind {
    brick:Air_Handler_Unit brick:Variable_Air_Volume_Box
    brick:Fan_Powered_Terminal_Unit brick:Heat_Pump
    brick:Boiler brick:Chiller brick:Cooling_Tower
    brick:Pump brick:Fan brick:HVAC_Zone
  }
  ?equip a/(rdfs:subClassOf|owl:equivalentClass)* ?kind .
  FILTER(STRSTARTS(STR(?equip), STR(bldg:)))
}
GROUP BY ?kind
ORDER BY DESC(?n) ?kind
"""
)

LIST_AHUS = (
    PREFIXES
    + """
SELECT ?ahu ?label WHERE {
  ?ahu a/(rdfs:subClassOf|owl:equivalentClass)* brick:Air_Handler_Unit .
  FILTER(STRSTARTS(STR(?ahu), STR(bldg:)))
  OPTIONAL { ?ahu rdfs:label ?label }
}
ORDER BY ?ahu
"""
)

# Tags live on the Brick *class* in the ontology, not as free text on each point
POINT_TAGS = (
    PREFIXES
    + f"""
SELECT ?point ?cls ?tag WHERE {{
  BIND(bldg:{EQUIPMENT} AS ?ahu)
  ?point brick:isPointOf ?owner .
  ?owner (brick:isPartOf|^brick:hasPart)* ?ahu .
  ?point a ?cls .
  FILTER(STRSTARTS(STR(?cls), STR(brick:)))
  ?cls brick:hasAssociatedTag ?tag .
}}
ORDER BY ?point ?tag
LIMIT 30
"""
)


def main() -> None:
    banner("Lesson 1 — mechanical system summary")

    with client() as http:
        health = http.get("/health")
        health.raise_for_status()
        print("\nGET /health →", json.dumps(health.json()))

        print_table("Mechanical roll-up", post_sparql(http, MECH_SUMMARY))
        print_table("AHUs", post_sparql(http, LIST_AHUS))
        print_table(f"Brick tags on {EQUIPMENT} (sample)", post_sparql(http, POINT_TAGS))

    print("\nNext →  uv run python scripts/lesson_02_fc1_points.py")


if __name__ == "__main__":
    main()
