# Day 9 — CASE and conditional aggregation: run hours, percent occupied

**Goal:** compute several different counts in one pass using `CASE` inside aggregates, and the pandas version with
boolean masks and `np.where`.

## Read

`CASE` is SQL's if/else, and it returns a value:

```
CASE WHEN condition THEN a
     WHEN other     THEN b
     ELSE c END
```

Put it inside an aggregate and you get **conditional aggregation**: one scan, many answers.

```
sum(CASE WHEN fan = 1 AND occ = 0 THEN 1 ELSE 0 END)   -- readings: running while unoccupied
avg(CASE WHEN fan = 1 THEN static END)                 -- average static only while running (ELSE → NULL, ignored)
```

In SQLite a comparison is already 0 or 1, so `sum(fan = 1 AND occ = 0)` works too. `CASE` is clearer and portable to
other databases.

The `occupied` role is the AHU's occupancy command: 1 when the schedule says the building is in use. An AHU running
while **unoccupied** is one of the most common energy findings in retro-commissioning (RCx).

**The same ideas in pandas.** A condition on whole columns gives a **boolean mask**, and `True` counts as 1:

| SQL | pandas |
|---|---|
| `CASE WHEN c THEN 1 ELSE 0 END` | `c.astype(int)`, or `np.where(c, 1, 0)` |
| `sum(CASE WHEN c THEN 1 ELSE 0 END)` | `c.sum()` |
| `avg(CASE WHEN c THEN x END)` (NULL skipped) | `x[c].mean()`, or `x.where(c).mean()` (NaN skipped) |
| `CASE WHEN a THEN 'x' WHEN b THEN 'y' ELSE 'z' END` | `np.select([a, b], ["x", "y"], default="z")` |
| `GROUP BY equipment_id` | `.groupby("equipment_id")` |

There is one real difference in cost. SQL's `sum(CASE ...)` is evaluated **row by row inside the scan**, keeping
only running totals: O(n) time, O(1) extra memory, however many conditions you stack in one query. pandas
builds each mask as a full-length boolean array first (n bytes each), so many masks cost O(n) memory each. In
exchange, a mask is a tight compiled loop, far faster than writing the same `if` in Python for every row. Writing
the `CASE` as `df.apply(lambda row: ..., axis=1)` is the slow way, and we time it below.

Units: raw (°F, inH2O, percent 0–100); the status and occupancy points are 0/1.

## Run

```python
import numpy as np
import pandas as pd

import lab

conn = lab.connect()
lab.ensure_points(conn)
pts = lab.query(conn, "SELECT * FROM lab_point")
ROLE_COLS = pts[["timeseries_id", "equipment_id", "openfdd_role"]]
KEYS = ["equipment_id", "ts"]


def role_samples(roles):
    """Readings of just the points that carry one of these roles, labelled with equipment and role."""
    ids = pts.loc[pts.openfdd_role.isin(roles), "timeseries_id"].tolist()
    marks = ",".join("?" * len(ids))
    raw = lab.query(
        conn, f"SELECT timeseries_id, ts, value FROM samples WHERE timeseries_id IN ({marks})", ids
    )
    return raw.merge(ROLE_COLS, on="timeseries_id", validate="m:1").drop(columns="timeseries_id")


def wide_roles(roles):
    """One row per (equipment, ts), one column per role: the long -> wide pivot from Day 8."""
    w = role_samples(roles).pivot(index=KEYS, columns="openfdd_role", values="value").reset_index()
    w.columns.name = None
    return w
```

**Hours each AHU ran while unoccupied, and was off while occupied.** The SQL needs a join per point (Day 8). The
pandas version pivots once, then the three answers are three masks over the same columns.

```python
UNOCC_SQL = """
SELECT fp.equipment_id,
       sum(CASE WHEN f.value = 1 AND o.value = 0 THEN 1 ELSE 0 END) * 5 / 60.0 AS run_unocc_h,
       sum(CASE WHEN f.value = 0 AND o.value = 1 THEN 1 ELSE 0 END) * 5 / 60.0 AS off_occ_h,
       100.0 * avg(o.value)                                                    AS pct_occupied
FROM lab_point fp
CROSS JOIN lab_point op ON op.equipment_id = fp.equipment_id AND op.openfdd_role = 'occupied'
CROSS JOIN samples f    ON f.timeseries_id = fp.timeseries_id
CROSS JOIN samples o    ON o.timeseries_id = op.timeseries_id AND o.ts = f.ts
WHERE fp.openfdd_role = 'fan-status'
GROUP BY fp.equipment_id
ORDER BY fp.equipment_id
"""
unocc_sql = lab.query(conn, UNOCC_SQL)

w = wide_roles(["fan-status", "occupied"])
fan, occ = w["fan-status"], w["occupied"]
flags = pd.DataFrame(
    {
        "equipment_id": w["equipment_id"],
        "run_unocc": (fan == 1) & (occ == 0),  # boolean masks
        "off_occ": (fan == 0) & (occ == 1),
        "occ": occ,
    }
)
g = flags.groupby("equipment_id")
unocc_pd = pd.DataFrame(
    {
        "run_unocc_h": g["run_unocc"].sum() * 5 / 60,
        "off_occ_h": g["off_occ"].sum() * 5 / 60,
        "pct_occupied": 100.0 * g["occ"].mean(),
    }
).reset_index()
lab.assert_parity(unocc_pd, unocc_sql, label="unoccupied run hours")
print(unocc_sql.round(1).to_string(index=False))
r1 = unocc_sql.set_index("equipment_id").round(1)
assert r1.loc["AHU_1"].tolist() == [58.6, 2.2, 51.3]
assert r1.loc["AHU_2", "off_occ_h"] == 30.8
```

(`CROSS JOIN` here only pins the join order, as on Day 8.) AHU_1 ran about 59 hours while the schedule said
unoccupied. AHU_2 has the opposite pattern: 30.8 hours **off** while occupied, which is a comfort problem rather
than an energy one. Note that `avg(o.value)` is "fraction of readings where occupied = 1", the same trick as
`occ.mean()`.

**Bucket outside air into bands and count.** A multi-branch `CASE` is `np.select` (or `pd.cut` for numeric bins).
The `WHEN`s are tried in order, so `value < 60` only sees values that already failed `value < 40`.

```python
BANDS_SQL = """
SELECT CASE
         WHEN value < 40 THEN '1: below 40 F'
         WHEN value < 60 THEN '2: 40-60 F'
         WHEN value < 80 THEN '3: 60-80 F'
         ELSE '4: 80 F and up'
       END AS band,
       count(*) AS readings
FROM samples
WHERE timeseries_id = (SELECT timeseries_id FROM lab_point
                       WHERE equipment_id = 'AHU_1' AND openfdd_role = 'outside-air-temp')
GROUP BY band
ORDER BY band
"""
bands_sql = lab.query(conn, BANDS_SQL)

oat = role_samples(["outside-air-temp"]).query("equipment_id == 'AHU_1'")["value"]
assert oat.notna().all()  # a NULL would fall into ELSE in SQL, and into `default` in np.select
labels = ["1: below 40 F", "2: 40-60 F", "3: 60-80 F"]
band = pd.Series(
    np.select([oat < 40, oat < 60, oat < 80], labels, default="4: 80 F and up"), name="band"
)
bands_pd = band.value_counts().rename("readings").rename_axis("band").reset_index()
lab.assert_parity(bands_pd, bands_sql, label="outside air bands")
print(bands_sql.to_string(index=False))
assert len(bands_sql) == 4

# the numeric-bin shortcut gives the same counts
cut = pd.cut(oat, [-np.inf, 40, 60, 80, np.inf], right=False, labels=labels + ["4: 80 F and up"])
assert cut.value_counts().sort_index().tolist() == bands_sql["readings"].tolist()
```

**Cost of the mask vs the Python `if`.** The same "running while unoccupied" flag, three ways, on the 142,144
fan and occupancy rows:

```python
def mask_way():
    return ((fan == 1) & (occ == 0)).sum()


def where_way():
    return np.where((fan == 1) & (occ == 0), 1, 0).sum()


def apply_way():
    return w.apply(lambda r: 1 if r["fan-status"] == 1 and r["occupied"] == 0 else 0, axis=1).sum()


t_mask, t_where, t_apply = (lab.best_time(f) for f in (mask_way, where_way, apply_way))
print(
    f"mask {t_mask * 1e3:7.2f} ms | np.where {t_where * 1e3:7.2f} ms | row-by-row apply {t_apply * 1e3:8.1f} ms"
)
assert mask_way() == where_way() == apply_way() == round(unocc_pd.run_unocc_h.sum() * 60 / 5)
assert t_apply > 10 * t_mask
```

All three are O(n), but the Python-level loop pays interpreter overhead per row: 100× or more. Vectorized
masks run in compiled code over the whole column. SQL's `CASE` runs in compiled code too, inside the scan.

## Try it

Solve the week 1 challenge, now with `lab_point` and `CASE`: for each month, AHU_1's average outside air temperature,
fan run hours, and readings with duct static above 1.5.

<details><summary>Answer</summary>

```python
MONTHLY_SQL = """
SELECT strftime('%Y-%m', s.ts, 'unixepoch') AS month,
       avg(CASE WHEN p.openfdd_role = 'outside-air-temp' THEN s.value END)             AS avg_oat,
       sum(CASE WHEN p.openfdd_role = 'fan-status' THEN s.value ELSE 0 END) * 5 / 60.0 AS run_h,
       sum(CASE WHEN p.openfdd_role = 'duct-static-pressure' AND s.value > 1.5 THEN 1 ELSE 0 END) AS high_static
FROM samples s
JOIN lab_point p ON p.timeseries_id = s.timeseries_id
WHERE p.equipment_id = 'AHU_1'
  AND p.openfdd_role IN ('outside-air-temp', 'fan-status', 'duct-static-pressure')
GROUP BY month
ORDER BY month
"""
monthly_sql = lab.query(conn, MONTHLY_SQL)

m = wide_roles(["outside-air-temp", "fan-status", "duct-static-pressure"])
m = m[m.equipment_id == "AHU_1"].assign(
    month=lambda d: pd.to_datetime(d["ts"], unit="s").dt.strftime("%Y-%m")
)
m["high"] = m["duct-static-pressure"] > 1.5
gm = m.groupby("month")
monthly_pd = pd.DataFrame(
    {
        "avg_oat": gm["outside-air-temp"].mean(),
        "run_h": gm["fan-status"].sum() * 5 / 60,
        "high_static": gm["high"].sum(),
    }
).reset_index()
lab.assert_parity(monthly_pd, monthly_sql, label="AHU_1 monthly summary")
print(monthly_sql.round(1).to_string(index=False))
assert round(monthly_sql.set_index("month").avg_oat["2026-03"], 1) == 41.5
```

One scan, three answers. The `CASE` picks which rows feed each column. In week 1 this took three queries, or a
self-join. SQL keeps the data long (one row per reading, every role mixed together) and uses `CASE` to pick. pandas
pivots to wide first, so each role is its own column. Same result, opposite shape. Day 11 stores the wide shape.

</details>

## Why it matters

A fault rule is a `CASE`: *when* the fan runs at full speed *and* static is below setpoint *then* 1 *else* 0. In
pandas it's a mask. Sum it and you have fault hours. Day 14 builds exactly that, both ways, with parity.
