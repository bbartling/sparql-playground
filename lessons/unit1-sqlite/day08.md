# Day 8 — Self-joins: static pressure *while the fan is running*

**Goal:** line up two different points at the same timestamp, and filter one by the other, in SQL and in pandas.

## Read

In long format, the fan status and the duct static pressure at 10:05 are **two different rows** of `samples`. To ask
"what was static pressure while the fan ran?", you need them side by side in one row. That takes a **self-join**:
join `samples` to itself, once for each point, matching on the same `ts`.

```
fan status reading  f   ─┐
                         ├─ same ts, same AHU ─▶ one row: (ts, fan status, static)
static reading      d   ─┘
```

Each copy of `samples` needs its own `lab_point` copy to pick the role:

```
FROM lab_point fp JOIN samples f  ON f.timeseries_id = fp.timeseries_id            -- fan status readings
JOIN lab_point dp ON dp.equipment_id = fp.equipment_id
                 AND dp.openfdd_role = 'duct-static-pressure'                      -- same AHU's static point
JOIN samples d    ON d.timeseries_id = dp.timeseries_id AND d.ts = f.ts            -- its reading at the same time
WHERE fp.openfdd_role = 'fan-status'
```

Matching on `ts` works because this historian logs every point on the same 5-minute grid. If two points were logged
at different times, you'd first round them onto a common grid (Day 10).

**The same thing in pandas.** There are two natural ways:

| Idea | SQL | pandas |
|---|---|---|
| one frame per role, join them | `JOIN samples d ON d.ts = f.ts AND ...` | `f.merge(d, on=["equipment_id", "ts"])` |
| reshape long → wide once | (Day 11: `MAX(CASE WHEN role = ...)`) | `long.pivot(index=[...], columns="openfdd_role", values="value")` |
| filter by the other point | `WHERE f.value = 1` | `m[m.fan == 1]` |

**Join algorithms, again.** SQLite runs the self-join as a nested loop. Its outer loop is the 71,072 fan readings.
For each one it seeks the static reading and the setpoint reading at the same `ts` through the
`PRIMARY KEY (timeseries_id, ts)` of `samples`. The key is *both* columns, so each seek lands on exactly one row
(O(log n)), and the self-join cannot multiply rows. pandas does each `merge` as a hash join on
`(equipment_id, ts)`: O(n + m) per merge, with a new DataFrame after each one. `pivot` does the reshaping in one pass
and raises an error if any `(equipment_id, ts)` pair appears twice, which is the same safety net as the primary key.

`validate="1:1"` on a merge is the pandas version of that guarantee: if either side had duplicate keys the join
would multiply rows, and `validate` raises instead.

Units: raw (°F, inH2O, percent 0–100). Fan status is 0/1.

## Run

```python
import pandas as pd

import lab

conn = lab.connect()
lab.ensure_points(conn)
pts = lab.query(conn, "SELECT * FROM lab_point")
ROLE_COLS = pts[["timeseries_id", "equipment_id", "openfdd_role"]]


def role_samples(roles):
    """Readings of just the points that carry one of these roles, labelled with equipment and role."""
    ids = pts.loc[pts.openfdd_role.isin(roles), "timeseries_id"].tolist()
    marks = ",".join("?" * len(ids))
    raw = lab.query(
        conn, f"SELECT timeseries_id, ts, value FROM samples WHERE timeseries_id IN ({marks})", ids
    )
    return raw.merge(ROLE_COLS, on="timeseries_id", validate="m:1").drop(columns="timeseries_id")
```

**Duct static vs setpoint, only while the supply fan runs.**

```python
RUNNING_SQL = """
SELECT fp.equipment_id,
       count(*)       AS running_readings,
       avg(d.value)   AS avg_static,
       avg(sp.value)  AS avg_setpoint
FROM lab_point fp
JOIN samples f    ON f.timeseries_id = fp.timeseries_id
JOIN lab_point dp ON dp.equipment_id = fp.equipment_id AND dp.openfdd_role = 'duct-static-pressure'
JOIN samples d    ON d.timeseries_id = dp.timeseries_id AND d.ts = f.ts
JOIN lab_point spp ON spp.equipment_id = fp.equipment_id AND spp.openfdd_role = 'duct-static-pressure-sp'
JOIN samples sp   ON sp.timeseries_id = spp.timeseries_id AND sp.ts = f.ts
WHERE fp.openfdd_role = 'fan-status' AND f.value = 1
GROUP BY fp.equipment_id
ORDER BY fp.equipment_id
"""
running_sql = lab.query(conn, RUNNING_SQL)
print(running_sql.round(3).to_string(index=False))
```

In pandas, take each role as its own frame and merge on equipment and timestamp:

```python
long = role_samples(["fan-status", "duct-static-pressure", "duct-static-pressure-sp"])


def one(role, name):
    return long.loc[long.openfdd_role == role, ["equipment_id", "ts", "value"]].rename(
        columns={"value": name}
    )


KEYS = ["equipment_id", "ts"]
merged = (
    one("fan-status", "fan")
    .merge(one("duct-static-pressure", "static"), on=KEYS, validate="1:1")
    .merge(one("duct-static-pressure-sp", "setpoint"), on=KEYS, validate="1:1")
)
assert len(merged) == len(
    one("fan-status", "fan")
)  # a clean join keeps every fan row: no loss, no explosion

running = merged[merged.fan == 1]
running_pd = (
    running.groupby("equipment_id")
    .agg(
        running_readings=("ts", "size"),
        avg_static=("static", "mean"),
        avg_setpoint=("setpoint", "mean"),
    )
    .reset_index()
)
lab.assert_parity(running_pd, running_sql, label="static while running (merge)")

ahu1 = running_sql.set_index("equipment_id").loc["AHU_1"]
assert (ahu1.running_readings, round(ahu1.avg_static, 3), round(ahu1.avg_setpoint, 3)) == (
    18893,
    1.347,
    1.402,
)
```

Compare with Day 4. Over all hours AHU_1's static averaged 0.78 against a 1.37 setpoint, which looked like a fault.
While running it's 1.35 against 1.40: close, slightly low. AHU_2 runs at **1.40 against a 0.76 setpoint**, well
above. That's worth a look, and it's what a "duct static too high" rule would flag.

The second way is one `pivot`: reshape the long frame to wide once, then every later question is a column filter.

```python
wide = long.pivot(
    index=KEYS, columns="openfdd_role", values="value"
).reset_index()  # raises on duplicate keys
wide.columns.name = None
run_w = wide[wide["fan-status"] == 1]
running_wide = (
    run_w.groupby("equipment_id")
    .agg(
        running_readings=("ts", "size"),
        avg_static=("duct-static-pressure", "mean"),
        avg_setpoint=("duct-static-pressure-sp", "mean"),
    )
    .reset_index()
)
lab.assert_parity(running_wide, running_sql, label="static while running (pivot)")
```

Both pandas routes match the six-way SQL join. Look at how SQLite decided to run it:

```python
for step in conn.execute("EXPLAIN QUERY PLAN " + RUNNING_SQL).fetchall():
    print(step[-1])
```

Every `samples` step reads `SEARCH ... USING PRIMARY KEY`: an index seek, never a scan of `samples`. And time the
three approaches. The pandas times include loading the three roles from SQLite, so it's the whole job in each case.

```python
def merge_way():
    lg = role_samples(["fan-status", "duct-static-pressure", "duct-static-pressure-sp"])
    f = lg.loc[lg.openfdd_role == "fan-status", KEYS + ["value"]]
    d = lg.loc[lg.openfdd_role == "duct-static-pressure", KEYS + ["value"]]
    m = f.merge(d, on=KEYS, suffixes=("_fan", "_static"))
    return m[m.value_fan == 1].groupby("equipment_id")["value_static"].mean()


def pivot_way():
    lg = role_samples(["fan-status", "duct-static-pressure", "duct-static-pressure-sp"])
    w = lg.pivot(index=KEYS, columns="openfdd_role", values="value")
    return w[w["fan-status"] == 1].groupby("equipment_id")["duct-static-pressure"].mean()


t_sql = lab.best_time(lambda: conn.execute(RUNNING_SQL).fetchall())
t_merge, t_pivot = lab.best_time(merge_way), lab.best_time(pivot_way)
print(
    f"SQL 6-way join {t_sql:5.2f} s | pandas merges {t_merge:5.2f} s | pandas pivot {t_pivot:5.2f} s"
)
```

The shape of the cost matters more than who wins on this machine. SQL does roughly 71,000 × 2 index seeks and keeps
nothing in memory. The pandas versions load about 213,000 readings, then hash-join or reshape them in memory:
fast, but bounded by RAM. Day 11 does the pivot once, in SQL, and stores the wide table.

## Try it

1. Average discharge air temperature on AHU_1 while the fan runs vs while it's off. Why is the minimum while running
   0.0 °F?
2. Rewrite the first query for the fan **off** (`f.value = 0`). What's static pressure doing then?

<details><summary>Answers</summary>

```python
DAT_SQL = """
SELECT f.value AS fan_status, avg(d.value) AS avg_dat, min(d.value) AS min_dat
FROM lab_point fp
CROSS JOIN lab_point dp ON dp.equipment_id = fp.equipment_id AND dp.openfdd_role = 'discharge-air-temp'
CROSS JOIN samples f    ON f.timeseries_id = fp.timeseries_id
CROSS JOIN samples d    ON d.timeseries_id = dp.timeseries_id AND d.ts = f.ts
WHERE fp.openfdd_role = 'fan-status' AND fp.equipment_id = :equip
GROUP BY f.value ORDER BY f.value
"""
dat_sql = lab.query(conn, DAT_SQL, {"equip": "AHU_1"})

dat = role_samples(["fan-status", "discharge-air-temp"])
dat = dat[dat.equipment_id == "AHU_1"]
fan_dat = dat.loc[dat.openfdd_role == "fan-status", ["ts", "value"]].rename(
    columns={"value": "fan_status"}
)
dat_dat = dat.loc[dat.openfdd_role == "discharge-air-temp", ["ts", "value"]].rename(
    columns={"value": "dat"}
)
joined = fan_dat.merge(dat_dat, on="ts", validate="1:1")
dat_pd = joined.groupby("fan_status")["dat"].agg(avg_dat="mean", min_dat="min").reset_index()
lab.assert_parity(dat_pd, dat_sql, label="DAT by fan status")
print(dat_sql.round(1).to_string(index=False))
by_fan = dat_sql.set_index("fan_status")
assert (round(by_fan.avg_dat[1], 1), round(by_fan.min_dat[1], 1)) == (53.3, 0.0)
assert (round(by_fan.avg_dat[0], 1), round(by_fan.min_dat[0], 1)) == (70.1, 45.4)
```

About `CROSS JOIN`: in SQLite it means "join, in exactly this order". The planner is normally free to reorder
joins, and for this query it chose to build a temporary index on `d.ts` over four million rows. That takes minutes.
Written as above, the order is point, point, fan readings, then the discharge reading, so every `samples` step
is a primary-key seek and the query takes a fraction of a second. Join order is a big part of what an optimizer
decides, and when it guesses wrong, you can still pin it. Check with `EXPLAIN QUERY PLAN`.

Running averages 53.3 °F, off 70.1 °F (the air in the duct drifts toward room temperature). A real discharge
temperature of 0 °F is impossible. It's a dropout: the controller or historian wrote 0 when it had no value. Treat 0
in a temperature column as **missing**, not cold. Fault rules must not fire on it.

```python
OFF_SQL = RUNNING_SQL.replace("f.value = 1", "f.value = 0")
off_sql = lab.query(conn, OFF_SQL)

off_pd = (
    merged[merged.fan == 0]
    .groupby("equipment_id")
    .agg(
        running_readings=("ts", "size"),
        avg_static=("static", "mean"),
        avg_setpoint=("setpoint", "mean"),
    )
    .reset_index()
)
lab.assert_parity(off_pd, off_sql, label="static while fan off")
print(off_sql.round(3).to_string(index=False))
assert len(off_sql) == 2 and (off_sql.avg_static < 0.2).all()
```

Near zero, as it should be with the fan off. That's why the Day 4 averages were misleading. (The
`running_readings` column here really counts *off* readings.)

</details>

## Why it matters

Every fault rule is a condition on several points at the same time, gated by "is the equipment on?". Six joins to
line up three points is clumsy, though. On Day 11 you'll pivot the data once into a wide table (the `pivot` above)
and write rules as simple `WHERE` clauses.
