# Day 19 — Joining weather: the as-of join

**Goal:** attach the most recent weather reading to every 5-minute AHU row, ignoring readings older than two hours,
in SQL (correlated subquery plus an index) and in pandas (`merge_asof`); see why the three ways to do it scale so
differently; then write a sensor-versus-weather rule on top.

## Read

Some Open-FDD rules need a number the building doesn't measure well: the real outdoor temperature. A sensor on an AHU's
outside-air intake can sit in the sun, in a shaded louver, or be wired wrong. The **`OAT-METEO`** rule compares it with
a weather feed (Open-FDD pulls hourly data from Open-Meteo) and flags a sensor that disagrees with the weather.

The join is awkward because the two series don't share timestamps. The AHU logs every 5 minutes; the weather arrives
hourly and sometimes not at all. You can't `JOIN ... ON h.ts = w.ts`. You want, for each AHU row, **the latest weather
row at or before that time, but only if it is recent enough** (here: no more than 2 hours old; otherwise it is
"stale", and the answer is `NULL`/`NaN`, meaning unknown, not "use whatever's old"). This is an **as-of join**.

**The data.** The AHU side is the real Building 50 export (both CSVs, 71,072 rows, `supply_fan_status` and
`outside_air_temp_f` converted to °C: `(f - 32) * 5 / 9`, since fault math is SI). **The weather is a stand-in.**
There is no weather feed in this repo, so we make one honestly: hourly means of AHU_1's own outdoor sensor, plus
0.5 °C of noise (real weather never matches a sensor exactly), with 12% of the hours deleted and one 6-hour block
missing, the way a feed with failures looks (2,592 of 2,961 hours remain). In production this table is the Open-Meteo
feed. It is derived from AHU_1, so AHU_1 will agree with it; AHU_2 has its own sensor, which reads about 1.2 °C
higher on average and has a few readings of 0 °F, which look like dropouts. The rule should notice.

The weather stand-in is made by the same small `make_weather` function in both scripts (pandas builds it, the SQL
script loads it into a `wx` table): it is *input data*, not the computation we compare.

How the join is done in each tool:

| | SQL (`day19_sql.py`) | pandas (`day19_pandas.py`) | plain Python (`day19_pandas.py`) |
|---|---|---|---|
| Idea | per AHU row, look up the newest weather row `<= ts` | merge two sorted tables in one pass | per AHU row, search the weather list |
| Code | `(SELECT w.ts FROM wx w WHERE w.ts <= h.ts AND w.ts >= h.ts - :tol ORDER BY w.ts DESC LIMIT 1)` | `pd.merge_asof(h, wx, on="ts", direction="backward", tolerance=...)` | `bisect_right(wx_ts, ts) - 1` |
| Stale handling | extra `AND w.ts >= h.ts - :tol` | `tolerance=` argument | `if ts - wx_ts > tol` |

**Complexity.** Let N be AHU rows and M weather rows.

- A *nested loop* with no index: for each of N rows, scan all M weather rows. **O(N·M)**. SQLite does this when there
  is no index on `wx(ts)`; so does a naive Python double loop.
- *With an index* (SQLite) or a sorted list and binary search (Python's `bisect`): each lookup is O(log M), so
  **O(N log M)**.
- `merge_asof` on two *sorted* inputs walks both once: **O(N + M)**. The price: the inputs must be sorted by the key,
  which costs O(N log N) if they aren't.

## Run

```bash
uv run python lessons/course.py run 19
```

That runs [`day19_pandas.py`](day19_pandas.py), then [`day19_sql.py`](day19_sql.py). `ts` is epoch seconds in both
(`unixepoch(timestamp_utc)` in SQL, `pd.to_datetime(...)` as seconds in pandas). Both build the per-row join, the rule,
the 1-hour variant and a growing-size benchmark on synthetic rows (`lab.synthetic_history`, one AHU, weather one hour
per 12 rows). `RESULTS` holds the per-row join (`asof_join`), the rule's `oat_meteo_hours`, `rows_without_weather` and
the number of matches per benchmark size (`timing_matches`).

```
71,072 AHU rows, 2,592 weather rows (of 2,961 hours)
rows with no usable weather: 1250
```

**The as-of join in SQL.** The inner query is run once *per AHU row*, which is what makes it "correlated". The weather
value is then looked up by that timestamp. In pandas, `merge_asof` needs both sides sorted by the key. Our table has two
AHUs interleaved by time, so we sort by `ts` for the merge, and copy `ts` into a `wx_ts` column so we can see which
weather row matched. A detail worth knowing: both treat the 2-hour limit as inclusive, so a reading exactly 7,200 s old
still counts. (The unit test would fail if they disagreed.)

**How the database does it: `EXPLAIN QUERY PLAN`** (Day 12). `day19_sql.py` prints the plan for the indexed and the
unindexed weather table:

```
EXPLAIN QUERY PLAN with wx:
   CORRELATED SCALAR SUBQUERY 1
   SEARCH w USING COVERING INDEX wx_ts (ts>? AND ts<?)

EXPLAIN QUERY PLAN with wx_plain:
   CORRELATED SCALAR SUBQUERY 1
   SCAN w
   USE TEMP B-TREE FOR ORDER BY
```

(Abridged.) With the index, each probe is a B-tree range seek; without it, a full scan of the weather table (plus a
temporary sort for the `ORDER BY`) per AHU row. SQLite also builds a throwaway "automatic index" for the final `LEFT JOIN`
on the unindexed copy, but not for the subquery's range condition, which is the expensive part.

**Plain Python, two ways.** In the pandas script. The nested loop is what SQLite does with no index. The `bisect` version
is the same idea as the index: keep the weather timestamps sorted and binary-search them. The pandas script prints
`bisect loop finds the same weather row as merge_asof: True`.

**Timing, growing the data.** The two O(N·M) methods stop at 10,000 rows; at a million rows they would run for hours.
`NaN` means "not run". On the machine this was written on (seconds):

```
      N     M  nested_s  bisect_s    asof_s          (day19_pandas.py)
   1000    70  0.002315 0.0001861 0.0009288
  10000   726      0.25   0.00239  0.001678
 100000  7322       NaN   0.03476  0.008587
1000000 73532       NaN    0.4317   0.06423

      N     M  sql_noindex_s  sql_index_s             (day19_sql.py)
   1000    70        0.00362    0.0002054
  10000   726         0.3633     0.002943
 100000  7322            NaN      0.02833
1000000 73532            NaN       0.3345
```

Read it in three parts. **The unindexed methods** (`nested_s`, `sql_noindex_s`) grow by about 100x for every 10x of data
(N grows 10x and so does M, so N·M grows 100x): 10,000 rows takes 0.25 s and 0.36 s, and a million would take hours.
SQLite's unindexed subquery is a compiled nested loop, but it follows the same curve as the Python one (and here is not
even faster). **With an index** (`sql_index_s`, and `bisect_s`, the Python equivalent) the growth is about 10x per 10x:
N lookups, each O(log M). **`merge_asof`** is the quickest because it does the whole job as one O(N + M) merge in
compiled code. It has almost no per-row overhead. Both scripts print the number of matched rows at every size
(`timing_matches`), and the unit test checks that they are the same.

The lesson that carries over to all of Week 4: an index (or a sort) changes the *shape* of the curve. Vectorizing only
changes the slope.

**A sensor-versus-weather rule.** In the spirit of `OAT-METEO`: while the fan runs, flag the AHU when its outdoor
sensor differs from the weather by more than 3 °C, confirmed for 6 rows (30 minutes). No weather (stale or missing)
means *unknown*, so no fault. In SQL, the join result is a CTE under the streak machinery from Day 14; in pandas, the
same `shift` / `cumsum` / `cumcount` trick.

```
equipment_id  fault_rows  raw_rows  fault_hours
       AHU_1          27       111         2.25
       AHU_2         196       526        16.33
```

AHU_2's sensor is found: 16.3 confirmed hours against 2.3 for AHU_1, whose sensor the weather was derived from (it
isn't silent, because the weather has 0.5 °C of noise and the rule's tolerance is finite). In real data there would be
more false alarms, which is why the rule has a 3 °C tolerance, a confirmation time and a stale-weather guard. Note what
the 2-hour tolerance bought: when the weather feed is down, the rule says nothing, instead of comparing a live sensor to
yesterday's weather.

## Try it

1. Tighten the tolerance to 1 hour. How many AHU rows lose their weather?
2. Replace "latest at or before" with "nearest *after*": SQL `w.ts >= h.ts ... ORDER BY w.ts ASC`, pandas
   `direction="forward"`. When would you ever want that, and when is it a bug?

<details><summary>Answers</summary>

1. `rows_without_weather` in each script's `RESULTS` already answers it: 1,250 rows with a 2-hour tolerance, 8,252 with
   one hour. Rows lose weather in the hours after a feed outage: with a 1-hour limit, a row whose latest reading is 1-2
   hours old becomes unknown. The two implementations agree row for row. In SQL, `tol` is a parameter:
   `query(NO_WEATHER_SQL, tol=3600)`; in pandas, `join_pandas(ahu, wx, 3600)`.
2. In pandas, `pd.merge_asof(left, wx.assign(wx_ts=wx.ts), on="ts", direction="forward", tolerance=TOL_S)`. In SQL,
   swap the condition and the sort in the subquery:

   ```sql
   WHERE w.ts >= h.ts AND w.ts <= h.ts + :tol
   ORDER BY w.ts ASC LIMIT 1
   ```

   Every matched weather timestamp is then at or after the row's (1,272 rows end up with no match, the ones before a
   gap this time). The forward join pairs each row with a *future* weather reading. That is legitimate for offline
   analysis when a value is stamped at the *end* of its interval (a mean over the previous hour). It is a **look-ahead
   bug** in anything that claims to run live, or in a backtest of a live rule: the rule would "know" something it
   couldn't have known yet. Always ask which direction is honest for the data you're joining.

</details>

## Why it matters

"Latest value at or before" is the most common join in building data: setpoints that change a few times a day against
readings every minute, schedules against measurements, weather against everything. Remember the three shapes: a nested
loop (O(N·M)), an index lookup (O(N log M)), a sorted merge (O(N + M)). Day 20 pits the three tools against each other on
the FC1 rule at scale.
