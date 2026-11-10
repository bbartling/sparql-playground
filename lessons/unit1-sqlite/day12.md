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
| previous / next row | `LAG(x) OVER (ORDER BY timestamp_utc)` / `LEAD(x) ...` | `df[x].shift(1)` / `.shift(-1)` |
| 15 minutes ahead | `LEAD(x, 3) OVER (...)` | `.shift(-3)` |
| change since last row | `x - LAG(x) OVER (...)` | `x - x.shift(1)` |
| 1-hour rolling mean | `AVG(x) OVER (... ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)` | `.rolling(12, min_periods=1).mean()` |
| fan start | `fan = 1 AND LAG(fan) OVER (...) = 0` | `(fan == 1) & (fan_prev == 0)` |
| first row has no previous | `LAG` is `NULL`, so the comparison is not true | `shift` gives `NaN`; the comparison is `False` |

The scripts look at AHU_1 only, so they need no `PARTITION BY`. With both AHUs stacked in one table you would add it
(and `df.groupby("equipment_id")[x].shift(1)` in pandas). Both are one pass over rows in time order, so O(n) (plus
the sort). The rolling mean can look like it costs 12 operations per row, but both engines
slide the window, adding the new row and dropping the oldest, so it stays O(n).

**Rows, not time.** `ROWS BETWEEN 11 PRECEDING` and `rolling(12)` count rows. They mean "one hour" only because the
data has exactly one row every five minutes. Day 15 checks that, and Day 18 handles data that has gaps.

**Units.** The CSV logs duct static in inches of water, so the scripts convert to pascals first
(`da_p_inwc * 249.08891`), and Day 12's numbers are in Pa. SI is what the fault rules use from here on.

## Run
```bash
uv run python lessons/course.py run 12
```

That runs [`day12_pandas.py`](day12_pandas.py), then [`day12_sql.py`](day12_sql.py). Both print:

```
AHU_1 fan cycling (duct static in Pa)
  fan starts: 123
  fan stops:  122
  highest 1-hour mean static (Pa): 427.7
  first fan start: 2026-03-16 09:00:00+00:00
  average static 15 min after a start (Pa): 294.68
First 3 fan events (start=1 or stop=1):
            timestamp_utc  fan_start  fan_stop
2026-03-16 09:00:00+00:00          1         0
2026-03-16 23:05:00+00:00          0         1
2026-03-17 08:35:00+00:00          1         0
```

(Times are UTC.) The fan starts about once a day and runs about 14 hours on a normal day. Fifteen minutes after a
start the static averages about 295 Pa, already close to where it settles: the fan comes up to pressure quickly. The
1-hour mean reacts slowly by design. That is why rules use the instantaneous value for "right now" and the mean for
"has this been going on".

Look at the rows around the first start yourself (`df.iloc[98:106]` in pandas): static sits at 5.6 Pa, then 137.5 Pa
for several rows in a row. The historian keeps the last value until a reading changes enough (change-of-value
logging), so repeated values are normal. Day 15 turns that into a quality check.

## Try it

1. Why does AHU_1 have one more fan start than fan stop?
2. In both scripts change `min_periods=1` / the frame so that the first 11 rows of each AHU are `NULL`/`NaN` instead
   (pandas: delete `min_periods=1`; SQL: wrap the average in `CASE WHEN row_number() ... >= 12`). What do you get?
   Which is the "right" first-row behaviour for a rule that must see a full hour?
3. A step of more than 100 Pa in one row: how would you find those rows with the columns the script already makes?

<details><summary>Answers</summary>

1. The last fan run is still going when the data ends (2026-07-17 09:55 UTC), so it has a start and no stop. The
   first row has no previous row, so it can be neither a start nor a stop.
2. The first 11 rows become `NaN` (pandas) or `NULL` (SQL) for `static_1h_mean_pa`. For a rule that needs a
   full hour of history, that is right: a mean of the 3 rows that exist is not an hour mean. For a plot, a partial
   mean is friendlier. Pick on purpose; the two tools default differently (SQL averages what exists, pandas
   returns `NaN`).
3. The scripts already make `static_prev_pa`. Add `df["static_step_pa"] = df["static_pa"] - df["static_prev_pa"]` and
   keep `df[df["static_step_pa"].abs() > 100]` in pandas; in SQL, `WHERE ABS(static_pa - static_prev_pa) > 100` on
   the windowed rows. That is 186 rows on AHU_1. Many are the fan starting (about +290 Pa) or stopping (about -290 Pa), and the
   jump lands one row after the status flips. Compare them with `fan_start` and `fan_stop`.

</details>

## Why it matters

Almost every rule is a window function in disguise. "Fan started less than 15 minutes ago" (suppress alarms while the
system settles), "static has been above setpoint for the last hour" (rolling mean), "the status changed" (LAG). Day
13 builds on `LAG` to count how long something stays the same, and Day 14's confirmation step uses the result.
