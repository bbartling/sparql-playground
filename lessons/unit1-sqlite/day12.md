# Day 12 — Window functions: look at neighbours and rolling windows (LAG, LEAD, rolling mean, fan starts)

**Goal:** compare each row with the rows around it, in SQL window functions and in pandas `shift` and `rolling`:
previous and next readings, a 1-hour rolling mean, and the moments the supply fan starts and stops.

## Read

An ordinary SQL query treats each row alone. FDD rules constantly need a row's **neighbours**: "did the status just
change?", "what was the reading five minutes ago?", "what is the average over the last hour?". A **window function**
computes a value for each row from a *window* of related rows, without collapsing them the way `GROUP BY` does. The
output has as many rows as the input.

```sql
LAG(duct_static_pa)  OVER (PARTITION BY equipment_id ORDER BY timestamp_utc)   -- the previous row's value
LEAD(duct_static_pa) OVER (PARTITION BY equipment_id ORDER BY timestamp_utc)   -- the next row's value
AVG(duct_static_pa)  OVER (PARTITION BY equipment_id ORDER BY timestamp_utc
                           ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)          -- this row and the 11 before it
```

`PARTITION BY equipment_id` restarts the window for each AHU, so AHU_2's first row never sees AHU_1's last row.
`ORDER BY timestamp_utc` is what makes "previous" mean *earlier*. `ROWS BETWEEN 11 PRECEDING AND CURRENT ROW` is a
12-row **frame**: 12 five-minute rows = one hour. The first rows of each AHU have fewer than 11 rows behind them.
SQL just averages what exists. pandas needs `min_periods=1` to do the same (the default would give NaN until it has
all 12).

| Idea | `day12_sql.py` | `day12_pandas.py` |
|---|---|---|
| previous / next row | `LAG(x) OVER w` / `LEAD(x) OVER w` | `groupby(eq)[x].shift(1)` / `.shift(-1)` |
| 15 minutes ahead | `LEAD(x, 3) OVER w` | `.shift(-3)` |
| change since last row | `x - LAG(x) OVER w` | `x - x.shift(1)` |
| 1-hour rolling mean | `AVG(x) OVER (... ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)` | `.rolling(12, min_periods=1).mean()` |
| fan start | `CASE WHEN fan = 1 AND LAG(fan) OVER w = 0 THEN 1 ELSE 0 END` | `(fan == 1) & (fan_prev == 0)` |
| first row has no previous | `LAG` is `NULL`; the `CASE` falls to `ELSE 0` | `shift` gives `NaN`; the comparison is `False` |

`groupby(eq)` plays the part of `PARTITION BY equipment_id` again. Both are one pass over rows in `(equipment, time)`
order, so O(n) (plus the sort). The rolling mean can look like it costs 12 operations per row, but both engines
slide the window, adding the new row and dropping the oldest, so it stays O(n).

**Rows, not time.** `ROWS BETWEEN 11 PRECEDING` and `rolling(12)` count rows. They mean "one hour" only because the
data has exactly one row every five minutes. Day 15 checks that, and Day 18 handles data that has gaps.

**Units.** The CSV logs duct static in inches of water, so the scripts convert to pascals first
(`da_p_inwc * 249.08891`), and Day 12's numbers are in Pa. SI is what the fault rules use from here on.

## Run

```bash
uv run python lessons/course.py run 12
```

That runs [`day12_pandas.py`](day12_pandas.py), then [`day12_sql.py`](day12_sql.py). Both end by printing the same
thing:

```
Fan cycling per AHU (duct static in Pa):
equipment_id  fan_starts  fan_stops  max_static_1h_mean_pa               first_start  avg_static_15min_after_start_pa
       AHU_1         123        122                  427.7 2026-03-16 09:00:00+00:00                           294.68
       AHU_2         129        128                  417.3 2026-03-16 09:00:00+00:00                           330.76

First 6 fan events on AHU_1 (start=1 / stop=1):
equipment_id             timestamp_utc  fan_start  fan_stop
       AHU_1 2026-03-16 09:00:00+00:00          1         0
       AHU_1 2026-03-16 23:05:00+00:00          0         1
       AHU_1 2026-03-17 08:35:00+00:00          1         0
       ...
```

(Times are UTC.) The fan starts about once a day and runs about 14 hours on a normal day. The "around the first
fan start" block at the end shows `static_prev_pa` lagging one row behind `duct_static_pa`, and the rolling mean climbing
slowly (6.0 to 16.9 to 27.8 to 38.8 Pa): a mean over an hour reacts slowly by design. That is why rules use
the instantaneous value for "right now" and the mean for "has this been going on".

Notice the data itself: static sits at 5.6 Pa, then 137.5 Pa for several rows in a row. The historian keeps the last
value until a reading changes enough (change-of-value logging), so repeated values are normal. Day 15 turns that
into a quality check.

## Try it

1. Why do both AHUs have one more fan start than fan stop?
2. In both scripts change `min_periods=1` / the frame so that the first 11 rows of each AHU are `NULL`/`NaN` instead
   (pandas: delete `min_periods=1`; SQL: wrap the average in `CASE WHEN row_number() ... >= 12`). What do you get?
   Which is the "right" first-row behaviour for a rule that must see a full hour?
3. A step of more than 100 Pa in one row: how would you find those rows with the columns the script already makes?

<details><summary>Answers</summary>

1. The last fan run is still going when the data ends (2026-07-17 09:55 UTC), so it has a start and no stop. The
   first row of each AHU has no previous row, so it can be neither a start nor a stop.
2. The first 11 rows per AHU become `NaN` (pandas) or `NULL` (SQL) for `static_1h_mean_pa`. For a rule that needs a
   full hour of history, that is right: a mean of the 3 rows that exist is not an hour mean. For a plot, a partial
   mean is friendlier. Pick on purpose; the two tools default differently (SQL averages what exists, pandas
   returns `NaN`).
3. The script already makes `static_step_pa = duct_static_pa - static_prev_pa`. Filter `abs(static_step_pa) > 100`:
   `windows[windows.static_step_pa.abs() > 100]` in pandas, `WHERE abs(static_step_pa) > 100` in SQL. That is 373
   rows (186 on AHU_1, 187 on AHU_2). Many are the fan starting (about +290 Pa) or stopping (about -290 Pa), and the
   jump lands one row after the status flips. Compare them with `fan_start` and `fan_stop`.

</details>

## Why it matters

Almost every rule is a window function in disguise. "Fan started less than 15 minutes ago" (suppress alarms while the
system settles), "static has been above setpoint for the last hour" (rolling mean), "the status changed" (LAG). Day
13 builds on `LAG` to count how long something stays the same, and Day 14's confirmation step uses the result.
