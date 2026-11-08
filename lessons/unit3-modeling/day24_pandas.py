"""Day 24, pandas: external timeseries references, with the history in SQLite *or* in a CSV file.

    uv run python lessons/unit3-modeling/day24_pandas.py

Needs var/timeseries.sqlite (`uv run bldgts model build && uv run bldgts bootstrap`). Each point
in the model says where its history lives with a ref:TimeseriesReference: an id
(ref:hasTimeseriesId) and a store (ref:storedAt). The model already has one reference per point,
to the SQLite store. Here we add a second reference per point, to the AHU's CSV export, in an
in-memory copy of the graph. A small resolver reads a point's series from whichever store a
reference names, and we check both stores hold the same series. Compare the printout with
day24_sql.py: the numbers should match."""

import json
import os
import sqlite3
from pathlib import Path

import pandas as pd
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"
MODEL = ROOT / "model" / "building_50.ttl"
AHUS = ("AHU_1", "AHU_2")

BTS = Namespace("https://example.org/openfdd/bldgts#")
BLDG = Namespace("https://example.org/openfdd/BUILDING_50#")
REF = Namespace("https://brickschema.org/schema/Brick/ref#")
PREFIXES = f"PREFIX bts: <{BTS}>\nPREFIX bldg: <{BLDG}>\nPREFIX ref: <{REF}>\n"


def local(iri) -> str:
    return str(iri).rsplit("#", 1)[-1]


# 1. Load the model. It was built with one reference per point, all to bldg:timeseries_db (SQLite).
g = Graph()
g.parse(MODEL, format="turtle")

# 2. Add a second kind of store: a CSV file. Plain Haystack has no tag for "where is the history";
#    the ref schema does, and it doesn't care what the store is. Brick's ref:Database means a
#    database, so we don't call a file one: we give CSV files their own class, bts:CsvFile, with
#    a path.
#    The "id" a CSV reference holds is the column name (a CSV has no UUIDs).
ROLE_POINTS_SPARQL = (
    PREFIXES
    + """
SELECT ?equip ?role ?point WHERE {
  ?point ref:hasExternalReference ?r .
  ?point bts:hasHaystackTag ?role_tag .
  ?role_tag bts:tagName "ofddRole" ; bts:tagValue ?role .
  ?point bts:hasHaystackTag ?equip_tag .
  ?equip_tag bts:tagName "equipRef" ; bts:tagValue ?equip .
}"""
)
role_points = [(r.equip, str(r.role), r.point) for r in g.query(ROLE_POINTS_SPARQL)]
col_map = {e: json.loads((DATA / e / "column_map.json").read_text())["points"] for e in AHUS}
for equip in AHUS:
    csv_store = BLDG[f"csv_{equip}"]
    g.add((csv_store, RDF.type, BTS.CsvFile))
    g.add((csv_store, BTS.path, Literal(f"data/BUILDING_50/{equip}/history_wide.csv")))
    g.add((csv_store, BTS.timeColumn, Literal("timestamp_utc")))
for equip_iri, role, point in role_points:
    column = col_map[local(equip_iri)].get(role)  # role -> column, from Day 21's first model
    if column is None:
        continue
    node = BNode()
    g.add((point, REF.hasExternalReference, node))
    g.add((node, RDF.type, REF.TimeseriesReference))
    g.add((node, REF.hasTimeseriesId, Literal(column)))
    g.add((node, REF.storedAt, BLDG[f"csv_{local(equip_iri)}"]))

# 3. Pick FC1's inputs by tag (Day 22) and list every reference each one has.
FC1_POINTS_SPARQL = (
    PREFIXES
    + """
SELECT DISTINCT ?point WHERE {
  ?point ref:hasExternalReference ?r .
  ?point bts:hasHaystackTag ?role_tag .
  ?role_tag bts:tagName "ofddRole" ; bts:tagValue ?role .
  FILTER(?role IN ("fan-status", "duct-static-pressure", "duct-static-pressure-sp"))
}"""
)
REFS_SPARQL = (
    PREFIXES
    + """
SELECT ?point ?ts_id ?store ?store_class WHERE {
  ?point ref:hasExternalReference ?r .
  ?r a ref:TimeseriesReference ; ref:hasTimeseriesId ?ts_id ; ref:storedAt ?store .
  ?store a ?store_class .
}"""
)
fc1_points = sorted(r.point for r in g.query(FC1_POINTS_SPARQL))
refs = pd.DataFrame(
    [
        (local(p), local(r.store), local(r.store_class), str(r.ts_id), str(r.store), str(p))
        for p in fc1_points
        for r in g.query(REFS_SPARQL, initBindings={"point": p})
    ],
    columns=["point_id", "store", "store_class", "timeseries_id", "store_iri", "point_iri"],
).sort_values(["point_id", "store"], ignore_index=True)


# 4. The resolver: read one reference's series (ts in epoch seconds, value) from the store it names.
def read_series(store: str, store_class: str, ts_id: str) -> pd.DataFrame:
    node = URIRef(store)
    if store_class == "Database":  # ref:Database; the model says backend sqlite, path in an env var
        backend = str(g.value(node, BTS.backend))
        if backend != "sqlite":
            raise ValueError(f"no reader for database backend {backend!r}")
        env = str(g.value(node, BTS.connectionEnv))
        path = Path(os.environ.get(env, ROOT / "var" / "timeseries.sqlite"))
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        sql = "SELECT ts, value FROM samples WHERE timeseries_id = ? ORDER BY ts"
        df = pd.read_sql_query(sql, conn, params=[ts_id])
        conn.close()
        return df
    if store_class == "CsvFile":  # bts:CsvFile; the id is the column name
        time_col = str(g.value(node, BTS.timeColumn))
        df = pd.read_csv(ROOT / str(g.value(node, BTS.path)), usecols=[time_col, ts_id])
        ts = pd.to_datetime(df[time_col], utc=True).dt.as_unit("s").astype("int64")
        return pd.DataFrame({"ts": ts, "value": df[ts_id]})
    raise ValueError(f"no reader for store class {store_class!r}")


# 5. Resolve every reference of every FC1 point, and compare the two stores point by point.
series = {
    (r.point_id, r.store_class): read_series(r.store_iri, r.store_class, r.timeseries_id)
    for r in refs.itertuples()
}
rows = []
for point_id in sorted({p for p, _ in series}):
    db, csv = series[(point_id, "Database")], series[(point_id, "CsvFile")]
    both = db.merge(csv, on="ts", suffixes=("_db", "_csv"))
    rows.append(
        {
            "point_id": point_id,
            "rows_sqlite": len(db),
            "rows_csv": len(csv),
            "rows_equal": int((both["value_db"] == both["value_csv"]).sum()),
            "max_abs_diff": float((both["value_db"] - both["value_csv"]).abs().max()),
        }
    )
series_compare = pd.DataFrame(rows)

RESULTS = {
    "refs": refs[["point_id", "store", "store_class", "timeseries_id"]],
    "series_compare": series_compare,
}

print("References of FC1's input points (a second store was added to each point in memory):")
print(RESULTS["refs"].to_string(index=False))
print("\nThe same series, read from SQLite and from the CSV file:")
print(series_compare.to_string(index=False))
