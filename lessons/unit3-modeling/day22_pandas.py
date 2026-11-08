"""Day 22, pandas: find FC1's inputs by Haystack tags, with SPARQL on the RDF model (rdflib, no
server).

    uv run python lessons/unit3-modeling/day22_pandas.py

model/building_50.ttl holds every point as Haystack tags written as RDF (markers, ofddRole,
equipRef...). rdflib loads it into memory and runs SPARQL; the result rows become a DataFrame.
Nothing here names a column or an id: the query asks for roles, the model answers. Compare the
printout with day22_sql.py: the same (equipment, role, point) rows come back."""

import unicodedata
from pathlib import Path

import pandas as pd
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "model" / "building_50.ttl"

PREFIXES = """
PREFIX bts:  <https://example.org/openfdd/bldgts#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX ref:  <https://brickschema.org/schema/Brick/ref#>
"""


def local(iri) -> str:
    """The part of an IRI after '#': bldg:AHU_1 -> 'AHU_1'."""
    return str(iri).rsplit("#", 1)[-1]


def plain(text) -> str:
    """NFKD turns the unit's subscript 2 into a plain 2, so any console can print the tag."""
    return unicodedata.normalize("NFKD", local(text))


# 1. Load the model: a graph of (subject, predicate, object) statements, held in memory.
g = Graph()
g.parse(MODEL, format="turtle")

# 2. What does one point look like? Its markers, then its tags (name, value) as RDF.
MARKERS_SPARQL = PREFIXES + "SELECT ?marker WHERE { bldg:AHU_1_DA_P bts:hasHaystackMarker ?marker }"
TAGS_SPARQL = (
    PREFIXES
    + """
SELECT ?tag_name ?tag_value WHERE {
  bldg:AHU_1_DA_P bts:hasHaystackTag ?t .
  ?t bts:tagName ?tag_name ; bts:tagValue ?tag_value .
}"""
)
markers = sorted(str(r.marker) for r in g.query(MARKERS_SPARQL))
one_point = pd.DataFrame(
    [(str(r.tag_name), plain(r.tag_value)) for r in g.query(TAGS_SPARQL)],
    columns=["tag_name", "tag_value"],
).sort_values("tag_name", ignore_index=True)

# 3. FC1's inputs per AHU, by tags. Start from the points that have a timeseries reference (118 of
#    them): rdflib evaluates patterns roughly in order, so a selective first pattern keeps every
#    join after it small. Starting from "every ofddRole tag" is much slower.
FC1_ROLES = ("fan-status", "duct-static-pressure", "duct-static-pressure-sp")
FC1_SPARQL = (
    PREFIXES
    + """
SELECT ?equip ?role ?point ?timeseries_id WHERE {
  ?point ref:hasExternalReference ?ref .
  ?ref ref:hasTimeseriesId ?timeseries_id .
  ?point bts:hasHaystackTag ?role_tag .
  ?role_tag bts:tagName "ofddRole" ; bts:tagValue ?role .
  FILTER(?role IN ("fan-status", "duct-static-pressure", "duct-static-pressure-sp"))
  ?point bts:hasHaystackTag ?equip_tag .
  ?equip_tag bts:tagName "equipRef" ; bts:tagValue ?equip .
}"""
)
fc1_inputs = pd.DataFrame(
    [
        (local(r.equip), str(r.role), local(r.point), str(r.timeseries_id))
        for r in g.query(FC1_SPARQL)
    ],
    columns=["equipment_id", "role", "point_id", "timeseries_id"],
).sort_values(["equipment_id", "role"], ignore_index=True)

# 4. How many points per AHU carry a fault-rule role at all?
ROLE_COUNT_SPARQL = (
    PREFIXES
    + """
SELECT ?equip (COUNT(?role) AS ?roles) WHERE {
  ?point ref:hasExternalReference ?ref .
  ?ref ref:hasTimeseriesId ?timeseries_id .
  ?point bts:hasHaystackTag ?role_tag .
  ?role_tag bts:tagName "ofddRole" ; bts:tagValue ?role .
  ?point bts:hasHaystackTag ?equip_tag .
  ?equip_tag bts:tagName "equipRef" ; bts:tagValue ?equip .
}
GROUP BY ?equip"""
)
roles_per_ahu = pd.DataFrame(
    [(local(r.equip), int(r.roles)) for r in g.query(ROLE_COUNT_SPARQL)],
    columns=["equipment_id", "roles"],
).sort_values("equipment_id", ignore_index=True)

RESULTS = {"fc1_inputs": fc1_inputs, "roles_per_ahu": roles_per_ahu, "one_point_tags": one_point}

print(f"The graph has {len(g)} statements.\n")
print("Markers of bldg:AHU_1_DA_P:", ", ".join(markers))
print("\nIts tags:")
print(one_point.to_string(index=False))
print("\nFC1's inputs, found by role and equipRef:")
print(fc1_inputs.to_string(index=False))
print("\nPoints with a fault-rule role, per AHU:")
print(roles_per_ahu.to_string(index=False))
