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

**The data.** The AHU side is the synthetic AHU from Day 16: AHU_1's first 100,000 rows (about 347 days), with
`oat_c`, its outdoor-air sensor in °C. **The weather is synthetic too**, in `var/synthetic_weather.csv` (and the
`synthetic_weather` table): one row per hour, the same daily temperature wave as the AHU's sensor plus noise, with 12%
of the hours deleted at random and six hours in a row missing near the start, the way a feed with failures looks. In
production this table is the Open-Meteo feed. The AHU's sensor has a planted problem: for 100 rows in every week it
reads **6 °C high**, like a sensor with the sun on it. The rule should notice.

How the join is done in each tool:

| | SQL (`day19_sql.py`) | pandas (`day19_pandas.py`) | plain Python (`day19_pandas.py`) |
|---|---|---|---|
| Idea | per AHU row, look up the newest weather row `<= ts` | merge two sorted tables in one pass | per AHU row, binary-search the weather times |
| Code | `(SELECT w.ts FROM synthetic_weather AS w WHERE w.ts <= h.ts AND w.ts >= h.ts - :max_age_seconds ORDER BY w.ts DESC LIMIT 1)` | `pd.merge_asof(ahu, weather, left_on="ts", right_on="weather_ts", direction="backward", tolerance=...)` | `bisect_right(weather_times, ts) - 1` |
| Stale handling | `AND w.ts >= h.ts - :max_age_seconds` | `tolerance=` argument | `if ts - weather_times[i] <= MAX_AGE_SECONDS` |

**Complexity.** Let N be AHU rows and M weather rows.

- A *nested loop* with no index: for each of N rows, scan all M weather rows. **O(N·M)**. SQLite does this when there
  is no index on the weather `ts`; so does a naive Python double loop.
- *With an index* (SQLite) or a sorted list and binary search (Python's `bisect`): each lookup is O(log M), so
  **O(N log M)**.
- `merge_asof` on two *sorted* inputs walks both once: **O(N + M)**. The price: the inputs must be sorted by the key,
  which costs O(N log N) if they aren't.

## Run

```bash
uv run python lessons/course.py run 19
```

That runs [`day19_pandas.py`](day19_pandas.py), then [`day19_sql.py`](day19_sql.py). `ts` is epoch seconds in both
tables. The pandas script prints:

```
AHU rows: 100000 | weather rows: 36586
Rows with no usable weather: 1372
Average weather temperature on the matched rows (C): 9.967
bisect loop matched the same rows: True

Sensor vs weather rule (fan on, more than 3 C apart for 30 minutes):
  raw rows: 5089 | confirmed rows: 3892 | hours: 324.33

Microseconds per AHU row (times vary by machine):
  nested loop: 908.34
  bisect loop: 0.23
  merge_asof:  0.06
```

and the SQL script the same numbers, with its own timings and two query plans:

```
Microseconds per AHU row (times vary by machine):
  no index:   900.47
  with index: 0.34
Plan on synthetic_weather: SEARCH synthetic_weather USING COVERING INDEX synthetic_weather_idx (ts>? AND ts<?)
Plan on weather_copy: SCAN weather_copy | USE TEMP B-TREE FOR ORDER BY
```

`RESULTS` holds `rows_without_weather`, `average_weather_c` and the rule's counts; the unit test checks that both
scripts agree.

**The as-of join in SQL** (steps 1-2). The inner query is run once *per AHU row*, which is what makes it
"correlated". The weather value is then looked up by that timestamp with an ordinary join. In pandas, `merge_asof`
needs both sides sorted by the key (they are). A detail worth knowing: both treat the 2-hour limit as inclusive, so a
reading exactly 7,200 s old still counts. (The unit test would fail if they disagreed.)

**How the database does it: `EXPLAIN QUERY PLAN`** (Day 11). With the index, each probe is a B-tree range seek
(`SEARCH ... USING COVERING INDEX`). On `weather_copy`, a copy with no index, it is a full scan of the weather table
plus a temporary sort for the `ORDER BY`, for every AHU row. That is why the SQL script runs the no-index version on
200 rows only.

**Plain Python, two ways** (steps 3-4 of the pandas script). The nested loop is what SQLite does with no index. The
`bisect` version is the same idea as the index: keep the weather timestamps sorted and binary-search them. The script
prints `bisect loop matched the same rows: True`.

**Timing.** The timings are per AHU row, in microseconds, so different row counts compare fairly. The two O(N·M)
methods take about 900 µs per row: at 100,000 rows that would be 90 seconds, which is why they only get 200. With an
index (or `bisect`, its Python twin) a lookup is a fraction of a microsecond: thousands of times faster, and the gap
grows with M. `merge_asof` is the quickest because it does the whole job as one O(N + M) merge in compiled code, with
almost no per-row overhead. SQLite's unindexed subquery is a compiled nested loop, but it is no faster than the Python
one: the curve, not the language, decides.

The lesson that carries over to all of Week 4: an index (or a sort) changes the *shape* of the curve. Vectorizing only
changes the slope.

**A sensor-versus-weather rule** (step 5). In the spirit of `OAT-METEO`: while the fan runs, flag the AHU when its
outdoor sensor differs from the weather by more than 3 °C, confirmed for 6 rows (30 minutes). No weather (stale or
missing) means *unknown*, so no fault. In SQL, the join result is a temp table under Day 14's streak steps; in pandas,
the same `shift` / `cumsum` / `cumcount` trick. It finds 3,892 confirmed rows, 324 hours: the "sun on the sensor"
stretches. In real data there would be more false alarms, which is why the rule has a 3 °C tolerance, a confirmation
time and a stale-weather guard. Note what the 2-hour limit bought: when the weather feed is down, the rule says
nothing, instead of comparing a live sensor to yesterday's weather.

## Try it

1. Tighten the limit to 1 hour (`MAX_AGE_SECONDS = 3600`, `"max_age_seconds"` in SQL). How many AHU rows lose their
   weather?
2. Replace "latest at or before" with "nearest *after*": SQL `w.ts >= h.ts AND w.ts <= h.ts + :max_age_seconds ...
   ORDER BY w.ts ASC`, pandas `direction="forward"`. When would you ever want that, and when is it a bug?

<details><summary>Answers</summary>

1. 11,530 rows have no usable weather, against 1,372 with 2 hours. With a 1-hour limit, every AHU row in the hour
   after a missing weather hour becomes unknown (12% of hours are missing, so about 12% of rows). The rule's
   confirmed hours drop to 259.5. The two implementations still agree.
2. In SQL, swap the condition and the sort in the subquery:

   ```sql
   WHERE w.ts >= h.ts AND w.ts <= h.ts + :max_age_seconds
   ORDER BY w.ts ASC LIMIT 1
   ```

   Every matched weather timestamp is then at or after the row's (1,372 rows again have no match, the ones before a
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
