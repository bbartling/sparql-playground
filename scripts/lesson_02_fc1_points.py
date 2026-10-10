#!/usr/bin/env python3
"""Lesson 2 — SPARQL for the three FC1 points on one AHU.

  duct-static-pressure     → Supply_Air_Static_Pressure_Sensor
  duct-static-pressure-sp  → Supply_Air_Static_Pressure_Setpoint
  fan-cmd                  → Fan_Speed_Command on Supply_Fan

  uv run python scripts/lesson_02_fc1_points.py
"""

from __future__ import annotations

from lesson_helpers import banner, client, post_sparql, print_table, short  # noqa: E402

# --- edit these (keep in sync across lesson_0*.py if you chain them) ---------
BASE_URL = "https://sparql-playground.onrender.com"
# BASE_URL = "http://127.0.0.1:8000"

EQUIPMENT = "AHU_1"
# ----------------------------------------------------------------------------

# Same text as scripts/sparql/02_fc1_points.rq — upload that file in Swagger via
# POST /api/sparql/upload (easiest). If you change EQUIPMENT, change bldg:AHU_1 too.
FC1_POINTS = """\
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>

SELECT ?role ?brickClass ?point ?timeseriesId WHERE {
  BIND(bldg:AHU_1 AS ?ahu)
  VALUES (?role ?brickClass ?needSupplyFan) {
    ("duct-static-pressure"    brick:Supply_Air_Static_Pressure_Sensor  false)
    ("duct-static-pressure-sp" brick:Supply_Air_Static_Pressure_Setpoint false)
    ("fan-cmd"                 brick:Fan_Speed_Command                   true)
  }
  ?point brick:isPointOf ?owner .
  ?owner (brick:isPartOf|^brick:hasPart)* ?ahu .
  ?point a/(rdfs:subClassOf|owl:equivalentClass|^owl:equivalentClass)* ?brickClass .
  OPTIONAL {
    ?owner a/(rdfs:subClassOf|owl:equivalentClass)* brick:Supply_Fan .
    BIND(true AS ?onSupplyFan)
  }
  FILTER(!?needSupplyFan || BOUND(?onSupplyFan))
  OPTIONAL {
    ?point ref:hasExternalReference ?ref .
    ?ref ref:hasTimeseriesId ?timeseriesId .
  }
}
ORDER BY ?role
"""

NEEDED = ("duct-static-pressure", "duct-static-pressure-sp", "fan-cmd")


def find_fc1_points(http, *, quiet: bool = False) -> dict[str, str]:
    """Return {open-fdd role → local point_id}."""
    rows = post_sparql(http, FC1_POINTS)
    if not quiet:
        print_table(f"FC1 points on {EQUIPMENT}", rows)

    by_role: dict[str, str] = {}
    for row in rows:
        role = row["role"]
        if role not in by_role:
            by_role[role] = short(row["point"])

    missing = [r for r in NEEDED if r not in by_role]
    if missing:
        raise SystemExit(f"SPARQL missed roles: {missing}")
    return by_role


def main() -> None:
    banner("Lesson 2 — find FC1 points with SPARQL", base_url=BASE_URL, equipment=EQUIPMENT)

    with client(BASE_URL) as http:
        points = find_fc1_points(http)

    print("\nUse these point ids in lesson 3:")
    for role, pid in points.items():
        print(f"  {role:26s}  {pid}")

    print("\nNext →  uv run python scripts/lesson_03_fc1_dataframe.py")


if __name__ == "__main__":
    main()
