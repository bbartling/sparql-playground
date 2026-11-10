# Day 15 — Data quality before you trust a rule, and the Unit 1 challenge

**Goal:** check the data before judging the equipment: dropouts, a setpoint that reads zero, out-of-range values,
flatlined sensors, the time step, and coverage. Then finish Unit 1 by writing a discharge air temperature rule in
both pandas and SQL.

## Read

A fault rule can only be as good as its inputs. A rule that fires on a sensor dropout reports a broken *logger*, not
a broken *air handler*, and the person who gets the work order can't tell the difference. So before a rule, check
the data. Today's checks run on AHU_1, in both scripts, with the same answers. They are
[`day15_pandas.py`](day15_pandas.py) and [`day15_sql.py`](day15_sql.py). (Point them at AHU_2 to compare; its numbers
are quoted below too.)

| Check | What it looks for | pandas | SQL |
|---|---|---|---|
| 3. dropout | a temperature that reads exactly 0 °F | `(df["discharge_air_temp_f"] == 0) \| ...` | `discharge_air_temp_f = 0 OR ...` |
| 4. missing setpoint | setpoint reads 0 while the fan runs | `fan_on & (df["dat_reset_f"] == 0)` | `supply_fan_status = 1 AND dat_reset_f = 0` |
| 5. out of range | outside what a sensor can report | `(x < -40) \| (x > 60)` | `x NOT BETWEEN :temp_min_c AND :temp_max_c` |
| 6. flatline | an identical value for 1 h or more | Day 13's streaks: `(x != x.shift()).cumsum()` | Day 13's window steps |
| 7. time step | every row 300 s after the last | `pd.to_datetime(...).diff()` | `unixepoch(ts) - LAG(unixepoch(ts)) OVER w` |

All temperatures are converted to °C (`(°F − 32) × 5/9`) and static to Pa before the checks, like Day 14. The
dropout test is the one place where we look at the raw °F value on purpose.

### Dropouts, and the comparison trap

Seven rows on each AHU have the mixed, return and discharge temperatures all reading **exactly 0 °F**. A logger
writes 0 when it gets no reading; 0 °F is a perfectly valid number, so nothing flags it. After conversion that
0 °F is **-17.78 °C**, and that is where the trap is.

```python
df["discharge_air_temp_f"] == 0  # 7 rows: the raw value is exactly 0.0
df["dat_c"] == -17.78  # 0 rows: the converted value is -17.7777777...
(df["dat_c"] - ZERO_F_IN_C).abs() < 0.01  # 7 rows: compare with a tolerance
```

-17.78 is a rounded, printed number. The value in memory is -17.777777... and floating-point `==` against any
rounded constant never matches. Two safe ways: test the **raw value** before converting (exact zeros are stored
exactly), or compare converted values with a **tolerance**. Never `==` a float you computed. The scripts print both
the exact-match count (0) and the tolerance count (7), one under the other.

The seven rows form three episodes: one row on 31 March, five on 22 April (16:10 to 16:30 UTC), one on 15 June.
Notice that they are not caught by the **range check**: our sensor range is -40 to 60 °C, and -17.78 °C is
inside it.
A range check catches impossible values (a duct at 500 °C); a dropout is a *plausible wrong* value, which is
harder. Out-of-range is 0 rows here. That is a result too.

### A setpoint of zero, and flatlines

`dat_reset_f` is the discharge air temperature **setpoint**. While the fan runs it should sit between 50 and 71 °F.
It reads **0 °F** for 1,233 running rows on AHU_1 and 984 on AHU_2, mostly in June. Seven of those are the dropout
rows. The rest are the control system publishing no setpoint. A rule comparing the discharge temperature with a
setpoint of -17.78 °C would call the whole stretch a fault.

**Flatlines.** A working temperature sensor wiggles in its last digits. The same value for an hour or more while the
fan runs is suspicious. This is Day 13's streak trick on the sensor reading: streaks of an identical
`discharge_air_temp_f`, kept if the streak is at least 12 rows (1 hour) and the fan ran for all of it. That finds
66 episodes (1,333 rows) on AHU_1 and 48 (1,064 rows) on AHU_2, the longest 136 and 135 rows (11 hours).
Remember Day 12: the historian logs change-of-value, so a stable reading is *normally* repeated. Treat flatlines as
"look here", not as proof, and raise the threshold if it's too chatty (see Try it).

### The time step, and coverage

Every row should be exactly 300 s after the one before. The check takes the difference to the previous timestamp
and counts rows where it isn't 300: **0 gaps, max step 300 s** on both AHUs. That is why counting rows works as
counting time in Days 12 to 14 (`ROWS BETWEEN 11 PRECEDING` really is one hour). Real data usually has gaps. Day 18
builds the gap-aware version.

**Coverage per month** (Try it 3) compares the rows present with the rows expected from the first to the last
timestamp in the month: 100% for every month here. March and July are partial months (the export starts on
16 March and ends on 17 July), so compare coverage against the *span*, not against a calendar month.

## Run
```bash
uv run python lessons/course.py run 15
```

Both scripts print the same numbers (pandas shows `300.0` where SQL shows `300`):

```
AHU_1 data-quality checks
  dropout rows (a temperature reads 0 F): 7
  setpoint reads 0 while the fan runs:    1233
  discharge temp out of range:            0
  flatline rows (1 h+ the same value):    1333
  flatline episodes:                      66
  time steps that are not 300 s:          0
  longest time step (s):                  300.0
  dat_c == -17.78 matches:                0
  dat_c within 0.01 of -17.78 matches:    7
```

followed by the challenge answer below.

## Try it

1. Raise the flatline threshold from 12 rows to 36 (3 hours), in both scripts (`FLAT_ROWS` in pandas, `flat_rows` in
   SQL). How many episodes are left?
2. The `dropout` flag looks at three temperatures. Why is it safer to flag the *row* than to remove the one
   dropout sensor?
3. Coverage: for each month, count the rows present and the rows expected from the month's first to its last
   timestamp (`span_s / 300 + 1`, Day 3). What percentage is present?

<details><summary>Answers</summary>

1. Five episodes remain on AHU_1 (419 rows; AHU_2 also has five, 416 rows). Most hour-long flatlines are probably
   change-of-value repeats. The few stretches of 3 hours or more are the ones worth asking about.
2. In a dropout all three sensors fail at the same moment, which points at the controller or the network rather than
   one sensor. A rule that mixes several temperatures would otherwise compute with a mix of real and fake values.
   Flag the whole row and let each rule skip it.
3. 100% for every month. In pandas: `df.groupby("month")["time"].agg(["size", "min", "max"])` with
   `time = pd.to_datetime(df["timestamp_utc"])`, then `(max - min).dt.total_seconds() / 300 + 1`. In SQL: `GROUP BY
   strftime('%Y-%m', timestamp_utc)` with `COUNT(*)` and `(unixepoch(MAX(...)) - unixepoch(MIN(...))) / 300 + 1`.

</details>

## Unit 1 challenge: a discharge air temperature rule, in SI, with a quality gate

Write the rule in both scripts (it's already in both, as steps 8 and 9, so the parity test covers it; try writing it
yourself first):

> While the supply fan runs, the discharge air temperature is **more than 2.78 °C (5 °F) away from its setpoint**
> (`discharge_air_temp_f` vs `dat_reset_f`), and this holds for **30 minutes (6 rows)**.

Report **fault hours per month** (AHU_1; then AHU_2). Do it twice: once trusting every row, once skipping rows where the data
quality checks fail.

<details><summary>Answer</summary>

Same shape as Day 14: gate, raw fault, confirm, aggregate.

```python
error_c = (df["dat_c"] - df["dat_setpoint_c"]).abs()  # both converted: (F - 32) * 5 / 9
raw_ungated = fan_on & (error_c > TOLERANCE_C)
raw_gated = raw_ungated & ~df["dropout"] & ~df["setpoint_zero"]
# then Day 13's streak trick: fault = raw & (row_in_streak >= 6); hours = rows * 5 / 60
```

```sql
supply_fan_status = 1 AND ABS(dat_c - dat_setpoint_c) > :tolerance_c                       -- ungated
supply_fan_status = 1 AND ABS(dat_c - dat_setpoint_c) > :tolerance_c
  AND NOT dropout AND NOT setpoint_zero                                                    -- gated
-- LAG / SUM OVER / ROW_NUMBER as on Day 13, then SUM(fault) * 5 / 60.0 per month
```

The absolute value matters: the discharge temperature can be too high or too low. A *difference* of temperatures
converts with only the 5/9 factor (the 32 cancels), so 5 °F is 5 × 5/9 = 2.78 °C. The scripts convert each
temperature first and then subtract, which gives the same answer and keeps every column in °C.

Fault hours on AHU_1 (ungated / gated), as the scripts print them:

```
  month  ungated_fault_h  gated_fault_h
2026-03            22.25          22.25
2026-04            46.00          46.00
2026-05           113.50         113.50
2026-06           213.75         123.75
2026-07            21.00          11.33
  total, trusting every row (h): 416.5
  total, quality gate on (h):    316.83
```

AHU_2, with the scripts pointed at it: 298.00 h ungated, 218.25 h gated (June 174.75 -> 104.67).

Both AHUs miss their discharge setpoint for a good part of the time, most of all in June. The quality gate matters:
the missing setpoint adds about 100 hours on AHU_1 and 80 on AHU_2, roughly a quarter of the ungated totals, almost
all of it in June and July, because a setpoint of -17.78 °C is "wrong" by 30 °C whenever the fan is on. Those are
not faults in the air handler. March and April are unchanged: the 7 dropout rows are too few and too short to
reach the 6-row confirmation. Fixing the setpoint publisher is its own work order.

</details>

## Why it matters

The quality gate changed the answer by about a quarter. That's the point of the day: **read the data before you read
the rule's output**. Production FDD does the same checks on every run. The gap-aware sample-and-hold
(`MAX_GAP_HOURS`) comes on Day 18.

**What production does differently (Timescale).** Everything this unit used (CSV, SQLite) is one machine and a few
hundred thousand rows. Open-FDD's production stack keeps history in **PostgreSQL with the TimescaleDB extension**: the
same SQL (window functions, `CASE`, `GROUP BY` all carry over), but the table is split into time chunks, old chunks
compress, and queries for one series and one time range touch only their chunks. That is Day 11's index idea,
applied automatically. Hard-coded column names are the other thing that changes: Week 5 replaces
`discharge_air_temp_f` with a lookup in a building model, so one rule runs over many buildings and exports.
