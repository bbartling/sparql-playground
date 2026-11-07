# Day 2 — SELECT, WHERE, ORDER BY, LIMIT on one sensor; what the UUIDs are

**Goal:** pull the readings of one sensor, sorted and trimmed, in SQL and in pandas, and know where its id comes from.

## Read

A `timeseries_id` looks like `bf422925-1e2d-598d-9069-3b0f17d49c48`. That's a **UUID**, a 128-bit id written as 32
hex digits. These are version-5 UUIDs: a hash of a name, so the same building/point always gets the same UUID. They
don't change between rebuilds, and the API can hand them out without exposing the BAS's internal point names.

The database doesn't know what a UUID means. That lives in the point list the model is built from,
`model/points/BUILDING_50__AHU_1.csv`. Open it in a text editor or spreadsheet and find this row:

| source_column | point_id | brick_class | unit | openfdd_role | timeseries_id |
|---|---|---|---|---|---|
| outside_air_temp_f | AHU_1_OA_T | Outside_Air_Temperature_Sensor | DEG_F | outside-air-temp | bf422925-1e2d-598d-9069-3b0f17d49c48 |

So `bf422925…` is AHU_1's outside air temperature in °F. Here are a few you'll use this week:

| Point | timeseries_id |
|---|---|
| AHU_1 outside air temp (°F) | `bf422925-1e2d-598d-9069-3b0f17d49c48` |
| AHU_1 supply fan status (1 = running) | `9ebf80dd-7821-510b-b2c0-cd0151e093c9` |
| AHU_1 duct static pressure (inH2O) | `52422584-9894-50bd-9696-2fbb8b062518` |
| AHU_1 duct static pressure setpoint (inH2O) | `761c2b61-4982-5157-bc66-2010cf6e2a47` |

The parts of a query, in the order you write them, and the pandas that does each job:

```
SELECT  columns            -- what to show            df[["ts", "value"]]
FROM    table              -- where from              (the DataFrame you loaded)
WHERE   condition          -- which rows              df[df.value > 1.5]
ORDER BY column [DESC]     -- sorted how              .sort_values("value", ascending=False)
LIMIT   n                  -- how many                .head(n)
```

Text values go in single quotes in SQL. Double quotes are for column and table names.

**Parameters, not f-strings.** In Python you'll be tempted to build SQL with an f-string:
`f"... WHERE timeseries_id = '{uid}'"`. Don't. If `uid` ever comes from a user, a file or an API request, a
value like `x' OR '1'='1` rewrites your query (**SQL injection**), and even with trusted values you get quoting bugs.
Instead leave a placeholder, `?` or a name like `:uid`, and pass the value separately. The database receives the
SQL text and the value as two different things, so a value can never be mistaken for SQL. It also lets SQLite
reuse the compiled query. Every query in this course passes values as parameters.

**Where the work happens.** `WHERE timeseries_id = ?` is the best case for this table. The primary key is
`(timeseries_id, ts)` and the rows are stored in that order in a B-tree, so SQLite **seeks** straight to the first
row of that series and reads the next 35,536 rows in a row: O(log n + k) for n rows in the table and k rows
returned. pandas has no such luxury. Once a table is loaded, `df[df.timeseries_id == uid]` compares every one of
the n rows: O(n). (A pandas `set_index` on the id sorts the frame and lets it do the same kind of lookup, but you
pay for that sort, and you had to load everything first.) So the usual pattern is: let SQL pick the rows, then use
pandas on what comes back.

## Run

```python
import numpy as np
import pandas as pd

import lab

conn = lab.connect()

OAT = "bf422925-1e2d-598d-9069-3b0f17d49c48"  # AHU_1 outside air temp, F
FAN = "9ebf80dd-7821-510b-b2c0-cd0151e093c9"  # AHU_1 supply fan status, 0/1
STATIC = "52422584-9894-50bd-9696-2fbb8b062518"  # AHU_1 duct static pressure, inH2O
STATIC_SP = "761c2b61-4982-5157-bc66-2010cf6e2a47"  # AHU_1 duct static pressure setpoint, inH2O

# Load ONE series for the pandas side. The id is a bound parameter.
SERIES_SQL = "SELECT ts, value FROM samples WHERE timeseries_id = :uid"


def series(uid):
    return lab.query(conn, SERIES_SQL, {"uid": uid})


oat = series(OAT)
print(len(oat), "rows")
assert len(oat) == 35_536
```

**The first three outside air readings.**

```python
FIRST3_SQL = """
SELECT ts, value
FROM samples
WHERE timeseries_id = :uid
ORDER BY ts
LIMIT 3
"""
first3_sql = lab.query(conn, FIRST3_SQL, {"uid": OAT})
first3_pd = oat.sort_values("ts").head(3).reset_index(drop=True)
lab.assert_parity(first3_pd, first3_sql, keys=["ts"], label="first 3 readings")
print(first3_sql)
assert first3_sql.iloc[0].tolist() == [1773621600, 69.0327]
```

**The hottest reading.** Sort by value, biggest first, keep one row. Adding `ts` as a second sort key makes the
answer deterministic if two readings tie.

```python
HOTTEST_SQL = """
SELECT ts, value
FROM samples
WHERE timeseries_id = :uid
ORDER BY value DESC, ts
LIMIT 1
"""
hottest_sql = lab.query(conn, HOTTEST_SQL, {"uid": OAT})
hottest_pd = (
    oat.sort_values(["value", "ts"], ascending=[False, True]).head(1).reset_index(drop=True)
)
lab.assert_parity(hottest_pd, hottest_sql, label="hottest reading")
assert hottest_sql.iloc[0].tolist() == [1784065200, 98.8608]
```

**Readings above 1.5 inH2O on AHU_1's duct static pressure.**

```python
HIGH_SQL = """
SELECT count(*) AS n
FROM samples
WHERE timeseries_id = :uid
  AND value > :limit
"""
high_sql = lab.query(conn, HIGH_SQL, {"uid": STATIC, "limit": 1.5})
static = series(STATIC)
high_pd = pd.DataFrame(
    {"n": [int((static["value"] > 1.5).sum())]}
)  # boolean mask, then count the Trues
lab.assert_parity(high_pd, high_sql, label="static > 1.5")
assert high_sql.n[0] == 8336
```

In pandas, `static["value"] > 1.5` makes a column of True/False, one per row, and `.sum()` counts the Trues. SQL's
`WHERE` drops the rows and `count(*)` counts what's left. Same answer, same O(k) work over the series; the
difference is that SQL never builds the 35,536-element mask or sends the rows to Python at all.

A look at the injection problem from above. The user-supplied string is treated as a plain id that matches nothing:

```python
evil = "x' OR '1'='1"
evil_sql = lab.query(
    conn, "SELECT count(*) AS n FROM samples WHERE timeseries_id = :uid", {"uid": evil}
)
print(evil_sql.n[0], "rows for a hostile id")
assert evil_sql.n[0] == 0  # with an f-string this would have counted the whole table
```

**The same slice through the API.** A real application doesn't open the SQLite file. It asks a service over HTTP and
gets JSON back. This repo has one (`bldgts serve`, a FastAPI app), and `lab.Api` drives it in-process with
FastAPI's test client, so it runs offline against the same database copy. The API speaks in **point ids** such as
`AHU_1_OA_T`, names the building model knows; the model maps each point id to the `timeseries_id` UUID that the
`samples` table is keyed on (Unit 4 asks the model that question in SPARQL). The service looks up the UUID, runs a
SQL query much like the ones above, and returns the rows as JSON. Here is 1 July 2026 (288 readings) three ways. The
API's `end` is inclusive, so we pass the last second of the day.

```python
DAY_SQL = """
SELECT ts, value FROM samples
WHERE timeseries_id = :uid AND ts >= :start AND ts < :end
"""
t0 = 1782864000  # 2026-07-01 00:00 UTC
day_sql = lab.query(conn, DAY_SQL, {"uid": OAT, "start": t0, "end": t0 + 86_400})
day_pd = oat[(oat.ts >= t0) & (oat.ts < t0 + 86_400)].reset_index(drop=True)

with lab.Api() as api:
    day_api = api.timeseries(
        "AHU_1_OA_T", start=t0, end=t0 + 86_399
    )  # HTTP GET -> JSON -> DataFrame
print(day_api.attrs)  # the model's point id -> UUID mapping, returned with the data

assert day_api.attrs["timeseries_id"] == OAT
lab.assert_parity(day_pd, day_sql, keys=["ts"], label="pandas == SQL")
lab.assert_parity(day_api, day_sql, keys=["ts"], label="API == SQL")
assert len(day_api) == 288
```

Three paths, one answer. The API adds a layer (HTTP, JSON, id lookup), which is how other programs, and people
without database access, get the same data. It also caps the rows it returns, which is why we asked for a day, not
all 35,536 readings.

`ts` is a big number. Tomorrow turns it into a date.

## Try it

1. What was the coldest outside air reading?
2. Is AHU_1's supply fan status ever anything other than 0 or 1?

<details><summary>Answers</summary>

```python
COLDEST_SQL = """
SELECT ts, value FROM samples
WHERE timeseries_id = :uid
ORDER BY value ASC, ts LIMIT 1
"""
coldest_sql = lab.query(conn, COLDEST_SQL, {"uid": OAT})
coldest_pd = oat.sort_values(["value", "ts"]).head(1).reset_index(drop=True)
lab.assert_parity(coldest_pd, coldest_sql, label="coldest reading")
assert coldest_sql.iloc[0].tolist() == [1773740400, 17.8308]

DISTINCT_SQL = """
SELECT DISTINCT value FROM samples
WHERE timeseries_id = :uid
ORDER BY value
"""
distinct_sql = lab.query(conn, DISTINCT_SQL, {"uid": FAN})
distinct_pd = pd.DataFrame({"value": np.sort(series(FAN)["value"].unique())})
lab.assert_parity(distinct_pd, distinct_sql, label="fan status values")
assert distinct_sql.value.tolist() == [0.0, 1.0]
```

1. The coldest reading is 17.83 °F (it is stored as a decimal, `17.8308`) at `ts = 1773740400`.
2. Only 0 and 1. Status points are numbers in a historian, not booleans.

</details>

## Why it matters

Pasting UUIDs by hand doesn't scale. AHU_1 alone has 83 points, and a campus has tens of thousands. Day 6 puts
the point list in a table, and Unit 4 replaces it with a SPARQL query: "give me the duct static pressure sensor of
every AHU" → UUIDs. And because those UUIDs will come from a query, not from your own keyboard, passing them as
parameters is not just tidy. It is how you keep a bad id from becoming a bad query.
