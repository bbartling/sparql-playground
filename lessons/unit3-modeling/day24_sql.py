"""Day 24, SQL: external timeseries references, with the history in SQLite *or* in a CSV file.

    uv run python lessons/unit3-modeling/day24_sql.py

Needs var/timeseries.sqlite (`uv run bldgts model build && uv run bldgts bootstrap`). The model
part is the same as day24_pandas.py (rdflib + SPARQL on an in-memory graph; a SQL database can't
read RDF). The resolver differs: for each reference it returns the SQL that reads that series from
the store the reference names, and SQLite compares the two stores. A CSV store is first loaded
into a TEMP table. Compare the printout with day24_pandas.py: the numbers should match."""

import csv
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


# 4. The resolver: for one reference, the SQL (and parameters) that read its series from the
#    store it names.
conn = sqlite3.connect(
    ":memory:", uri=True
)  # scratch connection; the samples database is attached read-only below
sqlite_stores = {}  # store IRI -> schema name of the attached SQLite database
csv_tables = {}  # store IRI -> name of the TEMP table holding that CSV file


def quote_ident(name: str, allowed: set[str]) -> str:
    """Identifiers can't be bound as parameters: accept a name that really exists, then quote it."""
    if name not in allowed:
        raise ValueError(f"unknown column {name!r}")
    return '"' + name.replace('"', '""') + '"'


def attach_sqlite(store: str) -> str:
    node = URIRef(store)
    backend = str(g.value(node, BTS.backend))
    if backend != "sqlite":
        raise ValueError(f"no reader for database backend {backend!r}")
    env = str(g.value(node, BTS.connectionEnv))
    path = Path(os.environ.get(env, ROOT / "var" / "timeseries.sqlite"))
    conn.execute("ATTACH DATABASE ? AS tsdb", (f"file:{path.as_posix()}?mode=ro",))
    return "tsdb"


def load_csv(store: str, columns: set[str]) -> str:
    """Load the columns a CSV store is asked for into a TEMP table (REAL values, epoch ts)."""
    node = URIRef(store)
    time_col = str(g.value(node, BTS.timeColumn))
    name = f"csv_{local(node)}"
    with open(ROOT / str(g.value(node, BTS.path)), encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        wanted = [header.index(c) for c in sorted(columns)]  # raises if a column is missing
        t = header.index(time_col)
        cols = ", ".join(f"{quote_ident(c, set(header))} REAL" for c in sorted(columns))
        conn.execute(f'CREATE TEMP TABLE "{name}" (ts INTEGER PRIMARY KEY, {cols}) WITHOUT ROWID')
        marks = ", ".join("?" * (len(wanted) + 1))
        conn.executemany(
            f'INSERT INTO "{name}" VALUES ({marks})',
            ([r[t], *(float(r[i]) if r[i] != "" else None for i in wanted)] for r in reader),
        )
    # the time text ('2026-03-16 00:40:00+00:00') becomes epoch seconds, like samples.ts
    conn.execute(f'UPDATE "{name}" SET ts = unixepoch(ts)')
    return name


def series_sql(store: str, store_class: str, ts_id: str, key: str) -> tuple[str, dict]:
    """`key` makes the bound parameter name unique when two series go into one query."""
    if store_class == "Database":  # ref:Database; the model says backend sqlite, path in an env var
        if store not in sqlite_stores:
            sqlite_stores[store] = attach_sqlite(store)
        schema = sqlite_stores[store]
        sql = f"SELECT ts, value FROM {schema}.samples WHERE timeseries_id = :id_{key}"
        return sql, {f"id_{key}": ts_id}
    if store_class == "CsvFile":  # bts:CsvFile; the id is the column name
        table = csv_tables[store]
        col = quote_ident(ts_id, csv_columns[store])
        return f'SELECT ts, {col} AS value FROM temp."{table}"', {}
    raise ValueError(f"no reader for store class {store_class!r}")


# CSV stores are loaded once, with just the columns the references name.
csv_columns = {}
for r in refs[refs["store_class"] == "CsvFile"].itertuples():
    csv_columns.setdefault(r.store_iri, set()).add(r.timeseries_id)
for store, columns in csv_columns.items():
    csv_tables[store] = load_csv(store, columns)

# 5. Resolve every reference of every FC1 point, and compare the two stores point by point.
COMPARE_SQL = """
WITH a AS ({sql_a}), b AS ({sql_b})
SELECT :point_id AS point_id,
       (SELECT count(*) FROM a) AS rows_sqlite,
       (SELECT count(*) FROM b) AS rows_csv,
       sum(a.value = b.value)   AS rows_equal,
       max(abs(a.value - b.value)) AS max_abs_diff
FROM a JOIN b ON b.ts = a.ts
"""
parts = []
for point_id, grp in refs.groupby("point_id"):
    by_class = {r.store_class: r for r in grp.itertuples()}
    db, cf = by_class["Database"], by_class["CsvFile"]
    sql_a, params_a = series_sql(db.store_iri, "Database", db.timeseries_id, "a")
    sql_b, params_b = series_sql(cf.store_iri, "CsvFile", cf.timeseries_id, "b")
    params = {"point_id": point_id} | params_a | params_b
    parts.append(
        pd.read_sql_query(COMPARE_SQL.format(sql_a=sql_a, sql_b=sql_b), conn, params=params)
    )
series_compare = pd.concat(parts, ignore_index=True)

RESULTS = {
    "refs": refs[["point_id", "store", "store_class", "timeseries_id"]],
    "series_compare": series_compare,
}

print("References of FC1's input points (a second store was added to each point in memory):")
print(RESULTS["refs"].to_string(index=False))
print("\nThe same series, read from SQLite and from the CSV file:")
print(series_compare.to_string(index=False))
