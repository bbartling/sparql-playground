# Day 14 — Write a fault rule (FC1, duct static too low) twice, and check it against Open-FDD

**Goal:** turn an engineering rule into SQL *and* into pandas, prove the two agree row for row, count fault hours,
and compare with a production FDD engine's results.

## Read

**Fault detection and diagnostics (FDD)** runs rules over trend data to find equipment that isn't doing what it
should. Open-FDD's rules come from ASHRAE Guideline 36 and the NIST/PNNL APAR rules. **FC1** says:

> The supply fan is running (at or near full speed) but duct static pressure stays below its setpoint.

The fan is working as hard as it can and still can't make pressure. Likely causes: a broken belt, a failing VFD, a
blocked filter or coil, a leaky duct, or a setpoint too high for this system.

Every Open-FDD rule (`sql/fdd/postgres/rules/*.sql`, and its pandas twin in `open_fdd/rules`) has the same shape:

1. **Gate**: only judge rows where the equipment is on (`fan_status = 1`). Off-hours aren't faults.
2. **Raw fault**: `CASE WHEN <condition> THEN 1 ELSE 0 END`, with a tolerance so noise doesn't trip it.
3. **Confirm**: count a row only once the raw fault has held for N consecutive rows (Day 13's streaks).
4. **Aggregate**: fault rows × 5 minutes = fault hours.

The math is **SI**, like Open-FDD: `lab_history` (Day 11) already holds pressure in pascals. The tolerance is
**25 Pa** (about 0.1 inH2O) and a fault is confirmed after **2 rows** (10 minutes).

Open-FDD keeps every rule twice on purpose. SQL is what runs next to the data. pandas is the **oracle**: a second,
independent implementation, easy to step through in a notebook. Its parity tests (`tests/parity` in Open-FDD) run
both on the same synthetic data and fail if a single row differs. You'll do exactly that here.

How each step maps across:

| Step | SQL (per row, inside window functions) | pandas (per column, vectorized) |
|---|---|---|
| gate + raw fault | `CASE WHEN fan_status = 1 AND ... THEN 1 ELSE 0 END` | boolean mask `(h.fan_status == 1) & (...)` |
| "value changed" | `raw = LAG(raw) OVER (PARTITION BY equipment_id ORDER BY ts)` | `raw.ne(raw.groupby(eq).shift())` |
| streak id | `SUM(new_streak) OVER (... ORDER BY ts)` | `new.groupby(eq).cumsum()` |
| row within streak | `ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ...)` | `groupby([eq, streak]).cumcount() + 1` |
| hours | `sum(fault) * 5 / 60.0` | `fault.sum() * 5 / 60` |

Both are O(n) once the rows are in `(equipment_id, ts)` order. SQLite gets that order from the
`lab_history (equipment_id, ts)` index; pandas from the `ORDER BY` in `lab.history()`.

## Run

```python
import numpy as np
import pandas as pd

import lab

conn = lab.connect()
lab.ensure_history(conn)  # lab_history: one row per AHU per 5 minutes, SI units (Day 11)

TOL_PA = 25.0  # tolerance below setpoint, pascals (~0.1 inH2O)
CONFIRM_ROWS = 2  # 2 rows x 5 min = 10 minutes before a fault counts
```

**The rule in SQL.** One string, four CTEs, one per step above. Named parameters (`:tol`, `:confirm`) keep numbers
out of the SQL text, as Open-FDD's `render_rule.py` does with its `{{...}}` placeholders.

```python
FC1_SQL = """
WITH base AS (
  SELECT equipment_id, ts,
         CASE WHEN fan_status = 1 AND duct_static < duct_static_sp - :tol THEN 1 ELSE 0 END AS raw_fault
  FROM lab_history
), marks AS (
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts)
                 THEN 0 ELSE 1 END AS new_streak
  FROM base
), streaks AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id FROM marks
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts) AS streak_len
  FROM streaks
)
SELECT equipment_id, ts, raw_fault, streak_id,
       CASE WHEN raw_fault = 1 AND streak_len >= :confirm THEN 1 ELSE 0 END AS fault
FROM ranked
ORDER BY equipment_id, ts
"""
params = {"tol": TOL_PA, "confirm": CONFIRM_ROWS}
fc1_sql = lab.query(conn, FC1_SQL, params)
print(fc1_sql.head())
```

**The same rule in pandas.** Each line is one column operation over all 71,072 rows; `groupby(eq)` plays the part
of `PARTITION BY equipment_id`.

```python
h = lab.history(conn)  # sorted by equipment_id, ts
eq = h["equipment_id"]

raw = ((h["fan_status"] == 1) & (h["duct_static"] < h["duct_static_sp"] - TOL_PA)).astype(int)
new_streak = raw.ne(raw.groupby(eq).shift()).astype(int)  # first row: shift() is NaN, so "new"
streak_id = new_streak.groupby(eq).cumsum()
streak_len = raw.groupby([eq, streak_id]).cumcount() + 1
fault = ((raw == 1) & (streak_len >= CONFIRM_ROWS)).astype(int)

fc1_pd = h[["equipment_id", "ts"]].assign(raw_fault=raw, streak_id=streak_id, fault=fault)
lab.assert_parity(fc1_pd, fc1_sql, keys=["equipment_id", "ts"], label="FC1 per row")
```

Every one of the 71,072 rows agrees: same raw flag, same streak number, same confirmed fault. Now the summary, again
both ways:

```python
lab.to_sqlite(fc1_sql, conn, "lab_fc1", index=["equipment_id", "ts"])  # Day 15 reads it
SUMMARY_SQL = """
SELECT equipment_id,
       sum(raw_fault) * 5 / 60.0 AS raw_fault_h,
       sum(fault) * 5 / 60.0     AS confirmed_fault_h,
       count(DISTINCT CASE WHEN fault = 1 THEN streak_id END) AS episodes
FROM lab_fc1
GROUP BY equipment_id
ORDER BY equipment_id
"""
summary_sql = lab.query(conn, SUMMARY_SQL)

hours = fc1_pd.groupby("equipment_id")[["raw_fault", "fault"]].sum().mul(5 / 60)
episodes = fc1_pd[fc1_pd.fault == 1].groupby("equipment_id")["streak_id"].nunique()
summary_pd = (
    hours.rename(columns={"raw_fault": "raw_fault_h", "fault": "confirmed_fault_h"})
    .assign(episodes=episodes)
    .fillna({"episodes": 0})
    .reset_index()
)
lab.assert_parity(summary_pd, summary_sql, label="FC1 summary")
print(summary_sql.round(2).to_string(index=False))
```

Notice the parity check compares the **unrounded** hours and the printout rounds. That's deliberate. AHU_1 has 1,371
confirmed rows = 114.25 h exactly, a tie at one decimal. SQLite's `round(114.25, 1)` rounds halves away from zero
(114.3); numpy and Python round halves to even (114.2). Round only for display, never before comparing.

```python
ahu1 = summary_sql.set_index("equipment_id").loc["AHU_1"]
print(ahu1.to_dict())
assert (ahu1.raw_fault_h, ahu1.confirmed_fault_h, ahu1.episodes) == (120.0, 114.25, 53)
```

AHU_1 has about 114 confirmed fault hours in 53 episodes. AHU_2 has 1.5 hours: essentially healthy for this rule
(its problem is the opposite: static *above* setpoint, Day 8).

**Compare with Open-FDD.** Its results for this data ship in `data/BUILDING_50/*/fdd_events.csv`.
`lab.ensure_events` loads them into `lab_fdd_event` (one row per fault episode: `equipment_id`, `rule_name`,
`start_ts`, `end_ts`, `duration_min`).

```python
lab.ensure_events(conn)
ofdd = lab.query(
    conn,
    """SELECT rule_name, equipment_id, count(*) AS episodes, round(sum(duration_min) / 60, 1) AS hours
       FROM lab_fdd_event WHERE rule_name = 'fc1' GROUP BY rule_name, equipment_id""",
)
print(ofdd.to_string(index=False))
assert ofdd.iloc[0].tolist() == ["fc1", "AHU_1", 80, 484.1]
```

80 episodes and 484 hours, against our 53 and 114. Different numbers don't mean either is wrong yet. Check whether
the two engines are finding **the same events**: how many of Open-FDD's episodes contain at least one of our
confirmed fault rows?

In SQL that's a **correlated `EXISTS`**: for each of the E events, probe our fault rows for that AHU and time range.
With the `(equipment_id, ts)` index each probe is a B-tree range seek, so the whole thing is O(E log N).

```python
OVERLAP_SQL = """
SELECT count(*) AS openfdd_episodes,
       sum(EXISTS (SELECT 1 FROM lab_fc1 f
                   WHERE f.equipment_id = e.equipment_id AND f.fault = 1
                     AND f.ts BETWEEN e.start_ts AND e.end_ts)) AS also_found_by_us
FROM lab_fdd_event e
WHERE e.rule_name = 'fc1'
"""
overlap_sql = lab.query(conn, OVERLAP_SQL)
```

pandas has no `EXISTS`. The fast equivalent is **binary search**: sort our fault timestamps once, then
`np.searchsorted` finds, for every event at once, how many fault rows fall before `start_ts` and how many at or
before `end_ts`. If those differ, the event contains one. Same O(E log F) as the index seek, written as array code.

```python
events = lab.query(
    conn, "SELECT equipment_id, start_ts, end_ts FROM lab_fdd_event WHERE rule_name = 'fc1'"
)
found = np.zeros(len(events), dtype=bool)
for equip, ev in events.groupby("equipment_id"):
    t = np.sort(fc1_pd.loc[(fc1_pd.equipment_id == equip) & (fc1_pd.fault == 1), "ts"].to_numpy())
    lo = np.searchsorted(t, ev["start_ts"].to_numpy(), side="left")
    hi = np.searchsorted(t, ev["end_ts"].to_numpy(), side="right")
    found[ev.index] = hi > lo
overlap_pd = pd.DataFrame(
    {"openfdd_episodes": [len(events)], "also_found_by_us": [int(found.sum())]}
)

lab.assert_parity(overlap_pd, overlap_sql, label="overlap with Open-FDD")
print(overlap_sql.to_string(index=False))
assert overlap_sql.iloc[0].tolist() == [80, 73]
```

73 of 80 overlap. Most of Open-FDD's episodes overlap ours: same problems, measured differently. Look at the episode lengths
(`max(duration_min)` is about 1,425 minutes, nearly a day). Open-FDD's episode clock runs from first to last fault
sample, including stretches in between, and its event timestamps aren't on this 5-minute grid. It ran on its own
copy of the data with its own tuning. Totals depend on those choices. Overlap tells you whether the rules agree on
**what** is wrong.

Real Open-FDD rules (`cmd1_fan_mismatch.sql` is a short one to read) add one more step you don't need here:
**forward sample-and-hold with a gap limit** (`MAX_GAP_HOURS`). Each row's state is held until the next sample, but a
gap longer than the limit counts as *unknown*: not fault time, and it breaks the streak. Building 50 has no gaps (every
step is exactly 300 s), so counting rows works. Day 18 builds the gap-aware version.

## Try it

1. Change the tolerance from 25 Pa to 50 Pa (~0.2 inH2O). How much do AHU_1's confirmed hours drop? Do it in SQL by
   changing only the parameter, and in pandas by changing only the tolerance, and check parity again.
2. Write the opposite rule, **duct static too high** (`duct_static > duct_static_sp + 25 Pa` while running), and run
   it on AHU_2 both ways.

<details><summary>Answers</summary>

A small function makes the pandas rule reusable for any raw condition; the SQL just gets a new parameter or a
flipped comparison.

```python
def confirmed(h, raw, n=CONFIRM_ROWS):
    """Per-row confirmed fault (0/1) from a raw 0/1 Series aligned with h (sorted by equipment, ts)."""
    eq = h["equipment_id"]
    streak = raw.ne(raw.groupby(eq).shift()).astype(int).groupby(eq).cumsum()
    return ((raw == 1) & (raw.groupby([eq, streak]).cumcount() + 1 >= n)).astype(int)


# 1. tolerance 50 Pa
sql_50 = lab.query(conn, FC1_SQL, {"tol": 50.0, "confirm": CONFIRM_ROWS})
raw_50 = ((h.fan_status == 1) & (h.duct_static < h.duct_static_sp - 50.0)).astype(int)
pd_50 = h[["equipment_id", "ts"]].assign(fault=confirmed(h, raw_50))
lab.assert_parity(pd_50, sql_50[["equipment_id", "ts", "fault"]], label="FC1 at 50 Pa")
hours_50 = round(sql_50.loc[sql_50.equipment_id == "AHU_1", "fault"].sum() * 5 / 60, 1)
print("AHU_1 confirmed FC1 hours at 50 Pa:", hours_50)

# 2. duct static too high, AHU_2
HIGH_SQL = FC1_SQL.replace(
    "duct_static < duct_static_sp - :tol", "duct_static > duct_static_sp + :tol"
)
high_sql = lab.query(conn, HIGH_SQL, params)
raw_hi = ((h.fan_status == 1) & (h.duct_static > h.duct_static_sp + TOL_PA)).astype(int)
high_pd = h[["equipment_id", "ts"]].assign(fault=confirmed(h, raw_hi))
lab.assert_parity(high_pd, high_sql[["equipment_id", "ts", "fault"]], label="static too high")
hi_h = round(high_sql.loc[high_sql.equipment_id == "AHU_2", "fault"].sum() * 5 / 60, 1)
print("AHU_2 confirmed high-static hours:", hi_h)
assert (hours_50, hi_h) == (101.2, 1428.3)
```

1. From about 114 to about 101 hours. Most of AHU_1's shortfall is more than 50 Pa: a real problem, not a marginal one.
2. About 1,428 hours, nearly all of AHU_2's 1,500 run hours. The fan pushes far more pressure than its setpoint asks
   for, all the time: wasted fan energy, and possibly a reset sequence that isn't working. Open-FDD's version of this
   rule is `ahu_ducthi.sql`.

</details>

## Why it matters

Notice what the rule needed from outside the data: which column is "duct static" and which is "fan status" for each
AHU. Change buildings and only that mapping changes. That's the case for a semantic model. The rule stays the same,
and the model tells it where the inputs are. And because you have the rule twice, a change to either one that alters
a single row fails the parity check before it ships.
