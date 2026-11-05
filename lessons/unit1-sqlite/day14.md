# Day 14 — Write a fault rule (FC1, duct static too low) and check it against Open-FDD

**Goal:** turn an engineering rule into SQL, count fault hours, and compare with a production FDD engine's results.

## Read

**Fault detection and diagnostics (FDD)** runs rules over trend data to find equipment that isn't doing what it
should. Open-FDD's rules come from ASHRAE Guideline 36 and the NIST/PNNL APAR rules. **FC1** says:

> The supply fan is running (at or near full speed) but duct static pressure stays below its setpoint.

The fan is working as hard as it can and still can't make pressure. Likely causes: a broken belt, a failing VFD, a
blocked filter or coil, a leaky duct, or a setpoint too high for this system.

Every rule in `open-fdd/sql_rules/` follows the same shape (read `fc1_duct_static_low.sql` after this lesson):

1. **Gate**: only judge rows where the equipment is on (`fan_status = 1`). Off-hours aren't faults.
2. **Raw fault**: `CASE WHEN <condition> THEN 1 ELSE 0 END`, with a tolerance so noise doesn't trip it.
3. **Confirm**: count a row only once the raw fault has held for N consecutive rows (Day 13's streaks).
4. **Aggregate**: fault rows × 5 minutes = fault hours.

Our simplified FC1 uses `duct_static < duct_static_sp - 0.1` (inH2O), gates on `fan_status = 1`, and confirms after 2
rows (10 minutes). Open-FDD's real FC1 has more knobs (fan speed, mode-change delay, coverage); `sql/fdd/` documents
them.

## Run

```sql
DROP TABLE IF EXISTS lab_fc1;
CREATE TABLE lab_fc1 AS
WITH base AS (
  SELECT equipment_id, ts,
         CASE WHEN fan_status = 1 AND duct_static < duct_static_sp - 0.1 THEN 1 ELSE 0 END AS raw_fault
  FROM lab_history
), marks AS (
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts)
                 THEN 0 ELSE 1 END AS new_streak
  FROM base
), streaks AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id FROM marks
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts) AS streak_len FROM streaks
)
SELECT equipment_id, ts, raw_fault, streak_id,
       CASE WHEN raw_fault = 1 AND streak_len >= 2 THEN 1 ELSE 0 END AS fault
FROM ranked;

SELECT equipment_id,
       round(sum(raw_fault) * 5 / 60.0, 1) AS raw_fault_h,
       round(sum(fault) * 5 / 60.0, 1)     AS confirmed_fault_h,
       count(DISTINCT CASE WHEN fault = 1 THEN streak_id END) AS episodes
FROM lab_fc1
GROUP BY equipment_id
ORDER BY equipment_id;
-- expect: AHU_1 | 120 | 114.3 | 53
```

AHU_1 has about 114 confirmed fault hours in 53 episodes. AHU_2 has 1.5 hours: essentially healthy for this rule
(its problem is the opposite: static *above* setpoint, Day 8).

**Compare with Open-FDD.** Its results for this data ship in `data/BUILDING_50/*/fdd_events.csv`. Load them:

```bash
uv run python lessons/course.py load-events
```

That creates `lab_fdd_event` (one row per fault episode: `equipment_id`, `rule_name`, `start_ts`, `end_ts`,
`duration_min`).

```sql
SELECT rule_name, equipment_id, count(*) AS episodes, round(sum(duration_min) / 60, 1) AS hours
FROM lab_fdd_event
WHERE rule_name = 'fc1'
GROUP BY rule_name, equipment_id;
-- expect: fc1 | AHU_1 | 80 | 484.1
```

80 episodes and 484 hours, against our 53 and 114. Different numbers don't mean either is wrong yet. Check whether
the two engines are finding **the same events**:

```sql
-- How many of Open-FDD's FC1 episodes contain at least one of our confirmed fault rows?
SELECT count(*) AS openfdd_episodes,
       sum(EXISTS (SELECT 1 FROM lab_fc1 f
                   WHERE f.equipment_id = e.equipment_id AND f.fault = 1
                     AND f.ts BETWEEN e.start_ts AND e.end_ts)) AS also_found_by_us
FROM lab_fdd_event e
WHERE e.rule_name = 'fc1';
-- expect: 80 | 73
```

73 of 80 overlap: same problems, measured differently. Look at the episode lengths
(`max(duration_min)` is about 1,425 minutes, nearly a day). Open-FDD's episode clock runs from first to last fault
sample, including stretches in between, and its event timestamps aren't on this 5-minute grid. It ran on its own
copy of the data with its own tuning. Totals depend on those choices. Overlap tells you whether the rules agree on
**what** is wrong.

## Try it

1. Change the tolerance from 0.1 to 0.2 inH2O. How much do AHU_1's confirmed hours drop?
2. Write the opposite rule, **duct static too high** (`duct_static > duct_static_sp + 0.1` while running), and run
   it on AHU_2.

<details><summary>Answers</summary>

```sql
WITH base AS (
  SELECT equipment_id, ts,
         CASE WHEN fan_status = 1 AND duct_static < duct_static_sp - 0.2 THEN 1 ELSE 0 END AS raw_fault
  FROM lab_history WHERE equipment_id = 'AHU_1'
), marks AS (
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER (ORDER BY ts) THEN 0 ELSE 1 END AS new_streak FROM base
), streaks AS (
  SELECT *, SUM(new_streak) OVER (ORDER BY ts) AS streak_id FROM marks
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY streak_id ORDER BY ts) AS streak_len FROM streaks
)
SELECT round(sum(raw_fault = 1 AND streak_len >= 2) * 5 / 60.0, 1) FROM ranked;
-- expect: 101.3
```

From 114.3 to 101.3 hours. Most of AHU_1's shortfall is more than 0.2 inH2O: a real problem, not a marginal one.

```sql
WITH base AS (
  SELECT equipment_id, ts,
         CASE WHEN fan_status = 1 AND duct_static > duct_static_sp + 0.1 THEN 1 ELSE 0 END AS raw_fault
  FROM lab_history WHERE equipment_id = 'AHU_2'
), marks AS (
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER (ORDER BY ts) THEN 0 ELSE 1 END AS new_streak FROM base
), streaks AS (
  SELECT *, SUM(new_streak) OVER (ORDER BY ts) AS streak_id FROM marks
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY streak_id ORDER BY ts) AS streak_len FROM streaks
)
SELECT round(sum(raw_fault = 1 AND streak_len >= 2) * 5 / 60.0, 1) AS high_static_h FROM ranked;
-- expect: 1428.3
```

About 1,428 hours, nearly all of AHU_2's 1,500 run hours. The fan pushes far more pressure than its setpoint asks
for, all the time: wasted fan energy, and possibly a reset sequence that isn't working.
Open-FDD's version of this rule is `ahu_ducthi.sql`.

</details>

## Why it matters

Notice what the rule needed from outside the data: which column is "duct static" and which is "fan status" for each
AHU. Change buildings and only that mapping changes. That's the case for a semantic model. The rule stays the same,
and the model tells it where the inputs are.
