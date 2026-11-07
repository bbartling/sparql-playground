# Day 11 — Long to wide, and into SI units: the `history` table every Open-FDD rule reads

**Goal:** pivot the readings into one row per AHU per timestamp, one column per role, in SQL *and* in pandas, and
convert everything to SI on the way.

## Read

Day 8 needed six joins to put three points side by side. Fault rules want *many* points side by side, so do the
pivot once:

```
long (samples + lab_point)                       wide (lab_history)
equipment ts     role          value             equipment ts     fan_status duct_static duct_static_sp ...
AHU_1     10:05  fan-status    1          ──▶     AHU_1     10:05  1          335.6       349.3
AHU_1     10:05  duct-static   1.31
AHU_1     10:05  duct-static-sp 1.40
```

The data is in **long** form (one row per reading) and rules want **wide** form (one row per moment). Each side has
its own idiom:

| Step | SQL | pandas |
|---|---|---|
| attach the role to each reading | `JOIN lab_point p ON p.timeseries_id = s.timeseries_id` | `samples.merge(points, on="timeseries_id")` |
| one row per (equipment, ts) | `GROUP BY p.equipment_id, s.ts` | `pivot(index=["equipment_id", "ts"], ...)` |
| one column per role | `MAX(CASE WHEN role = 'x' THEN value END) AS col` | `columns="openfdd_role"` |
| convert units | an expression inside the `MAX(CASE ...)` | arithmetic on the pivoted column |

The SQL trick is **conditional aggregation** again (Day 9): each group has exactly one reading per role, so `MAX`
simply picks it, and the other rows give NULL, which `MAX` ignores. pandas' `pivot` does the same job directly, and
it is stricter: if a group had *two* readings for one role it raises an error instead of quietly picking one
(`pivot_table(aggfunc="max")` is the forgiving version, the same as SQL's `MAX`).

Open-FDD's SQL rules (see `sql/fdd/postgres/rules/*.sql`) all read a relation called `history` with columns named
after roles: `fan_status`, `fan_cmd`, `duct_static`, `duct_static_sp`, `sat`, `mat`, `rat`, `oat`… The column names
below follow that **input contract**, so a rule written against it doesn't care which building it runs on.

### Why the history is SI

The historian logged what the building controller showed: °F, inches of water column, percent 0–100. In weeks 1–2
you explored the data as logged. **From today on, the data every rule reads is SI**: temperatures in °C, pressure
in pascals, commands and positions as fractions 0–1. Open-FDD's fault math is SI-only for three reasons:

- **One rule, any building.** A threshold like "25 Pa below setpoint" or "2.8 °C from setpoint" means the same thing
  on a US site logging °F and a European one logging °C, as long as the conversion happens once, at the door.
- **No unit logic inside rules.** A rule that guessed units would need an `if` on every comparison. Convert once in
  the `history` build and every rule stays a plain comparison.
- **Fractions compose.** A damper at `0.35` times a flow is a flow. A damper at `35` times a flow needs a `/100`
  somewhere, and sooner or later someone forgets it.

| Quantity | As logged | In `history` | Conversion |
|---|---|---|---|
| temperatures (`sat`, `sat_sp`, `mat`, `rat`, `oat`) | °F | °C | `(v - 32) * 5 / 9` |
| pressures (`duct_static`, `duct_static_sp`) | inH2O | Pa | `v * 249.08891` |
| commands and positions (`fan_cmd`, `oa_damper`, `clg_valve`) | % 0–100 | fraction 0–1 | `v / 100` |
| statuses (`fan_status`, `occupied`) | 0 / 1 | 0 / 1 | none |

Note for later: the `- 32` only applies to a **temperature**. A temperature *difference* of 5 °F is 5 × 5/9 =
2.78 °C, with no 32 in it. Day 15 needs that.

You'll make the history a **table**, not a view: the pivot reads 924k rows and takes a few seconds. As a table it's
built once and every rule after that is fast (the Day 10 summary-table idea).

## Run

```python
import numpy as np
import pandas as pd

import lab

conn = lab.connect()
lab.ensure_points(conn)  # lab_point: timeseries_id -> equipment, openfdd_role (Day 8)
```

**In SQL.** The `MAX(CASE ...)` is written out in full, with the conversion for each column inside it.

```python
HISTORY_SQL = """
SELECT p.equipment_id, s.ts,
  MAX(CASE WHEN p.openfdd_role = 'fan-status' THEN s.value END) AS fan_status,
  MAX(CASE WHEN p.openfdd_role = 'fan-cmd' THEN s.value / 100.0 END) AS fan_cmd,
  MAX(CASE WHEN p.openfdd_role = 'duct-static-pressure' THEN s.value * 249.08891 END) AS duct_static,
  MAX(CASE WHEN p.openfdd_role = 'duct-static-pressure-sp' THEN s.value * 249.08891 END) AS duct_static_sp,
  MAX(CASE WHEN p.openfdd_role = 'discharge-air-temp' THEN (s.value - 32.0) * 5.0 / 9.0 END) AS sat,
  MAX(CASE WHEN p.openfdd_role = 'discharge-air-temp-sp' THEN (s.value - 32.0) * 5.0 / 9.0 END) AS sat_sp,
  MAX(CASE WHEN p.openfdd_role = 'mixed-air-temp' THEN (s.value - 32.0) * 5.0 / 9.0 END) AS mat,
  MAX(CASE WHEN p.openfdd_role = 'return-air-temp' THEN (s.value - 32.0) * 5.0 / 9.0 END) AS rat,
  MAX(CASE WHEN p.openfdd_role = 'outside-air-temp' THEN (s.value - 32.0) * 5.0 / 9.0 END) AS oat,
  MAX(CASE WHEN p.openfdd_role = 'outside-air-damper' THEN s.value / 100.0 END) AS oa_damper,
  MAX(CASE WHEN p.openfdd_role = 'cooling-valve' THEN s.value / 100.0 END) AS clg_valve,
  MAX(CASE WHEN p.openfdd_role = 'occupied' THEN s.value END) AS occupied
FROM samples s
JOIN lab_point p ON p.timeseries_id = s.timeseries_id
WHERE p.openfdd_role IS NOT NULL
GROUP BY p.equipment_id, s.ts
"""
conn.execute("DROP TABLE IF EXISTS lab_history")
conn.execute("CREATE TABLE lab_history AS " + HISTORY_SQL)
conn.execute(
    "CREATE INDEX lab_history_eq_ts ON lab_history (equipment_id, ts)"
)  # Day 12 explains why
conn.commit()

history_sql = lab.query(conn, "SELECT * FROM lab_history ORDER BY equipment_id, ts")
print(len(history_sql), "rows")
assert len(history_sql) == 71072  # 2 AHUs x 35,536 timestamps
```

**In pandas.** Read the readings and the point list as two DataFrames, merge them, then pivot. Reading all 4.2
million samples takes a moment; the merge keeps only the 924k that have a role.

```python
samples = lab.query(conn, "SELECT timeseries_id, ts, value FROM samples")
points = lab.query(
    conn,
    "SELECT timeseries_id, equipment_id, openfdd_role FROM lab_point WHERE openfdd_role IS NOT NULL",
)
long = samples.merge(
    points, on="timeseries_id", how="inner"
)  # inner join: unmapped series drop out
print(len(samples), "samples ->", len(long), "readings with a role")

# one row per (equipment, ts), one column per role. pivot() raises if any cell had two readings.
wide = long.pivot(index=["equipment_id", "ts"], columns="openfdd_role", values="value")
print(wide.shape)
```

Now the SI conversion, one explicit line per column, using the converters in `lab`
(`f_to_c`, `inh2o_to_pa`) and plain arithmetic:

```python
history_pd = pd.DataFrame(index=wide.index)
history_pd["fan_status"] = wide["fan-status"]
history_pd["fan_cmd"] = wide["fan-cmd"] / 100.0
history_pd["duct_static"] = lab.inh2o_to_pa(wide["duct-static-pressure"])
history_pd["duct_static_sp"] = lab.inh2o_to_pa(wide["duct-static-pressure-sp"])
history_pd["sat"] = lab.f_to_c(wide["discharge-air-temp"])
history_pd["sat_sp"] = lab.f_to_c(wide["discharge-air-temp-sp"])
history_pd["mat"] = lab.f_to_c(wide["mixed-air-temp"])
history_pd["rat"] = lab.f_to_c(wide["return-air-temp"])
history_pd["oat"] = lab.f_to_c(wide["outside-air-temp"])
history_pd["oa_damper"] = wide["outside-air-damper"] / 100.0
history_pd["clg_valve"] = wide["cooling-valve"] / 100.0
history_pd["occupied"] = wide["occupied"]
history_pd = history_pd.reset_index().sort_values(["equipment_id", "ts"]).reset_index(drop=True)

lab.assert_parity(history_pd, history_sql, keys=["equipment_id", "ts"], label="wide history")
```

Every cell of the SQL table equals the pandas one (the `MAX(CASE ...)` and the `pivot` are two spellings of the
same reshape). One more check, so later days can trust the helper: `lab.ensure_history` builds this same table
from `lab.HISTORY_COLUMNS` (role plus conversion per column), and `lab.history_sql()` is the SQL it runs. Same data?

```python
helper = lab.query(conn, lab.history_sql())
lab.assert_parity(
    history_sql, helper, keys=["equipment_id", "ts"], label="lesson table == lab helper"
)
lab.ensure_history(conn)  # no-op now: lab_history exists, so later days reuse it
```

Look at the result, and at what SI did to the numbers. Day 8's six-join query is now one line of logic. The old
`1.347 inH2O` average duct static has become pascals:

```python
running = history_sql[history_sql.fan_status == 1]
by_ahu = running.groupby("equipment_id").agg(
    avg_static_pa=("duct_static", "mean"),
    avg_setpoint_pa=("duct_static_sp", "mean"),
    rows=("ts", "size"),
)
print(by_ahu.round(1))

AVG_SQL = """
SELECT equipment_id, avg(duct_static) AS avg_static_pa, avg(duct_static_sp) AS avg_setpoint_pa,
       count(*) AS rows
FROM lab_history
WHERE fan_status = 1
GROUP BY equipment_id
"""
lab.assert_parity(by_ahu, lab.query(conn, AVG_SQL), label="average static while running")
a1 = by_ahu.loc["AHU_1"]
assert (
    round(a1.avg_static_pa, 1) == 335.6
    and round(a1.avg_setpoint_pa, 1) == 349.3
    and a1.rows == 18893
)
```

AHU_1 holds 335.6 Pa while running against a 349.3 Pa setpoint (1.347 and 1.402 inH2O, the same numbers in other
units). That 14 Pa shortfall is invisible in a quick glance and is exactly what Day 14's rule goes looking for.

## Try it

1. Data quality: how many rows have the fan running but a discharge, mixed or return air temperature that was
   logged as exactly **0 °F** (a dead sensor)? Do it in SQL and in pandas.
2. What's missing from this pivot if a role has **no** point on some AHU? (Think about what the column would hold.)

<details><summary>Answers</summary>

1. The units changed under this question. In the raw database the dropout test was `sat = 0`. In `lab_history`
   a 0 °F reading is **-17.78 °C**, so `sat = 0` now means *0 °C* (32 °F), which is a perfectly normal temperature
   and matches nothing here. The test would silently find zero dropouts. The new test converts the dropout value
   too, and compares with a small tolerance because these are floating-point numbers:

```python
ZERO_F_IN_C = lab.f_to_c(0.0)  # -17.777...
DROPOUT_SQL = """
SELECT count(*) AS dropout_rows FROM lab_history
WHERE fan_status = 1
  AND (abs(sat - :z) < 1e-6 OR abs(mat - :z) < 1e-6 OR abs(rat - :z) < 1e-6)
"""
dropout_sql = lab.query(conn, DROPOUT_SQL, {"z": ZERO_F_IN_C})

r = history_pd[history_pd.fan_status == 1]
bad = (
    np.isclose(r.sat, ZERO_F_IN_C) | np.isclose(r.mat, ZERO_F_IN_C) | np.isclose(r.rat, ZERO_F_IN_C)
)
dropout_pd = pd.DataFrame({"dropout_rows": [int(bad.sum())]})

lab.assert_parity(dropout_pd, dropout_sql, label="0 F dropouts while running")
naive = ((r.sat == 0) | (r.mat == 0) | (r.rat == 0)).sum()  # the old test, now meaningless
print("dropouts:", dropout_pd.iloc[0, 0], "| old 'sat = 0' test finds:", naive)
assert dropout_pd.iloc[0, 0] == 14 and naive == 0
```

   Fourteen dropout rows while running: rare, but each one could trip a rule ("discharge air 50 °F below
   setpoint!"). Production rules filter or flag them. Better still, filter dropouts **before** converting, on the raw
   value, where "exactly 0" is unambiguous.

2. The column would be NULL (pandas: NaN) for that AHU. That's correct: "not measured" is not 0. A rule that needs
   that role must then **skip** the AHU and say so, rather than invent data. Open-FDD's contract calls that
   "skipped / not applicable". Both sides do it the same way. Pretend AHU_2 has no outside-air-temp point:

```python
SKIP = "NOT (p.equipment_id = 'AHU_2' AND p.openfdd_role = 'outside-air-temp')"
no_oat_sql = lab.history_sql().replace(
    "WHERE p.openfdd_role IS NOT NULL", "WHERE p.openfdd_role IS NOT NULL AND " + SKIP
)
sql_missing = lab.query(
    conn,
    f"SELECT equipment_id, count(*) AS rows, count(oat) AS oat_rows FROM ({no_oat_sql}) GROUP BY 1",
)

long2 = long[~((long.equipment_id == "AHU_2") & (long.openfdd_role == "outside-air-temp"))]
wide2 = long2.pivot(index=["equipment_id", "ts"], columns="openfdd_role", values="value")
wide2 = wide2.reindex(
    columns=wide.columns
)  # a missing role is a column of NaN, not a missing column
oat = wide2["outside-air-temp"]
pd_missing = oat.groupby("equipment_id").agg(rows="size", oat_rows="count").reset_index()

lab.assert_parity(pd_missing, sql_missing, label="role missing on one AHU")
print(sql_missing.to_string(index=False))
assert sql_missing.set_index("equipment_id").loc["AHU_2", "oat_rows"] == 0
```

   AHU_2 still has all 35,536 rows, but 0 outside-air-temperature values. `count(col)` and pandas' `count()` both
   ignore NULL/NaN, which is how a rule can tell "no data" from "zero".

</details>

## Why it matters

Which UUID becomes `duct_static` for which AHU is a **metadata** question. Here `lab_point.openfdd_role` answered
it. In Unit 4 a SPARQL query will: "for each AHU, the point with role duct-static-pressure and its
`ref:hasTimeseriesId`". That's the model-driven way to build this exact table for any building. And the unit
conversion belongs in that same build step: convert at the door, once, and nothing downstream has to ask.
