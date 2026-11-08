# Day 13 — Streaks (gaps and islands): how long has this been true?

**Goal:** find runs of consecutive rows with the same value, using the three-step streak trick in SQL and its
`cumsum` twin in pandas. Use it to find the longest continuous fan run and to count "true for N rows in a row", the
confirmation step in every Open-FDD rule.

## Read

A lot of FDD questions are about **duration**, not single readings: "the fan has been on for 30 minutes", "static
has been low for an hour", "this sensor hasn't changed all night". A raw fault on one row is noise; a raw fault that
holds for N rows is a finding. Rows in a table don't know their neighbours, so we need a way to say "these
consecutive rows belong to one run". This is the classic *gaps and islands* problem.

The trick has three steps. Take the fan status as an example:

```
status        0 0 1 1 1 0 1 1
new_streak    1 0 1 0 0 1 1 0      1 where the value differs from the previous row (the first row is always 1)
streak_id     1 1 2 2 2 3 4 4      running total of new_streak: every row of a run shares one id
row in streak 1 2 1 2 3 1 1 2      counts 1, 2, 3 ... inside each run
```

Now a run is just a `GROUP BY streak_id`, and "true for N rows in a row" is `row in streak >= N`. Each step is cheap
and the whole thing is one pass over the rows, O(n) after sorting.

| Step | `day13_sql.py` (window functions) | `day13_pandas.py` (vectorized) |
|---|---|---|
| mark changes | `CASE WHEN x = LAG(x) OVER w THEN 0 ELSE 1 END` | `x.ne(x.groupby(eq).shift())` |
| streak id | `SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts)` | `new_streak.groupby(eq).cumsum()` |
| row in streak | `ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts)` | `x.groupby([eq, streak_id]).cumcount() + 1` |
| each run | `GROUP BY equipment_id, streak_id` | `groupby(["equipment_id", "run_id"]).agg(...)` |
| longest per AHU | rank with `ROW_NUMBER() OVER (PARTITION BY equipment_id ORDER BY rows DESC)`, keep 1 | `sort_values(...).groupby(eq).head(1)` |

Two details. On an AHU's first row `LAG` is `NULL`, so `x = LAG(x)` is `NULL`, not false, and the `CASE` takes the
`ELSE 1` branch: the first row starts a streak, as it should. And a *tie* for the longest run needs a rule, or two
runs of equal length make the answer unstable; both scripts break ties by the earlier start.

**A second route to "true for N rows in a row".** Instead of numbering streaks, slide a window of N rows over the 0/1
raw flag and ask whether all N are 1: `SUM(raw) OVER (... ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) = 6` in SQL,
`raw.rolling(6).sum() == 6` in pandas (Day 12's windows). Both scripts compute both routes and print their counts
side by side: they agree. The streak route needs no window size, and it gives you the streak id so you can count
episodes and measure their length. The window route is shorter when you only need the flag.

Today's raw flag is "supply fan at 95% speed or more while running", confirmed after **6 rows** (30 minutes).
Day 14 uses the same shape with a pressure rule.

## Run

```bash
uv run python lessons/course.py run 13
```

That runs [`day13_pandas.py`](day13_pandas.py), then [`day13_sql.py`](day13_sql.py). Both end by printing:

```
Fan runs per AHU (status = 1 streaks):
equipment_id  runs  avg_run_hours  longest_rows  longest_hours             longest_start
       AHU_1   123          12.80          1313         109.42 2026-07-06 09:45:00+00:00
       AHU_2   129          11.62          1313         109.42 2026-07-06 09:45:00+00:00

Full speed (>= 95 %) for 6 rows in a row, by streak id and by rolling sum:
equipment_id  raw_rows  confirmed_rows_streak  confirmed_rows_window  episodes
       AHU_1      1349                   1153                   1153        31
       AHU_2       222                    192                    192         6
```

The fans normally run about 14 hours a day. The longest run is **109 hours**, on both AHUs, from 6 July 09:45 to
10 July 23:05 UTC: the fan never stopped for over four days, so something (probably a schedule override)
kept it on. A person
reading a chart would find that; the streak trick finds it for every AHU in a building with one query.

The confirmed counts are smaller than the raw counts because the first 5 rows of each full-speed run are not yet
"confirmed" (and one-row blips never are). AHU_1 spends far more time at full speed than AHU_2 (1,349 vs 222 rows),
which is itself worth a question.

## Try it

1. Change the confirmation from 6 rows to 12 (one hour) in both scripts. In SQL there are two places to change.
   What happens to the two routes if you only change `:confirm`?
2. Find the longest time each AHU was **off** (status 0) in a row.

<details><summary>Answers</summary>

1. With 12 rows, AHU_1 drops to 995 confirmed rows in 21 episodes, and AHU_2 to 160 rows in 5 episodes. The
   streak route only needs `:confirm` (or `CONFIRM_ROWS`). The window route also needs its frame
   (`ROWS BETWEEN 11 PRECEDING`), and the SQL check `rows_in_window = :confirm`. Change only the parameter and the
   frame still holds 6 rows, so the window route finds none (SQL) while the streak route finds the new answer. The
   two columns disagree, which is how you'd spot the slip. pandas hides it, because `rolling(CONFIRM_ROWS)` reads
   the same constant.
2. Filter the streaks to `supply_fan_status = 0` instead of `1` and take the longest. It is 999 rows, 83.25 hours,
   on both AHUs. The streak table already has all the runs of both kinds; only the filter changes.

</details>

## Why it matters

Day 14 builds an entire fault rule from these pieces: a raw flag, the streak trick, `streak_len >= N`, and a sum of
fault rows times five minutes. Day 15 reuses the trick to find flatlined sensors, where the "value" being compared is
the sensor reading itself.
