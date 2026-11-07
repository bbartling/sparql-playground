# Day 6 — A point list table (`lab_point`), and why it's a stand-in for the RDF model

**Goal:** get the point list into the database (and into a DataFrame), so queries can say "duct static pressure"
instead of a UUID.

## Read

The UUID → meaning mapping lives in `model/points/*.csv`, one file per AHU. Today you flatten both files into one
table, `lab_point`. `lab.load_points(conn)` does it (it adds `equipment_id`, which isn't a column in the files; it
comes from the file name, `BUILDING_50__AHU_1.csv` → `AHU_1`).

| Column | Example | Meaning |
|---|---|---|
| `timeseries_id` | `52422584-…` | joins to `samples.timeseries_id` |
| `point_id` | `AHU_1_DA_P` | a readable name for the point |
| `equipment_id` | `AHU_1` | which AHU's mapping file it came from |
| `owner_id` | `AHU_1_Supply_Fan` | the piece of equipment the point belongs to |
| `brick_class` | `Supply_Air_Static_Pressure_Sensor` | what kind of point it is (Brick vocabulary, Unit 3) |
| `unit` | `IN_H2O` | engineering unit |
| `openfdd_role` | `duct-static-pressure` | the role a fault rule asks for, if any |
| `source_column` | `da_p_inwc` | the column name in the BAS export |

Weeks 1 and 2 stay in the raw units the BAS logged: °F, inH2O, and percent 0–100. The SI conversion (°C, Pa,
fractions) happens once, on Day 11.

**Two ways to hold the same table.** In SQL it's a table with a primary key. In pandas it's a DataFrame you build
with `pd.read_csv` and `pd.concat`. The same operations have different names:

| Question | SQL on `lab_point` | pandas on a DataFrame `pts` |
|---|---|---|
| how many rows | `SELECT count(*)` | `len(pts)` |
| non-NULL count | `count(openfdd_role)` | `pts["openfdd_role"].count()` |
| distinct count | `count(DISTINCT brick_class)` | `pts["brick_class"].nunique()` |
| rows per group | `GROUP BY equipment_id` | `pts.groupby("equipment_id").size()` |
| filter | `WHERE equipment_id = 'AHU_1'` | `pts[pts.equipment_id == "AHU_1"]` |
| NULL test | `IS NOT NULL` | `.notna()` (never `== None`) |

Both treat a missing value as "unknown": SQL's `NULL` and pandas' `NaN` refuse to equal anything, even themselves.
That's why SQL needs `IS NOT NULL`, and why `= NULL` matches nothing.

**Why the primary key matters.** `lab_point.timeseries_id` is the primary key, so SQLite keeps a B-tree on it.
Finding one point by UUID is O(log n), not a scan of every row. For 118 points that's invisible, but it is the exact
lookup Day 7's join does for each of 924,000 role readings. A DataFrame has no index on a column unless you ask for
one (`set_index`); a plain boolean filter scans every row, O(n).

**Why this table is a compromise.** Look at `owner_id`: the supply fan status belongs to `AHU_1_Supply_Fan`, which
is part of `AHU_1`. Zone temperatures belong to `Zone_VAV_107`, which AHU_1 feeds. A flat table holds *one*
"belongs to" column. A building is a **graph**: fans are part of AHUs, AHUs feed zones, sensors are points of
equipment. You'll be tempted to write `owner_id LIKE 'AHU_1%'`. That works here by luck of the naming and breaks
on the next site. The RDF model stores those relationships explicitly (`brick:isPartOf`, `brick:feeds`,
`brick:isPointOf`), and Units 3–4 query them with SPARQL. For three weeks of SQL, this table is enough.

## Run

```python
import numpy as np
import pandas as pd

import lab

conn = lab.connect()
lab.ensure_points(conn)  # creates lab_point from model/points/*.csv if it isn't there yet
```

**The point list in pandas,** straight from the CSV files. This is the oracle: `lab_point` has to match it.

```python
frames = []
for path in lab.POINT_CSVS:
    df = pd.read_csv(path, dtype=str)  # keep everything as text, like the table
    df["equipment_id"] = path.stem.split("__", 1)[1]  # BUILDING_50__AHU_1 -> AHU_1
    frames.append(df)
pts = pd.concat(frames, ignore_index=True)
pts = pts.astype(object).where(
    pts.notna(), None
)  # NaN -> None, so text NULLs compare equal in parity

COLUMNS = [
    "timeseries_id",
    "point_id",
    "equipment_id",
    "owner_id",
    "label",
    "brick_class",
    "unit",
    "openfdd_role",
    "source_column",
]
lab_point = lab.query(conn, "SELECT * FROM lab_point")
lab.assert_parity(pts[COLUMNS], lab_point, keys=["timeseries_id"], label="lab_point vs CSV files")
print(pts[COLUMNS].head(3).to_string(index=False))
```

Same 118 rows, same values. Empty CSV cells come out of `read_csv` as `NaN` and are `NULL` in the table. We turned
the `NaN`s into `None` (what `sqlite3` turns `NULL` into) so that missing *text* compares equal; `.notna()` and
`.count()` treat both the same.

```python
COUNTS_SQL = """
SELECT count(*) AS points, count(openfdd_role) AS with_role, count(DISTINCT brick_class) AS classes
FROM lab_point
"""
counts_sql = lab.query(conn, COUNTS_SQL)
counts_pd = pd.DataFrame(
    {
        "points": [len(pts)],
        "with_role": [pts["openfdd_role"].count()],
        "classes": [pts["brick_class"].nunique()],
    }
)
lab.assert_parity(counts_pd, counts_sql, label="counts")
print(counts_sql.iloc[0].to_dict())
assert counts_sql.iloc[0].tolist() == [118, 26, 30]
```

`count(openfdd_role)` skips NULLs, so 26 of the 118 points have a fault-rule role: 13 per AHU.

```python
PER_EQUIP_SQL = """
SELECT equipment_id, count(*) AS points
FROM lab_point
GROUP BY equipment_id
ORDER BY equipment_id
"""
per_equip_sql = lab.query(conn, PER_EQUIP_SQL)
per_equip_pd = pts.groupby("equipment_id").size().rename("points").reset_index()
lab.assert_parity(per_equip_pd, per_equip_sql, label="points per AHU")
print(per_equip_sql.to_string(index=False))
assert per_equip_sql.set_index("equipment_id")["points"].to_dict() == {"AHU_1": 83, "AHU_2": 35}
```

```python
ROLES_SQL = """
SELECT openfdd_role, point_id, unit, timeseries_id
FROM lab_point
WHERE equipment_id = :equip AND openfdd_role IS NOT NULL
ORDER BY openfdd_role
"""
roles_sql = lab.query(conn, ROLES_SQL, {"equip": "AHU_1"})
sel = pts[(pts.equipment_id == "AHU_1") & pts.openfdd_role.notna()]
lab.assert_parity(
    sel[["openfdd_role", "point_id", "unit", "timeseries_id"]].reset_index(drop=True),
    roles_sql,
    keys=["openfdd_role"],
    label="AHU_1 roles",
)
print(roles_sql[["openfdd_role", "point_id", "unit"]].to_string(index=False))
assert len(roles_sql) == 13
```

`IS NOT NULL` in SQL, `.notna()` in pandas. Never `!= NULL` or `!= None`: a comparison with a missing value is
never true.

**Is `lab_point` really the model?** The app's RDF model (`model/building_50.ttl`) was built from these same CSV
files. Ask its SPARQL endpoint for every point that has an `ofddRole` tag: which equipment it belongs to
(`equipRef`) and its timeseries UUID. `lab.Api` runs the repo's FastAPI app in-process (no server, same database),
and `api.sparql` returns a DataFrame. Equipment comes back as an IRI, so we keep the local name after `#`.

```python
MODEL_QUERY = """
PREFIX bts: <https://example.org/openfdd/bldgts#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>
SELECT ?equip ?role ?timeseriesId WHERE {
  ?point ref:hasExternalReference ?ref .
  ?ref ref:hasTimeseriesId ?timeseriesId .
  ?point bts:hasHaystackTag ?roleTag .
  ?roleTag bts:tagName "ofddRole" ; bts:tagValue ?role .
  ?point bts:hasHaystackTag ?direct .
  ?direct bts:tagName "equipRef" ; bts:tagValue ?equip .
}
"""
with lab.Api() as api:
    graph = api.sparql(MODEL_QUERY)
graph["equipment_id"] = graph["equip"].str.split("#").str[-1]  # .../BUILDING_50#AHU_1 -> AHU_1
graph = graph.rename(columns={"role": "openfdd_role", "timeseriesId": "timeseries_id"})
graph = graph[["equipment_id", "openfdd_role", "timeseries_id"]]

TRIPLE_SQL = """
SELECT equipment_id, openfdd_role, timeseries_id FROM lab_point WHERE openfdd_role IS NOT NULL
"""
from_sql = lab.query(conn, TRIPLE_SQL)
from_csv = pts.loc[
    pts.openfdd_role.notna(), ["equipment_id", "openfdd_role", "timeseries_id"]
].reset_index(drop=True)

lab.assert_parity(from_csv, from_sql, label="CSV files vs lab_point (SQL)")
lab.assert_parity(from_csv, graph, label="CSV files vs the RDF model (SPARQL)")
assert len(graph) == 26
```

Three routes to the same 26 `(equipment, role, UUID)` facts: the CSV files read with pandas, the SQL table, and a
SPARQL query over the graph. That is the point of today: `lab_point` is a flat copy of what the model says. What the
flat copy can't hold is the structure around those facts (fans *part of* AHUs, AHUs *feeding* zones), and that's
what SPARQL adds.

The order of the patterns in `MODEL_QUERY` is deliberate. rdflib evaluates them roughly top to bottom, like a nested
loop join (Day 7). Starting from `ref:hasExternalReference` binds only the 118 points that have history, so every
later pattern is a cheap lookup. Starting from "every tag named `ofddRole`" first is the same answer but a much bigger
intermediate result, slow enough to hit the API's 10-second query timeout. A database's query planner reorders joins
for you; a simple SPARQL engine may not.

(One performance note. The patterns start from points that have a timeseries UUID, the 118 selective ones. With
the same patterns listed in another order the query took over 10 seconds and the API cut it off with a 504. A graph
engine, like SQLite's join planner on Day 8, is sensitive to where it starts.)

**What the primary key buys.** Look up one point by UUID three ways: SQL through the primary-key index, a pandas
boolean filter (scans every row), and a pandas lookup after `set_index` (a hash table). With 118 rows all three are
microseconds, so repeat the table 2,000 times to make the scan visible.

```python
big = pd.concat([pts] * 2000, ignore_index=True)  # 236,000 rows, 118 distinct UUIDs
target = pts.timeseries_id.iloc[-1]
by_uuid = big.set_index("timeseries_id").sort_index()  # a sorted index on the column

t_scan = lab.best_time(lambda: big[big.timeseries_id == target])
t_index = lab.best_time(lambda: by_uuid.loc[[target]])
t_sql = lab.best_time(
    lambda: conn.execute("SELECT * FROM lab_point WHERE timeseries_id = ?", (target,)).fetchall()
)
print(
    f"pandas scan {t_scan * 1e6:8.0f} us | pandas index {t_index * 1e6:8.0f} us | SQL primary key {t_sql * 1e6:6.0f} us"
)
assert t_sql < t_scan  # an index lookup beats scanning 236,000 rows
```

The scan touches every row; the indexed lookups don't. SQLite's table is tiny, but its lookup cost would barely
change at 118 million rows (a B-tree grows one level per ~100× more rows). That is why Day 7's join can afford to
look up a point for every reading.

## Try it

1. What is AHU_2's duct static pressure UUID?
2. Why does AHU_1 have 83 points but AHU_2 only 35? Look at `brick_class`.

<details><summary>Answers</summary>

```python
UUID_SQL = """
SELECT timeseries_id FROM lab_point
WHERE equipment_id = 'AHU_2' AND openfdd_role = 'duct-static-pressure'
"""
uuid_sql = lab.query(conn, UUID_SQL)
mask = (pts.equipment_id == "AHU_2") & (pts.openfdd_role == "duct-static-pressure")
lab.assert_parity(
    pts.loc[mask, ["timeseries_id"]].reset_index(drop=True), uuid_sql, label="AHU_2 static UUID"
)
assert uuid_sql.iloc[0, 0] == "f8a0d594-2fff-567a-9853-71ba66233eba"
print(uuid_sql.iloc[0, 0])
```

```python
ZONE_SQL = """
SELECT equipment_id, count(*) AS zone_temps FROM lab_point
WHERE brick_class = 'Zone_Air_Temperature_Sensor'
GROUP BY equipment_id
"""
zone_sql = lab.query(conn, ZONE_SQL)
zones = pts[pts.brick_class == "Zone_Air_Temperature_Sensor"]
zone_pd = zones.groupby("equipment_id").size().rename("zone_temps").reset_index()
lab.assert_parity(zone_pd, zone_sql, label="zone temperature sensors")
print(zone_sql.to_string(index=False))
assert zone_sql.set_index("equipment_id")["zone_temps"].to_dict() == {"AHU_1": 47}
```

AHU_1's export included the zone temperatures of the VAV boxes it serves (47 of them). AHU_2's didn't, so it has no
row at all in the result. Same kind of building, different export: a point list tells you what was **exported**,
not what exists.

</details>

## Why it matters

`lab_point` is a lookup table: id → attributes. In week 5 you'll build the same thing as a dict in Python (a hash
table, O(1) per lookup, like the pandas index above), then as a set of triples `(point, hasUnit, IN_H2O)`. That's
the shape of RDF.
