# Day 15 — What production does differently (Timescale), and the UUID bridge to RDF

**Goal:** know which parts of Unit 1 carry over to a production historian, see where the RDF model picks up, and
run one fault rule end to end with the points found by the **model** rather than by a table you wrote.

## Read

### SQLite here, Timescale in production

Open-FDD's production stack keeps history in **PostgreSQL + TimescaleDB**. Everything you wrote this unit is plain
SQL and carries over. The differences are operational:

| Need | This course (SQLite) | Timescale |
|---|---|---|
| Store readings | `samples(timeseries_id, ts, value)`, key on series + time | a **hypertable**: same columns, split into time **chunks** automatically, so "last week" only touches a few chunks |
| Bucket by time | `strftime('%Y-%m', ts, 'unixepoch')`, `ts / 3600 * 3600` | `time_bucket('1 hour', time)` |
| Summary tables | `CREATE TABLE lab_hourly AS ...`, rebuilt by hand | **continuous aggregates**, refreshed incrementally as data arrives |
| Old data | keep everything | **compression** and **retention policies** per chunk |
| Many writers and readers | one writer at a time | a server with concurrent connections and roles |
| Wide `history` input | `lab_history` table | a view or temporary table built for one site, then the rule SQL runs as is |

The pandas side of "bucket by time" is the same idea again: `dt.strftime("%Y-%m")`, `dt.to_period("M")`, or
`resample`. The rules don't change. The Open-FDD SQL you read yesterday runs on Postgres with small dialect changes
(`sql/fdd/README.md` lists them). SQLite needs a few more, like sample standard deviation, which it lacks.

### The UUID bridge

All unit long you used `lab_point` to know that `52422584-…` is AHU_1's duct static pressure. The API doesn't use a
table for that. It uses the RDF model, `model/building_50.ttl`. Open it in a text editor and search for
`52422584-9894-50bd-9696-2fbb8b062518`:

```turtle
bldg:AHU_1_DA_P a bts:Entity ;
    rdfs:label "AHU1 DA-P" ;
    ref:hasExternalReference [ a ref:TimeseriesReference ;
            ref:hasTimeseriesId "52422584-9894-50bd-9696-2fbb8b062518" ;
            ref:storedAt bldg:timeseries_db ] ;
    bts:hasHaystackMarker "air", "discharge", "his", ...
```

Read it as statements, each one **subject, predicate, object**:

- `AHU_1_DA_P` has label "AHU1 DA-P".
- `AHU_1_DA_P` has an external reference, a TimeseriesReference with id `52422584-…`, stored at
  `bldg:timeseries_db`.
- `AHU_1_DA_P` has the Haystack markers `air`, `discharge`, …

And further down, `bldg:timeseries_db` describes the database you've been querying, including its schema:
`samples(timeseries_id TEXT, ts INTEGER epoch-s UTC, value REAL)`.

So the model is a graph of statements about things, and one kind of statement points into the time-series store by
UUID. Units 2–4 teach you to store, query and build graphs like this. Then the question "give me duct static and fan
status for every AHU" is answered by the model. The answer comes back as UUIDs, and those go into the SQL you already
know. The last section of this lesson does exactly that, through the repo's real API.

## Run

```python
import numpy as np
import pandas as pd

import lab

conn = lab.connect()
lab.ensure_history(conn)  # lab_history: one row per AHU per 5 minutes, SI units (Day 11)
h = lab.history(conn)  # sorted by equipment_id, ts
```

**FC1 again, compactly.** This lesson runs on its own, so rebuild Day 14's rule. The SQL is one template where only
the raw condition changes (`__RAW__`); the pandas side is one function. Both are the four steps from Day 14: gate and
raw fault, streak id, row within streak, confirm.

```python
RULE_SQL = """
WITH base AS (
  SELECT equipment_id, ts, CASE WHEN __RAW__ THEN 1 ELSE 0 END AS raw_fault FROM lab_history
), marks AS (
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts)
                 THEN 0 ELSE 1 END AS new_streak FROM base
), streaks AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id FROM marks
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts) AS streak_len FROM streaks
)
SELECT equipment_id, ts, raw_fault, streak_id,
       CASE WHEN raw_fault = 1 AND streak_len >= :confirm THEN 1 ELSE 0 END AS fault
FROM ranked ORDER BY equipment_id, ts
"""
FC1_SQL = RULE_SQL.replace("__RAW__", "fan_status = 1 AND duct_static < duct_static_sp - :tol")


def rule_pandas(h: pd.DataFrame, raw: pd.Series, confirm: int) -> pd.DataFrame:
    """Day 14's logic: raw 0/1 -> streak id -> row-in-streak -> confirmed fault. h is sorted by (equipment, ts)."""
    eq = h["equipment_id"]
    raw = raw.astype(int)
    streak_id = raw.ne(raw.groupby(eq).shift()).astype(int).groupby(eq).cumsum()
    streak_len = raw.groupby([eq, streak_id]).cumcount() + 1
    fault = ((raw == 1) & (streak_len >= confirm)).astype(int)
    return h[["equipment_id", "ts"]].assign(raw_fault=raw, streak_id=streak_id, fault=fault)


TOL_PA, CONFIRM_ROWS = 25.0, 2
fc1_sql = lab.query(conn, FC1_SQL, {"tol": TOL_PA, "confirm": CONFIRM_ROWS})
fc1_pd = rule_pandas(
    h, (h.fan_status == 1) & (h.duct_static < h.duct_static_sp - TOL_PA), CONFIRM_ROWS
)
lab.assert_parity(fc1_pd, fc1_sql, keys=["equipment_id", "ts"], label="FC1 per row")

lab.to_sqlite(fc1_sql, conn, "lab_fc1", index=["equipment_id", "ts"])
hours = fc1_sql.groupby("equipment_id").fault.sum() * 5 / 60
print(hours.to_dict())
assert hours["AHU_1"] == 114.25  # Day 14's number
```

**What the course added to the database.** The catalogue is itself a table, `sqlite_master`:

```python
lab_objects = lab.query(
    conn, "SELECT type, name FROM sqlite_master WHERE name LIKE 'lab\\_%' ESCAPE '\\' ORDER BY 1, 2"
)
print(lab_objects.to_string(index=False))
assert {"lab_point", "lab_history", "lab_fc1"} <= set(lab_objects.name)
```

**The one-line summary of Unit 1: confirmed FC1 hours per AHU per month,** in SQL with `strftime`, and in pandas
by turning epoch seconds into datetimes.

```python
MONTHLY_SQL = """
SELECT equipment_id, strftime('%Y-%m', ts, 'unixepoch') AS month,
       sum(fault) * 5 / 60.0 AS fc1_hours
FROM lab_fc1
GROUP BY equipment_id, month
ORDER BY equipment_id, month
"""
monthly_sql = lab.query(conn, MONTHLY_SQL)

when = pd.to_datetime(fc1_pd.ts, unit="s", utc=True)  # epoch seconds -> UTC datetimes
monthly_pd = (
    fc1_pd.assign(month=when.dt.strftime("%Y-%m"))  # the same format string as SQLite's strftime
    .groupby(["equipment_id", "month"])["fault"]
    .sum()
    .mul(5 / 60)
    .rename("fc1_hours")
    .reset_index()
)
lab.assert_parity(monthly_pd, monthly_sql, label="FC1 hours per month")

# the other idiom: a Period is "the month this timestamp falls in" (drop the timezone first)
period = when.dt.tz_localize(None).dt.to_period("M").astype(str)
assert (period == when.dt.strftime("%Y-%m")).all()

print(monthly_sql.pivot(index="month", columns="equipment_id", values="fc1_hours").round(1))
assert abs(monthly_sql[monthly_sql.equipment_id == "AHU_1"].fc1_hours.sum() - 114.25) < 1e-9
```

Notice `GROUP BY equipment_id, month` uses the alias from the `SELECT`: SQLite allows that, standard SQL doesn't.
In pandas you simply group on the column you just made. Both are O(n): one pass over the fault rows.

When you're done, `uv run python lessons/course.py reset` drops every `lab_*` object. The API's data is untouched.

### The model-driven run: FC1 through the real API

Everything above found "duct static" and "fan status" with `lab_point`, a table built from CSVs. Production doesn't.
Here is the same rule with every point found by **SPARQL against the RDF model**, and every series fetched through
the app's **HTTP API**, with no ids written in the code. `lab.Api` runs the repo's FastAPI app in-process (no server,
no network) on the same database. Pattern order matters to rdflib's simple engine: starting from the 118 points
that have a timeseries reference keeps every later join small (Day 6 explains why).

```python
FC1_POINTS_SPARQL = """
PREFIX bts: <https://example.org/openfdd/bldgts#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>
SELECT ?ahu ?role ?point ?timeseriesId WHERE {
  ?point ref:hasExternalReference ?ref .
  ?ref ref:hasTimeseriesId ?timeseriesId .
  ?point bts:hasHaystackTag ?roleTag .
  ?roleTag bts:tagName "ofddRole" ; bts:tagValue ?role .
  FILTER(?role IN ("fan-status", "duct-static-pressure", "duct-static-pressure-sp"))
  ?point bts:hasHaystackTag ?direct .
  ?direct bts:tagName "equipRef" ; bts:tagValue ?ahu .
}
ORDER BY ?ahu ?role
"""
with lab.Api() as api:
    found = api.sparql(FC1_POINTS_SPARQL)  # one row per (AHU, role): the point and its UUID
    found["equipment_id"] = found.ahu.str.rsplit("#", n=1).str[-1]  # IRI local name: AHU_1
    found["point_id"] = found.point.str.rsplit("#", n=1).str[-1]
    series = {
        (r.equipment_id, r.role): api.timeseries(r.point_id)  # GET /api/points/{id}/timeseries
        for r in found.itertuples()
    }
print(found[["equipment_id", "role", "point_id", "timeseriesId"]].to_string(index=False))
assert len(found) == 6  # 2 AHUs x 3 roles, found by the model
assert all(
    s.attrs["timeseries_id"] == r.timeseriesId for s, r in zip(series.values(), found.itertuples())
)
```

The model said which UUID is which role on which AHU, and the API returned each series from that point's name; the
`timeseries_id` the API reports back is the UUID the model gave us. Now the same steps as Day 11, in pandas: long,
pivot to wide, convert to SI (the history from the API is as logged: inH2O).

```python
long = pd.concat(
    [s.assign(equipment_id=eq_id, role=role) for (eq_id, role), s in series.items()],
    ignore_index=True,
)
wide = long.pivot(index=["equipment_id", "ts"], columns="role", values="value").reset_index()
api_h = (
    pd.DataFrame(
        {
            "equipment_id": wide.equipment_id,
            "ts": wide.ts,
            "fan_status": wide["fan-status"],
            "duct_static": lab.inh2o_to_pa(wide["duct-static-pressure"]),
            "duct_static_sp": lab.inh2o_to_pa(wide["duct-static-pressure-sp"]),
        }
    )
    .sort_values(["equipment_id", "ts"])
    .reset_index(drop=True)
)
print(len(api_h), "rows from the API")

raw_api = (api_h.fan_status == 1) & (api_h.duct_static < api_h.duct_static_sp - TOL_PA)
fc1_api = rule_pandas(api_h, raw_api, CONFIRM_ROWS)

lab.assert_parity(
    fc1_api, fc1_sql, keys=["equipment_id", "ts"], label="API -> pandas FC1 == SQL FC1"
)
lab.assert_parity(
    fc1_api, fc1_pd, keys=["equipment_id", "ts"], label="API -> pandas FC1 == sqlite -> pandas FC1"
)
```

Three routes to the same answer: SQL on the `lab_history` table, pandas on a DataFrame read from SQLite, and pandas
on series fetched over HTTP after the model located them. Every row agrees. That is what "model-driven" means: change
building and the SPARQL finds that building's points, and the rule doesn't change.

## Unit 1 challenge

Write a **discharge air temperature** rule for AHU_1 and AHU_2: while the fan runs, discharge air temperature (`sat`)
is more than **5 °F** away from its setpoint (`sat_sp`) for at least 30 minutes. The history is in SI, so convert the
threshold. Mind the trap from Day 11: 5 °F is a temperature **difference**, so it is 5 × 5/9 = 2.78 °C, **not**
`(5 - 32) * 5 / 9`. Then:

1. Exclude dropout rows (`sat` logged as 0 °F) and explain how many rows that removed.
2. Report fault hours per AHU per month, in SQL and in pandas, and check parity.
3. Pick the worst day and chart `sat`, `sat_sp` and `fan_status` for it. DB Browser's **Plot** tab works, or
   matplotlib (`uv run --with matplotlib python`).
4. Write two sentences an operator could act on.

Reuse `RULE_SQL` and `rule_pandas`: only the raw condition changes. Try it before opening the answer.

<details><summary>Answer</summary>

```python
DELTA_C = 5 * 5 / 9  # 5 degF of *difference* -> 2.78 degC
ZERO_F_IN_C = lab.f_to_c(0.0)  # dropout value in the SI history
CONFIRM_SAT = 6  # 6 rows x 5 min = 30 minutes
p = {"delta": DELTA_C, "z": ZERO_F_IN_C, "confirm": CONFIRM_SAT}

SAT_COND = "fan_status = 1 AND abs(sat - sat_sp) > :delta"
SAT_NODROP_COND = SAT_COND + " AND abs(sat - :z) > 1e-6"  # item 1: a dropout row is not a fault
sat_sql = lab.query(conn, RULE_SQL.replace("__RAW__", SAT_COND), p)
sat_nd_sql = lab.query(conn, RULE_SQL.replace("__RAW__", SAT_NODROP_COND), p)

off = (h.sat - h.sat_sp).abs() > DELTA_C
dropout = np.isclose(h.sat, ZERO_F_IN_C)
sat_pd = rule_pandas(h, (h.fan_status == 1) & off, CONFIRM_SAT)
sat_nd_pd = rule_pandas(h, (h.fan_status == 1) & off & ~dropout, CONFIRM_SAT)
lab.assert_parity(sat_pd, sat_sql, keys=["equipment_id", "ts"], label="SAT rule")
lab.assert_parity(
    sat_nd_pd, sat_nd_sql, keys=["equipment_id", "ts"], label="SAT rule, dropouts excluded"
)

# item 1: what did excluding dropouts change?
n_drop = int(((h.fan_status == 1) & dropout).sum())
print(
    "running rows with sat dropout:",
    n_drop,
    "| raw fault rows",
    int(sat_pd.raw_fault.sum()),
    "->",
    int(sat_nd_pd.raw_fault.sum()),
    "| confirmed rows",
    int(sat_pd.fault.sum()),
    "->",
    int(sat_nd_pd.fault.sum()),
)

# item 2: hours per AHU per month (the confirmed fault rows, dropouts excluded)
lab.to_sqlite(sat_nd_sql, conn, "lab_sat", index=["equipment_id", "ts"])
SAT_MONTHLY_SQL = MONTHLY_SQL.replace("lab_fc1", "lab_sat").replace("fc1_hours", "sat_hours")
sat_monthly_sql = lab.query(conn, SAT_MONTHLY_SQL)
when = pd.to_datetime(sat_nd_pd.ts, unit="s", utc=True)
sat_monthly_pd = (
    sat_nd_pd.assign(month=when.dt.strftime("%Y-%m"))
    .groupby(["equipment_id", "month"])["fault"]
    .sum()
    .mul(5 / 60)
    .rename("sat_hours")
    .reset_index()
)
lab.assert_parity(sat_monthly_pd, sat_monthly_sql, label="SAT hours per month")
print(sat_monthly_sql.pivot(index="month", columns="equipment_id", values="sat_hours").round(1))

# item 3: the worst day per AHU (hours of confirmed fault), both ways
DAILY_SQL = """
SELECT equipment_id, strftime('%Y-%m-%d', ts, 'unixepoch') AS day, sum(fault) * 5 / 60.0 AS sat_hours
FROM lab_sat GROUP BY equipment_id, day
"""
daily_sql = lab.query(conn, DAILY_SQL)
day = when.dt.strftime("%Y-%m-%d")
daily_pd = (
    sat_nd_pd.assign(day=day)
    .groupby(["equipment_id", "day"])["fault"]
    .sum()
    .mul(5 / 60)
    .rename("sat_hours")
    .reset_index()
)
lab.assert_parity(daily_pd, daily_sql, label="SAT hours per day")
worst = (
    daily_sql.sort_values(["sat_hours", "day"], ascending=[False, True])
    .groupby("equipment_id")
    .head(1)
)
print(worst.to_string(index=False))
assert n_drop == 14 and int(sat_pd.raw_fault.sum()) == int(sat_nd_pd.raw_fault.sum()) == 10007
w = worst.set_index("equipment_id")
assert w.loc["AHU_1", "day"] == "2026-05-18" and abs(w.loc["AHU_1", "sat_hours"] - 24.0) < 1e-9
assert sat_monthly_sql.groupby("equipment_id").sat_hours.sum().round(1).tolist() == [416.5, 298.0]
```

```python
# no-run
# item 3, the chart (needs matplotlib: uv run --with matplotlib python)
import matplotlib.pyplot as plt

d = worst.iloc[0]
one = h[
    (h.equipment_id == d.equipment_id)
    & (pd.to_datetime(h.ts, unit="s", utc=True).dt.strftime("%Y-%m-%d") == d.day)
]
t = pd.to_datetime(one.ts, unit="s", utc=True)
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(t, one.sat, label="sat (degC)")
ax.plot(t, one.sat_sp, label="sat_sp (degC)")
ax.fill_between(
    t, one.sat.min(), one.sat.max(), where=one.fan_status == 1, alpha=0.1, label="fan on"
)
ax.legend()
plt.show()
```

1. **Dropouts.** 14 running rows have `sat` at exactly 0 °F. Excluding them removes **0** raw fault rows (10,007
   before and after). Why? These are whole-row dropouts: `sat_sp`, `mat` and `rat` read 0 °F too, so
   `abs(sat - sat_sp)` is 0 and the rule never fired on them anyway. It's still the right habit: a rule comparing
   `sat` against a *different* reference (like `mat`) would have fired on every one of them. Note the unit trap
   again: a dropout is -17.78 °C in this history, never 0.
2. **Hours.** AHU_1 has about 417 confirmed hours and AHU_2 about 298, mostly in May and June. That's far more than
   FC1 found (114 h and 1.5 h).
3. **Worst day.** AHU_1 on 2026-05-18 is off its setpoint by more than 2.8 °C for all 24 hours; AHU_2's worst is
   2026-06-16 at 23.1 hours. Whole days like that are a stuck valve, damper or setpoint, not weather.
4. Something like: "AHU_1's discharge air stayed more than 2.8 °C from setpoint for the whole of 18 May and about
   417 hours since March. Check the cooling valve and the discharge sensor on AHU_1, and look at what changed in
   May." Be specific, give the date and a first thing to check.

Because Day 14's rule and this one share `RULE_SQL` and `rule_pandas`, adding a third rule is one new condition
string and one new boolean mask, with parity checking the pair.

</details>

Next: **Unit 2** builds a tiny triple store in Python, so the Turtle above stops being mysterious.
