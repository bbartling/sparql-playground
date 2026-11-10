# Day 14 — Write a fault rule (FC1, duct static too low) twice, and check it against Open-FDD

**Goal:** turn an engineering rule into a pandas script *and* a SQL script, see that they give the same answer,
count fault hours, and compare with a production FDD engine's results.

## Read

**Fault detection and diagnostics (FDD)** runs rules over trend data to find equipment that isn't doing what it
should. Open-FDD's rules come from ASHRAE Guideline 36 and the NIST/PNNL APAR rules. **FC1** says:

> The supply fan is running (at or near full speed) but duct static pressure stays below its setpoint.

The fan is working as hard as it can and still can't make pressure. Likely causes: a broken belt, a failing VFD, a
blocked filter or coil, a leaky duct, or a setpoint too high for this system.

Every Open-FDD rule (`sql/fdd/postgres/rules/*.sql`, and its pandas twin in `open_fdd/rules`) has the same shape:

1. **Gate**: only judge rows where the equipment is on (`supply_fan_status = 1`). Off-hours aren't faults.
2. **Raw fault**: `CASE WHEN <condition> THEN 1 ELSE 0 END`, with a tolerance so noise doesn't trip it.
3. **Confirm**: count a row only once the raw fault has held for N consecutive rows (Day 13's streaks).
4. **Aggregate**: fault rows × 5 minutes = fault hours.

The math is **SI**, like Open-FDD (Day 6): the CSV's `da_p_inwc` is in inches of water, so both scripts convert to
pascals first. The tolerance is **25 Pa** (about 0.1 inH2O) and a fault is confirmed after **2 rows** (10 minutes).

The inputs are **hard-coded column names**: `supply_fan_status`, `da_p_inwc`, `da_p_setpoint_inwc`. The scripts run
on AHU_1; AHU_2's export happens to use the same names, so pointing them at AHU_2 is a one-word change. That's fine for one building. Week 5 shows where it
breaks, and how a data model replaces those names.

Open-FDD keeps every rule twice on purpose. SQL is what runs next to the data. pandas is the **oracle**: a second,
independent implementation, easy to step through in a notebook. Its parity tests run both on the same data and fail
if a single row differs. Today you write both halves and compare them.

How each step maps across:

| Step | `day14_sql.py` (per row, window functions) | `day14_pandas.py` (per column, vectorized) |
|---|---|---|
| 1. read AHU_1 | `FROM ahu_1` | `pd.read_csv(".../AHU_1/history_wide.csv", usecols=columns)` |
| 2. SI | `da_p_inwc * :pa_per_inh2o AS static_pa` | `df["da_p_inwc"] * PA_PER_INH2O` |
| 3. gate + raw fault | `supply_fan_status = 1 AND static_pa < setpoint_pa - :tolerance_pa` | `fan_on & too_low` |
| 4a. "value changed" | `raw_fault IS NOT LAG(raw_fault) OVER (ORDER BY timestamp_utc)` | `df["raw_fault"] != df["raw_fault"].shift()` |
| 4b. streak id | `SUM(new_streak) OVER (ORDER BY timestamp_utc)` | `df["new_streak"].cumsum()` |
| 4c. row within streak | `ROW_NUMBER() OVER (PARTITION BY streak_id ORDER BY timestamp_utc)` | `df.groupby("streak_id").cumcount() + 1` |
| 5. hours | `SUM(fault) * 5 / 60.0` | `df["fault"].sum() * 5 / 60` |

Both are O(n) once the rows are in time order. With several AHUs in one table, every window would add
`PARTITION BY equipment_id` (pandas: `groupby("equipment_id")`), so a streak never runs from one AHU into the next.
Day 20 and Day 25 do exactly that.

## Run
```bash
uv run python lessons/course.py run 14
```

That runs [`day14_pandas.py`](day14_pandas.py), then [`day14_sql.py`](day14_sql.py). Read them side by side: each
numbered comment in one has the same number in the other. Both print:

```
AHU_1, FC1 (duct static too low)
  raw fault hours:       120.0
  confirmed fault hours: 114.25
  confirmed episodes:    53
Open-FDD, FC1 on AHU_1
  episodes: 80
  hours:    484.1
Open-FDD episodes that contain one of our faults: 73 of 80
```

AHU_1 has about 114 confirmed fault hours in 53 episodes. Point the scripts at AHU_2 (`AHU_2` in the CSV paths,
`ahu_2` and `bld_50_AHU_2` in the SQL) and you get 1.5 hours in 5 episodes: essentially healthy for this rule (its
problem is the opposite, static *above* setpoint, as Day 8 showed).

AHU_1 has 1,371 confirmed rows = 114.25 h exactly, a tie at one decimal. SQLite's `round(114.25, 1)` rounds halves
away from zero (114.3), numpy and Python round halves to even (114.2). Round only for display, never before comparing
two results.

**Compare with Open-FDD.** Its results for this data ship next to the CSVs in `data/BUILDING_50/*/fdd_events.csv`
(the SQL side has them as the `fdd_events` table). It found **80 FC1 episodes, 484 hours** on AHU_1, against our 53
and 114. Different numbers don't mean either is wrong. Check whether the two engines are finding **the same events**:
how many of Open-FDD's episodes contain at least one of our confirmed fault rows? (Step 6.)

- SQL uses a **correlated `EXISTS`**: for each of the E events, ask "is there a confirmed fault row between this
  event's start and end?". Without an index each probe scans the `fc1` table; add one
  (`CREATE INDEX temp.fc1_time ON fc1 (timestamp_utc)`) and each probe is a B-tree range seek: O(E log N).
- pandas has no `EXISTS`, so the script loops over the 80 events and tests the fault times against each one
  (`inside.any()`): E passes over our F fault rows, O(E · F). That is instant for 80 events. With thousands you would
  sort the fault times once and binary-search them (`np.searchsorted`), O(E log F).

Both print **73 of 80**. Same problems, measured differently. Open-FDD's episode clock runs from first to last fault
sample, including stretches in between, and its event timestamps aren't on this 5-minute grid. It ran on its own
copy of the data with its own tuning. Totals depend on those choices; overlap tells you whether the rules agree on
**what** is wrong.

Real Open-FDD rules (`cmd1_fan_mismatch.sql` is a short one to read) add one more step: **forward sample-and-hold
with a gap limit** (`MAX_GAP_HOURS`). Building 50 has no gaps (every step is exactly 5 minutes), so counting rows
works here. Day 15 checks that, and Day 18 builds the gap-aware version.

## Try it

1. Change the tolerance from 25 Pa to 50 Pa (~0.2 inH2O) in both scripts (`TOLERANCE_PA` in pandas,
   `"tolerance_pa"` in SQL). How much do AHU_1's confirmed hours drop? Do the two scripts still agree?
2. Write the opposite rule, **duct static too high** (`duct_static > setpoint + 25 Pa` while running), in both
   scripts, and run it on AHU_2.

<details><summary>Answers</summary>

1. From 114.25 to 101.25 hours. Most of AHU_1's shortfall is more than 50 Pa: a real problem, not a
   marginal one.
2. Point the scripts at AHU_2 and flip one comparison in each: `df["static_pa"] > df["setpoint_pa"] + TOLERANCE_PA`
   and `static_pa > setpoint_pa + :tolerance_pa`. AHU_2 shows about 1,428 confirmed hours, nearly all of its 1,500
   run hours. The fan pushes far more pressure than its setpoint asks for, all the time: wasted fan energy, and possibly
   a reset sequence that isn't working. Open-FDD's version of this rule is `ahu_ducthi.sql`.

</details>

## Why it matters

Notice what the rule needed from outside the data: which column is "duct static" and which is "fan status" for each
AHU. Here those names are typed into the code. Change buildings, or meet an AHU whose export names a column
differently, and the rule breaks even though the physics hasn't changed. Week 5 fixes that with a semantic model: the
rule stays the same, and the model tells it where its inputs are. And because you have the rule twice, a change to
either script that alters a single row shows up as a mismatch (`tests/test_lesson_scripts.py` checks every day).
