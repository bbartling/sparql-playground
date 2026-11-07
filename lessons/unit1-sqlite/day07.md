# Day 7 — JOIN: readings by role and equipment instead of UUID

**Goal:** combine `samples` and `lab_point` so you can ask for readings by meaning, in SQL and with a pandas merge.

## Read

A **JOIN** pairs rows from two tables that match a condition:

```
FROM samples AS s
JOIN lab_point AS p ON p.timeseries_id = s.timeseries_id
```

For every reading `s`, find the point row `p` with the same `timeseries_id`, and glue them into one wider row.
`s` and `p` are **aliases** (short names), so you can write `s.value` and `p.unit`.

- `JOIN` (inner join) keeps only rows that matched.
- `LEFT JOIN` keeps every row from the left table and fills the right side with NULLs when nothing matched. It's the
  tool for "which readings have no point?" style checks.

Once joined, you filter and group by point attributes: `WHERE p.openfdd_role = 'fan-status'`,
`GROUP BY p.equipment_id`. No UUIDs typed.

In pandas the same thing is `samples.merge(pts, on="timeseries_id", how="inner")`, and `how="left"` is the `LEFT JOIN`.

| | SQL | pandas |
|---|---|---|
| inner join | `JOIN lab_point p ON p.timeseries_id = s.timeseries_id` | `s.merge(p, on="timeseries_id")` |
| left join | `LEFT JOIN ...` | `s.merge(p, on="timeseries_id", how="left", indicator=True)` |
| filter after join | `WHERE p.openfdd_role = 'fan-status'` | `m[m.openfdd_role == "fan-status"]` |
| aggregate | `GROUP BY p.equipment_id` + `sum(...)` | `m.groupby("equipment_id")["value"].sum()` |
| "this must be one-to-one" | a `PRIMARY KEY` / `UNIQUE` constraint | `merge(..., validate="m:1")` |

**How the join is computed.** The two tools use different algorithms.

- SQLite does a **nested loop with an index lookup**. It picks an outer table, and for each of its rows it seeks the
  matching row in the inner table through an index. That costs O(n log m) for n outer rows and m inner rows, and
  needs almost no extra memory. This is why `samples` has `PRIMARY KEY (timeseries_id, ts)` and `lab_point` has
  `PRIMARY KEY (timeseries_id)`: those are the indexes the seeks use. It also lets SQLite pick the *cheaper* outer
  table. With `WHERE openfdd_role = 'fan-status'` it starts from the two fan-status points and seeks only their
  readings, never touching the other 4 million rows.
- pandas does a **hash join**. It builds a hash table of one side's keys and probes it with the other side's rows:
  O(n + m) time, but the data has to be in memory (a DataFrame for each side plus the result), and the merge happens
  on whatever you loaded. You do the "pick only the fan-status readings" step yourself, before the merge.

**Join explosion.** If the key isn't unique on the side you're looking up, every match makes its own output row, and
the result has *more* rows than the readings you started with. Sums and averages quietly turn wrong. Always check
that a join keeps the row count you expect (SQL: look at `count(*)`; pandas: `validate="m:1"`).

Units: weeks 1 and 2 use the raw values (°F, inH2O, percent 0–100).

## Run

```python
import pandas as pd

import lab

conn = lab.connect()
lab.ensure_points(conn)
pts = lab.query(conn, "SELECT * FROM lab_point")  # 118 rows: the lookup side of every join


def role_samples(roles):
    """Readings of just the points that carry one of these roles (not all 4.2 million rows), as a DataFrame."""
    ids = pts.loc[pts.openfdd_role.isin(roles), "timeseries_id"].tolist()
    marks = ",".join("?" * len(ids))
    return lab.query(
        conn, f"SELECT timeseries_id, ts, value FROM samples WHERE timeseries_id IN ({marks})", ids
    )
```

`role_samples` keeps pandas memory sensible: it asks SQLite for only the readings it needs, rather than loading
the whole table and filtering afterwards.

**Supply fan run hours for every AHU, no UUIDs typed.** Fan status is 1 when running, 0 when off, one reading per
5 minutes, so `sum(value) * 5 / 60` is hours.

```python
RUN_HOURS_SQL = """
SELECT p.equipment_id, sum(s.value) * 5 / 60.0 AS run_hours
FROM samples AS s
JOIN lab_point AS p ON p.timeseries_id = s.timeseries_id
WHERE p.openfdd_role = 'fan-status'
GROUP BY p.equipment_id
ORDER BY p.equipment_id
"""
run_sql = lab.query(conn, RUN_HOURS_SQL)

fan = role_samples(["fan-status"]).merge(
    pts[["timeseries_id", "equipment_id"]], on="timeseries_id", how="inner", validate="m:1"
)
run_pd = (fan.groupby("equipment_id")["value"].sum() * 5 / 60).rename("run_hours").reset_index()
lab.assert_parity(run_pd, run_sql, label="fan run hours")
print(run_sql.round(1).to_string(index=False))
assert round(run_sql.set_index("equipment_id").run_hours["AHU_1"], 1) == 1574.4
```

`validate="m:1"` says "many readings to one point". If two point rows ever shared a `timeseries_id` the merge would
raise instead of silently doubling the answer.

```python
AVG_SQL = """
SELECT p.equipment_id, p.openfdd_role, avg(s.value) AS avg_f
FROM samples AS s
JOIN lab_point AS p ON p.timeseries_id = s.timeseries_id
WHERE p.openfdd_role IN ('discharge-air-temp', 'return-air-temp')
GROUP BY p.equipment_id, p.openfdd_role
ORDER BY p.equipment_id, p.openfdd_role
"""
avg_sql = lab.query(conn, AVG_SQL)

temps = role_samples(["discharge-air-temp", "return-air-temp"]).merge(
    pts[["timeseries_id", "equipment_id", "openfdd_role"]], on="timeseries_id", validate="m:1"
)
avg_pd = (
    temps.groupby(["equipment_id", "openfdd_role"])["value"].mean().rename("avg_f").reset_index()
)
lab.assert_parity(avg_pd, avg_sql, label="average discharge vs return")
print(avg_sql.round(2).to_string(index=False))
row = avg_sql[(avg_sql.equipment_id == "AHU_1") & (avg_sql.openfdd_role == "discharge-air-temp")]
assert round(row.avg_f.iloc[0], 2) == 61.17
```

**Integrity check: any readings whose UUID is not in the point list?** In SQL, a `LEFT JOIN` and look for the NULLs.
In pandas, a left merge with `indicator=True` adds a column saying which side each row came from. Counting
readings means reading all 4.2 million, so first collapse them to one row per series (`GROUP BY` in SQL, before the
merge). Aggregating before joining is the cheap order, in both tools.

```python
ORPHANS_SQL = """
SELECT count(*) AS orphan_readings
FROM samples AS s
LEFT JOIN lab_point AS p ON p.timeseries_id = s.timeseries_id
WHERE p.timeseries_id IS NULL
"""
orphans_sql = lab.query(conn, ORPHANS_SQL)

per_series = lab.query(
    conn, "SELECT timeseries_id, count(*) AS n FROM samples GROUP BY timeseries_id"
)
checked = per_series.merge(pts[["timeseries_id"]], on="timeseries_id", how="left", indicator=True)
orphans_pd = pd.DataFrame(
    {"orphan_readings": [checked.loc[checked["_merge"] == "left_only", "n"].sum()]}
)
lab.assert_parity(orphans_pd, orphans_sql, label="orphan readings")
assert orphans_sql.iloc[0, 0] == 0
print(len(per_series), "series in samples,", len(pts), "points in lab_point")
```

Zero orphans. The repo's tests enforce the same invariant on the RDF model: every series in the store has a point,
and every point's series is in the store.

**Join explosion, on purpose.** Duplicate the two fan-status point rows, as a sloppy export might, and join again.
Row counts double, and so does every sum.

```python
fan_ids = pts.loc[pts.openfdd_role == "fan-status", ["timeseries_id", "equipment_id"]]
dup_pts = pd.concat(
    [pts[["timeseries_id", "equipment_id"]], fan_ids]
)  # 120 rows, 2 UUIDs appear twice

conn.execute("DROP TABLE IF EXISTS temp.dup_point")
conn.execute(
    "CREATE TEMP TABLE dup_point (timeseries_id TEXT, equipment_id TEXT)"
)  # no primary key
conn.executemany("INSERT INTO dup_point VALUES (?, ?)", dup_pts.values.tolist())

n_fan = len(fan)
n_sql = conn.execute(
    """SELECT count(*) FROM samples s JOIN dup_point p ON p.timeseries_id = s.timeseries_id
       WHERE s.timeseries_id IN (SELECT timeseries_id FROM lab_point WHERE openfdd_role = 'fan-status')"""
).fetchone()[0]
n_pd = len(role_samples(["fan-status"]).merge(dup_pts, on="timeseries_id"))
print(f"fan readings {n_fan} -> SQL join {n_sql} rows, pandas merge {n_pd} rows")
assert n_sql == n_pd == 2 * n_fan

try:
    role_samples(["fan-status"]).merge(dup_pts, on="timeseries_id", validate="m:1")
except pd.errors.MergeError as err:
    print("validate caught it:", str(err)[:70])
else:
    raise AssertionError("expected a MergeError")
```

**What the planner does.** `EXPLAIN QUERY PLAN` shows the nested loop SQLite chose for the run-hours query.

```python
plan = conn.execute("EXPLAIN QUERY PLAN " + RUN_HOURS_SQL).fetchall()
for step in plan:
    print(step[-1])
```

It scans `lab_point` (118 rows) first, because of the `WHERE` on role, then seeks `samples` through its primary key
for each matching point. Now time it against the pandas version. The pandas side is fast too once it has loaded
only fan readings, but the work of *choosing* what to load was done by hand.

```python
def pandas_run_hours():
    f = role_samples(["fan-status"]).merge(
        pts[["timeseries_id", "equipment_id"]], on="timeseries_id"
    )
    return f.groupby("equipment_id")["value"].sum()


t_sql = lab.best_time(lambda: conn.execute(RUN_HOURS_SQL).fetchall())
t_pd = lab.best_time(pandas_run_hours)
print(f"SQL join {t_sql * 1000:6.1f} ms | pandas load + merge {t_pd * 1000:6.1f} ms")
```

Neither wins by principle: both read the same 71,072 readings. The SQL cost model is O(n log m) with no big
intermediate result; the pandas one is O(n + m) but holds the readings and the merged copy in memory at once.
Join the *whole* `samples` table to `lab_point` in pandas and that's 4.2 million rows × several columns, many
hundreds of MB. Filter or aggregate first.

## Try it

1. Average duct static pressure **setpoint** per AHU. Are the two AHUs controlled to the same setpoint?
2. Count readings per `unit`. Which unit has the most data?

<details><summary>Answers</summary>

```python
SP_SQL = """
SELECT p.equipment_id, avg(s.value) AS avg_sp FROM samples s
JOIN lab_point p ON p.timeseries_id = s.timeseries_id
WHERE p.openfdd_role = 'duct-static-pressure-sp'
GROUP BY p.equipment_id ORDER BY p.equipment_id
"""
sp_sql = lab.query(conn, SP_SQL)
sp = role_samples(["duct-static-pressure-sp"]).merge(
    pts[["timeseries_id", "equipment_id"]], on="timeseries_id", validate="m:1"
)
sp_pd = sp.groupby("equipment_id")["value"].mean().rename("avg_sp").reset_index()
lab.assert_parity(sp_pd, sp_sql, label="average setpoint")
print(sp_sql.round(3).to_string(index=False))
assert round(sp_sql.set_index("equipment_id").avg_sp["AHU_1"], 3) == 1.366
```

AHU_1 averages 1.37 inH2O, AHU_2 0.78. Different setpoints, which is normal: each fan system is sized for its own
ductwork.

```python
UNIT_SQL = """
SELECT coalesce(p.unit, '(none)') AS unit, count(*) AS readings
FROM samples s JOIN lab_point p ON p.timeseries_id = s.timeseries_id
GROUP BY unit ORDER BY readings DESC
"""
unit_sql = lab.query(conn, UNIT_SQL)

# pandas: aggregate to one row per series first (35,536 readings each), then merge the 118-row table
unit_pd = (
    per_series.merge(pts[["timeseries_id", "unit"]], on="timeseries_id", validate="1:1")
    .assign(unit=lambda d: d["unit"].fillna("(none)"))
    .groupby("unit")["n"]
    .sum()
    .rename("readings")
    .reset_index()
)
lab.assert_parity(unit_pd, unit_sql, label="readings per unit")
print(unit_sql.to_string(index=False))
assert unit_sql.iloc[0].tolist() == ["DEG_F", 2380912]
```

`coalesce(x, y)` returns the first non-NULL argument; in pandas that's `fillna`. Here it labels the points that have
no unit (statuses, commands, alarms). The pandas version never merges 4.2 million readings: it merges 118 per-series
counts, which is the aggregate-before-join order.

</details>

## Why it matters

"Join readings to metadata, filter by metadata" is exactly what the API does. The difference is that its metadata
comes from a SPARQL query over the graph rather than a table. Week 12's client runs a SPARQL query, gets UUIDs back,
and reads samples. Same join, across two systems.
