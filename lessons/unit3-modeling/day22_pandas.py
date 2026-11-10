# Day 22 (pandas): find FC1's inputs for AHU_1 by Haystack tags, with SPARQL on the RDF model.
# Run from the repo root:
#     uv run python lessons/unit3-modeling/day22_pandas.py
#
# model/building_50.ttl holds every point as Haystack tags written as RDF. rdflib loads it into
# memory and runs SPARQL. Nothing below names a column or an id: the query asks for roles.

import unicodedata

import pandas as pd
from rdflib import Graph

PREFIXES = """
PREFIX bts:  <https://example.org/openfdd/bldgts#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX ref:  <https://brickschema.org/schema/Brick/ref#>
"""

# 1. Load the model: a graph of (subject, predicate, object) statements, held in memory
g = Graph()
g.parse("model/building_50.ttl")

# 2. What does one point look like? Its markers (plain tags with no value)...
markers_query = (
    PREFIXES
    + """
SELECT ?marker WHERE { bldg:AHU_1_DA_P bts:hasHaystackMarker ?marker }
"""
)
markers = []
for row in g.query(markers_query):
    markers.append(str(row.marker))

# ...and its tags (a name and a value)
tags_query = (
    PREFIXES
    + """
SELECT ?tag_name ?tag_value WHERE {
  bldg:AHU_1_DA_P bts:hasHaystackTag ?tag .
  ?tag bts:tagName ?tag_name ; bts:tagValue ?tag_value .
}
"""
)
tags = []
for row in g.query(tags_query):
    value = str(row.tag_value).split("#")[-1]  # equipRef is an IRI; keep the part after the #
    value = unicodedata.normalize("NFKD", value)  # the unit's subscript 2 becomes a plain 2
    tags.append({"tag_name": str(row.tag_name), "tag_value": value})
one_point = pd.DataFrame(tags).sort_values("tag_name")

# 3. FC1's three inputs on AHU_1, found by tags. The first pattern starts from the points that
#    have a timeseries reference (118 of them), so every join after it stays small.
fc1_query = (
    PREFIXES
    + """
SELECT ?role ?point ?timeseries_id WHERE {
  ?point ref:hasExternalReference ?ref .
  ?ref ref:hasTimeseriesId ?timeseries_id .
  ?point bts:hasHaystackTag ?role_tag .
  ?role_tag bts:tagName "ofddRole" ; bts:tagValue ?role .
  FILTER(?role IN ("fan-status", "duct-static-pressure", "duct-static-pressure-sp"))
  ?point bts:hasHaystackTag ?equip_tag .
  ?equip_tag bts:tagName "equipRef" ; bts:tagValue bldg:AHU_1 .
}
"""
)
input_rows = []
for row in g.query(fc1_query):
    # an id like https://example.org/openfdd/BUILDING_50#AHU_1_DA_P: keep what follows the #
    point_id = str(row.point).split("#")[-1]
    input_rows.append(
        {
            "equipment_id": "AHU_1",
            "role": str(row.role),
            "point_id": point_id,
            "timeseries_id": str(row.timeseries_id),
        }
    )
fc1_inputs = pd.DataFrame(input_rows).sort_values("role")

# 4. How many AHU_1 points carry a fault-rule role at all?
count_query = (
    PREFIXES
    + """
SELECT (COUNT(?role) AS ?roles) WHERE {
  ?point ref:hasExternalReference ?ref .
  ?ref ref:hasTimeseriesId ?timeseries_id .
  ?point bts:hasHaystackTag ?role_tag .
  ?role_tag bts:tagName "ofddRole" ; bts:tagValue ?role .
  ?point bts:hasHaystackTag ?equip_tag .
  ?equip_tag bts:tagName "equipRef" ; bts:tagValue bldg:AHU_1 .
}
"""
)
for row in g.query(count_query):
    roles_count = int(row.roles)

print("The graph has", len(g), "statements.")
print("\nMarkers of bldg:AHU_1_DA_P:", ", ".join(sorted(markers)))
print("\nIts tags:")
print(one_point.to_string(index=False))
print("\nFC1's inputs on AHU_1, found by role and equipRef:")
print(fc1_inputs.to_string(index=False))
print("\nAHU_1 points with a fault-rule role:", roles_count)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"fc1_inputs": fc1_inputs, "roles_count": roles_count}
