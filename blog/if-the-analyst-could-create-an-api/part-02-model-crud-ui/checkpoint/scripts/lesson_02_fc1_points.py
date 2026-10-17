#!/usr/bin/env python3
"""Lesson 2 — SPARQL for the three FC1 points on one AHU.

Roles are matched via Haystack ``ofddRole`` tags under the AHU equipRef tree.

uv run python scripts/lesson_02_fc1_points.py
"""

from __future__ import annotations

from lesson_helpers import (  # noqa: E402
    banner,
    client,
    post_sparql,
    print_table,
    short,
    wait_until_ready,
)

# --- edit these (keep in sync across lesson_0*.py if you chain them) ---------
BASE_URL = "https://sparql-playground.onrender.com"
# BASE_URL = "http://127.0.0.1:8000"

EQUIPMENT = "AHU_1"
# ----------------------------------------------------------------------------

# Same text as scripts/sparql/02_fc1_points.rq — upload that file in Swagger via
# POST /api/sparql/upload (easiest). If you change EQUIPMENT, change bldg:AHU_1 too.
FC1_POINTS = """\
PREFIX bts: <https://example.org/openfdd/bldgts#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>

SELECT ?role ?point ?label ?timeseriesId WHERE {
  BIND(bldg:AHU_1 AS ?ahu)
  VALUES (?role) {
    ("duct-static-pressure")
    ("duct-static-pressure-sp")
    ("fan-cmd")
  }
  ?point bts:hasHaystackMarker "point" .
  ?point bts:hasHaystackTag ?roleTag .
  ?roleTag bts:tagName "ofddRole" ; bts:tagValue ?role .
  {
    ?point bts:hasHaystackTag ?direct .
    ?direct bts:tagName "equipRef" ; bts:tagValue ?ahu .
  } UNION {
    ?point bts:hasHaystackTag ?partRef .
    ?partRef bts:tagName "equipRef" ; bts:tagValue ?part .
    ?part bts:hasHaystackTag ?parentTag .
    ?parentTag bts:tagName "equipRef" ; bts:tagValue ?ahu .
  }
  OPTIONAL { ?point rdfs:label ?label }
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
        wait_until_ready(http)
        points = find_fc1_points(http)

    print("\nUse these point ids in lesson 3:")
    for role, pid in points.items():
        print(f"  {role:26s}  {pid}")

    print("\nNext →  uv run python scripts/lesson_03_fc1_dataframe.py")


if __name__ == "__main__":
    main()
