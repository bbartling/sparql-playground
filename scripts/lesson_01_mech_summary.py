#!/usr/bin/env python3
"""Lesson 1 — health check + mechanical inventory via SPARQL.

  uv run python scripts/lesson_01_mech_summary.py
"""

from __future__ import annotations

import json

from lesson_helpers import banner, client, post_sparql, print_table  # noqa: E402

# --- edit these -------------------------------------------------------------
BASE_URL = "https://sparql-playground.onrender.com"
# BASE_URL = "http://127.0.0.1:8000"

EQUIPMENT = "AHU_1"
# ----------------------------------------------------------------------------

MECH_SUMMARY = """\
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

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

LIST_AHUS = """\
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

# Tags live on the Brick *class*. Twin file: scripts/sparql/01_point_tags.rq
# (upload via Swagger POST /api/sparql/upload). Change bldg:AHU_1 if EQUIPMENT changes.
POINT_TAGS = """\
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT ?point ?cls ?tag WHERE {
  BIND(bldg:AHU_1 AS ?ahu)
  ?point brick:isPointOf ?owner .
  ?owner (brick:isPartOf|^brick:hasPart)* ?ahu .
  ?point a ?cls .
  FILTER(STRSTARTS(STR(?cls), STR(brick:)))
  ?cls brick:hasAssociatedTag ?tag .
}
ORDER BY ?point ?tag
LIMIT 30
"""


def main() -> None:
    banner("Lesson 1 — mechanical system summary", base_url=BASE_URL, equipment=EQUIPMENT)

    with client(BASE_URL) as http:
        # /health also wakes a sleeping Render free instance; retry until ready=true
        health = http.get("/health")
        health.raise_for_status()
        print("\nGET /health →", json.dumps(health.json()))
        if not health.json().get("ready"):
            print("Server still starting — wait a few seconds and re-run.")
            return

        print_table("Mechanical roll-up", post_sparql(http, MECH_SUMMARY))
        print_table("AHUs", post_sparql(http, LIST_AHUS))
        print_table(f"Brick tags on {EQUIPMENT} (sample)", post_sparql(http, POINT_TAGS))

    print("\nNext →  uv run python scripts/lesson_02_fc1_points.py")


if __name__ == "__main__":
    main()
