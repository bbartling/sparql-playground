# Day 24 (pandas): external timeseries references. One model, history in SQLite *or* in a CSV.
# Run from the repo root (once: uv run bldgts model build && uv run bldgts bootstrap):
#     uv run python lessons/unit3-modeling/day24_pandas.py
#
# Each point in the model says where its history lives: a ref:TimeseriesReference with an id
# (ref:hasTimeseriesId) and a store (ref:storedAt). The model has one per point, to SQLite.
# We add a second one per FC1 input, to the AHU's CSV export, in memory (the .ttl file is not
# changed), read each series from the store its reference names, and compare the two stores.

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

# 4. The resolver: read each series (ts in epoch seconds, value) from the store it names
conn = sqlite3.connect("file:var/timeseries.sqlite?mode=ro", uri=True)  # read-only
series = {}
for _, ref in refs.iterrows():
    if ref["store_class"] == "Database":  # the SQLite store: look the id up in `samples`
        sql = "SELECT ts, value FROM samples WHERE timeseries_id = ?"
        one_series = pd.read_sql_query(sql, conn, params=[ref["timeseries_id"]])
    elif ref["store_class"] == "CsvFile":  # a CSV file: the id is a column name
        store = BLDG[ref["store"]]
        path = str(g.value(store, BTS.path))
        time_column = str(g.value(store, BTS.timeColumn))
        csv = pd.read_csv(path, usecols=[time_column, ref["timeseries_id"]])
        times = pd.to_datetime(csv[time_column], utc=True)
        epoch_seconds = times.dt.as_unit("s").astype("int64")
        one_series = pd.DataFrame({"ts": epoch_seconds, "value": csv[ref["timeseries_id"]]})
    else:
        raise ValueError("no reader for a store of class " + ref["store_class"])
    series[(ref["point_id"], ref["store_class"])] = one_series

# 5. Compare the two stores, point by point: same rows, same values?
compare_rows = []
for point_id in sorted(refs["point_id"].unique()):
    from_db = series[(point_id, "Database")]
    from_csv = series[(point_id, "CsvFile")]
    both = from_db.merge(from_csv, on="ts", suffixes=("_db", "_csv"))
    compare_rows.append(
        {
            "point_id": point_id,
            "rows_sqlite": len(from_db),
            "rows_csv": len(from_csv),
            "rows_equal": (both["value_db"] == both["value_csv"]).sum(),
            "max_abs_diff": (both["value_db"] - both["value_csv"]).abs().max(),
        }
    )
series_compare = pd.DataFrame(compare_rows)

print("References of FC1's input points (one store added to each, in memory):")
print(refs.to_string(index=False))
print("\nThe same series, read from SQLite and from the CSV file:")
print(series_compare.to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"refs": refs, "series_compare": series_compare}
