# Day 24 (SQL): external timeseries references. One model, history in SQLite *or* in a CSV.
# Run from the repo root (once: uv run bldgts model build && uv run bldgts bootstrap):
#     uv run python lessons/unit3-modeling/day24_pandas.py
#
# Each point in the model says where its history lives: a ref:TimeseriesReference with an id
# (ref:hasTimeseriesId) and a store (ref:storedAt). The model has one per point, to SQLite.
# We add a second one per FC1 input, to the AHU's CSV export, in memory (the .ttl file is not
# changed), read each series from the store its reference names, and compare the two stores.
# SQL can't read RDF, so steps 1-3 (the model) are the same rdflib code as day24_pandas.py;
# steps 4-5 read and compare the series with SQL.

import json
import sqlite3

import pandas as pd
from rdflib import RDF, BNode, Graph, Literal, Namespace

BTS = Namespace("https://example.org/openfdd/bldgts#")
BLDG = Namespace("https://example.org/openfdd/BUILDING_50#")
REF = Namespace("https://brickschema.org/schema/Brick/ref#")
PREFIXES = """
PREFIX bts:  <https://example.org/openfdd/bldgts#>
PREFIX bldg: <https://example.org/openfdd/BUILDING_50#>
PREFIX ref:  <https://brickschema.org/schema/Brick/ref#>
"""

# 1. Load the model
g = Graph()
g.parse("model/building_50.ttl")

# 2. Add a CSV store for each AHU, and a second reference on each FC1 input point.
#    A CSV has no UUIDs, so that reference's id is the column name, from Day 21's column map.
inputs_query = (
    PREFIXES
    + """
SELECT DISTINCT ?point ?role WHERE {
  ?point ref:hasExternalReference ?ref .
  ?point bts:hasHaystackTag ?role_tag .
  ?role_tag bts:tagName "ofddRole" ; bts:tagValue ?role .
  FILTER(?role IN ("fan-status", "duct-static-pressure", "duct-static-pressure-sp"))
  ?point bts:hasHaystackTag ?equip_tag .
  ?equip_tag bts:tagName "equipRef" ; bts:tagValue ?equip .
}
"""
)
for ahu in ["AHU_1", "AHU_2"]:
    csv_store = BLDG["csv_" + ahu]
    g.add((csv_store, RDF.type, BTS.CsvFile))
    g.add((csv_store, BTS.path, Literal("data/BUILDING_50/" + ahu + "/history_wide.csv")))
    g.add((csv_store, BTS.timeColumn, Literal("timestamp_utc")))

    with open("data/BUILDING_50/" + ahu + "/column_map.json") as f:
        column_for_role = json.load(f)["points"]

    inputs = list(g.query(inputs_query, initBindings={"equip": BLDG[ahu]}))
    for row in inputs:
        reference = BNode()  # a new, unnamed node: the reference itself
        g.add((row.point, REF.hasExternalReference, reference))
        g.add((reference, RDF.type, REF.TimeseriesReference))
        g.add((reference, REF.hasTimeseriesId, Literal(column_for_role[str(row.role)])))
        g.add((reference, REF.storedAt, csv_store))

# 3. Every reference of FC1's input points: the id, the store, and what kind of store it is
refs_query = (
    PREFIXES
    + """
SELECT ?point ?timeseries_id ?store ?store_class WHERE {
  ?point ref:hasExternalReference ?ref .
  ?point bts:hasHaystackTag ?role_tag .
  ?role_tag bts:tagName "ofddRole" ; bts:tagValue ?role .
  FILTER(?role IN ("fan-status", "duct-static-pressure", "duct-static-pressure-sp"))
  ?ref ref:hasTimeseriesId ?timeseries_id ; ref:storedAt ?store .
  ?store a ?store_class .
}
"""
)
ref_rows = []
for row in g.query(refs_query):
    ref_rows.append(
        {
            "point_id": str(row.point).split("#")[-1],  # keep the part after the #
            "store": str(row.store).split("#")[-1],
            "store_class": str(row.store_class).split("#")[-1],
            "timeseries_id": str(row.timeseries_id),
        }
    )
refs = pd.DataFrame(ref_rows).sort_values(["point_id", "store"])

# 4. The resolver. The SQLite store is opened read-only. Each CSV series goes into a TEMP
#    table, with SQLite turning the time text into epoch seconds (unixepoch).
conn = sqlite3.connect("file:var/timeseries.sqlite?mode=ro", uri=True)
conn.execute("CREATE TEMP TABLE csv_series (point_id TEXT, ts INTEGER, value REAL)")
insert_sql = "INSERT INTO csv_series (point_id, ts, value) VALUES (?, unixepoch(?), ?)"
for _, ref in refs.iterrows():
    if ref["store_class"] == "Database":
        continue  # already in `samples`; step 5 reads it there
    elif ref["store_class"] == "CsvFile":  # a CSV file: the id is a column name
        store = BLDG[ref["store"]]
        path = str(g.value(store, BTS.path))
        time_column = str(g.value(store, BTS.timeColumn))
        csv = pd.read_csv(path, usecols=[time_column, ref["timeseries_id"]])
        for time_text, value in zip(csv[time_column], csv[ref["timeseries_id"]], strict=True):
            conn.execute(insert_sql, [ref["point_id"], time_text, value])
    else:
        raise ValueError("no reader for a store of class " + ref["store_class"])
conn.execute("CREATE INDEX temp.csv_series_idx ON csv_series (point_id, ts)")

# 5. Compare the two stores, point by point: same rows, same values?
compare_sql = """
SELECT
  (SELECT COUNT(*) FROM samples WHERE timeseries_id = :timeseries_id) AS rows_sqlite,
  (SELECT COUNT(*) FROM csv_series WHERE point_id = :point_id) AS rows_csv,
  SUM(s.value = c.value) AS rows_equal,
  MAX(ABS(s.value - c.value)) AS max_abs_diff
FROM samples AS s
JOIN csv_series AS c ON c.ts = s.ts
WHERE s.timeseries_id = :timeseries_id AND c.point_id = :point_id
"""
db_refs = refs[refs["store_class"] == "Database"]
compare_rows = []
for _, ref in db_refs.iterrows():
    ids = {"point_id": ref["point_id"], "timeseries_id": ref["timeseries_id"]}
    rows_sqlite, rows_csv, rows_equal, max_abs_diff = conn.execute(compare_sql, ids).fetchone()
    compare_rows.append(
        {
            "point_id": ref["point_id"],
            "rows_sqlite": rows_sqlite,
            "rows_csv": rows_csv,
            "rows_equal": rows_equal,
            "max_abs_diff": max_abs_diff,
        }
    )
series_compare = pd.DataFrame(compare_rows)

print("References of FC1's input points (one store added to each, in memory):")
print(refs.to_string(index=False))
print("\nThe same series, read from SQLite and from the CSV file:")
print(series_compare.to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"refs": refs, "series_compare": series_compare}
