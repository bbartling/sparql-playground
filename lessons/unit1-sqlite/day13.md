# Day 13 — Window functions: LAG, rolling averages, streaks

**Goal:** compare each row with its neighbours in time, without collapsing rows like `GROUP BY` does.

## Read

A **window function** computes a value for each row from a "window" of related rows. All rows stay in the result.

```
LAG(x)        OVER (PARTITION BY equipment_id ORDER BY ts)   -- x from the previous row
LEAD(x)       OVER (...)                                      -- x from the next row
ROW_NUMBER()  OVER (PARTITION BY ... ORDER BY ts)             -- 1, 2, 3 ... within each partition
AVG(x)        OVER (PARTITION BY ... ORDER BY ts
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) -- rolling mean of the last 12 rows (1 hour)
SUM(x)        OVER (PARTITION BY ... ORDER BY ts)             -- running total
```

- `PARTITION BY equipment_id` keeps AHU_1 and AHU_2 separate. Without it, AHU_2's first row would "follow" AHU_1's
  last.
- `ORDER BY ts` defines what "previous" means.

**Streaks (gaps and islands).** Fault rules need "this condition has been true for N rows in a row". The standard
trick takes three steps:

1. Mark where the value changes: `CASE WHEN x = LAG(x) OVER w THEN 0 ELSE 1 END AS new_streak`.
2. A running sum of those marks numbers each streak: `SUM(new_streak) OVER w AS streak_id`.
3. Number the rows inside each streak: `ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts)`.

A window function can't be used directly in `WHERE`, because windows are computed after filtering. Wrap the query in
a subquery, or a `WITH name AS (...)` common table expression (CTE), and filter outside.

## Run

```sql
-- Each reading next to the previous one
SELECT datetime(ts, 'unixepoch') AS t, duct_static,
       LAG(duct_static) OVER (PARTITION BY equipment_id ORDER BY ts) AS prev
FROM lab_history
WHERE equipment_id = 'AHU_1'
ORDER BY ts
LIMIT 3;
-- expect rows: 3
```

The first row's `prev` is NULL: nothing came before it.

```sql
-- Fan starts: off in the previous row, on in this one
WITH w AS (
  SELECT equipment_id, ts, fan_status,
         LAG(fan_status) OVER (PARTITION BY equipment_id ORDER BY ts) AS prev
  FROM lab_history
)
SELECT equipment_id, count(*) AS starts
FROM w
WHERE fan_status = 1 AND prev = 0
GROUP BY equipment_id
ORDER BY equipment_id;
-- expect: AHU_1 | 123
```

About one start a day for 123 days, as you'd expect for a scheduled AHU.

```sql
-- Longest continuous run of AHU_1's fan, in hours
WITH marks AS (
  SELECT ts, fan_status,
         CASE WHEN fan_status = LAG(fan_status) OVER (ORDER BY ts) THEN 0 ELSE 1 END AS new_streak
  FROM lab_history WHERE equipment_id = 'AHU_1'
), streaks AS (
  SELECT *, SUM(new_streak) OVER (ORDER BY ts) AS streak_id FROM marks
)
SELECT round(max(n) * 5 / 60.0, 1) AS longest_run_h
FROM (SELECT streak_id, count(*) AS n FROM streaks WHERE fan_status = 1 GROUP BY streak_id);
-- expect: 109.4
```

109 hours: the fan ran for more than four days straight. For an office AHU that's worth asking about (an override?
a schedule left in occupied?). It's the same question Day 9's unoccupied runtime raised.

## Try it

1. A 1-hour rolling average of AHU_2's duct static pressure. What's its maximum?
2. Count AHU_1 fan **stops** (on, then off). Should it equal the starts? Why might it differ by one?

<details><summary>Answers</summary>

```sql
SELECT round(max(r), 3) FROM (
  SELECT AVG(duct_static) OVER (PARTITION BY equipment_id ORDER BY ts
                                ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS r
  FROM lab_history WHERE equipment_id = 'AHU_2'
);
-- expect: 1.675
```

```sql
WITH w AS (
  SELECT fan_status, LAG(fan_status) OVER (ORDER BY ts) AS prev
  FROM lab_history WHERE equipment_id = 'AHU_1'
)
SELECT count(*) FROM w WHERE fan_status = 0 AND prev = 1;
-- expect: 122
```

122 stops against 123 starts. They can differ by one because the data can begin or end in the middle of a run (it
ends with the fan running).

</details>

## Why it matters

"Condition true for N consecutive rows" is how a fault rule ignores a one-sample blip and reports only persistent
problems. Tomorrow that's the confirmation step of a real rule.
