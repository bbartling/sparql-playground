# Day 10 — Joining Open-FDD's results: episodes per rule, then tag every row with its fault episode

**Goal:** count Open-FDD's fault episodes and hours per rule, then attach each 5-minute history row to the episode(s)
it falls inside: an *interval join*, in SQL (`BETWEEN` join) and pandas (`searchsorted`, `merge_asof`). Then finish
Week 2 with a challenge that uses everything.

## Read

Open-FDD writes its findings as **episodes**: one row per stretch of time a rule was in fault, with a start, an end
and the rule's name. They ship next to the CSVs in `data/BUILDING_50/*/fdd_events.csv`, and the SQL side has them as
the `fdd_events` table (columns `start_time_utc`, `end_time_utc`, `hvac_system`, `rule_name`, `duration_min`,
`sample_count`). `hvac_system` is `bld_50_AHU_1`; the scripts strip the prefix to get the same `equipment_id`
the history
uses. Counting is a plain `GROUP BY`:

```
equipment_id           rule_name  episodes  hours
       AHU_1                 fc1        80  484.1
       AHU_1                fc13        90  510.0
       AHU_2                fc13        77  209.9
```

That answers "how many, how long", but not "what was the AHU doing during them?" For that, the two tables need to
meet: the history has one row per instant, the episodes one row per *interval*. An **interval join** matches a row
to an episode when `start <= timestamp <= end`.

| Step | `day10_sql.py` | `day10_pandas.py` |
|---|---|---|
| episodes per rule | `GROUP BY equipment_id, rule_name` | `groupby(["equipment_id", "rule_name"]).agg(...)` |
| row inside episode | `ON r.timestamp_utc BETWEEN e.start_time_utc AND e.end_time_utc` | `start <= t <= end` on epoch seconds |
| how many episodes at once | `LEFT JOIN` + `GROUP BY row` + `count(e.start_time_utc)` | `searchsorted(starts, t, "right") - searchsorted(ends, t, "left")` |
| latest episode that started | `SELECT max(start) ... WHERE start <= row_ts` (index seek) | `pd.merge_asof(rows, episodes, by="equipment_id")` |

**Why `searchsorted` works.** Sort the starts and sort the ends, once. For a time `t`, the episodes that have started
are `#(start <= t)`, the ones that already finished are `#(end < t)`, and the difference is how many contain `t`.
Each count is a binary search, so tagging n rows against E episodes costs O((n + E) log E), where the obvious
every-row-against-every-episode comparison is O(n · E). On the 35,536 × 90 rows here it's 1.7 ms against 10 ms with
numpy broadcasting; against a pure-Python double loop the gap is orders of magnitude.

**Why SQL needs an index here.** The `BETWEEN` join is a "range join": `ev` has an index on
`(equipment_id, start_time_utc)`, so for each row SQLite seeks to the episodes with `start_time_utc <= row time`
(the plan says `SEARCH e USING INDEX ev_eq_start (equipment_id=? AND start_time_utc<?)`) and then filters on the end.
A B-tree can only narrow one end of an interval, which is why interval joins are slower than equality joins (about a
second here for 71,072 rows, against tens of milliseconds for Day 7's join).

**As-of vs interval.** `merge_asof` is built for "the most recent thing before this row" (a price, a setpoint, a
status change), and it's fast because both sides are sorted. It returns **one** match, the latest start at or before
the row; the script keeps it only if that episode hasn't ended yet. That is correct *if episodes don't overlap*.
Open-FDD's episodes **do** overlap heavily: AHU_1's `fc13` has 90 episodes and, at the busiest moment, 15 open at
once (`max_open`). That also explains why the summed `hours` above (510 h) is so much larger than the time the rows
are actually covered (1,206 rows × 5 min = 100.5 h): the episodes overlap and the sum counts the overlap many
times. Count rows or merge the intervals, don't add up `duration_min` when intervals overlap. (`pd.IntervalIndex`
is the other pandas option, but its `get_indexer` raises `InvalidIndexError: cannot handle overlapping indices`
for this data; `get_indexer_non_unique` is the overlapping-friendly version.)

Here the as-of lookup misses no rows (`rows_missed_by_asof` is 0), because the overlapping episodes share the same
end.
That's luck of this data, not a property you can rely on: a short episode starting inside a long one would hide
the long one from `merge_asof`. The `episodes_open` count is the one to trust.

## Run

```bash
uv run python lessons/course.py run 10
```

That runs [`day10_pandas.py`](day10_pandas.py), then [`day10_sql.py`](day10_sql.py). Both print:

```
Every 5-minute row tagged with its fc13 episodes:
equipment_id  rows  rows_in_episode  max_open  rows_missed_by_asof  covered_h  episode_hours_summed
       AHU_1 35536             1206        15                    0      100.5                 510.0
       AHU_2 35536              954        10                    0       79.5                 209.9
equipment_id             timestamp_utc  episodes_open              latest_start
       AHU_1 2026-04-09 15:25:00+00:00              1 2026-04-09 15:23:30+00:00
```

A tagged row carries the start of its episode (`latest_start`). Timestamps are ISO text in one format, so SQL compares
the strings directly and pandas converts them to seconds since 1970; the results are identical.
At the end each script prints a timing: pandas, brute force vs binary search; SQL, the `BETWEEN` join vs the as-of
lookup.

## Try it

1. Change `RULE` / `rule` to `"fc1"` in both scripts. What do you get for AHU_2, and why is that a trap for a naive
   `INNER JOIN` version of the query?
2. **Week 2 challenge.** Use the tagged rows. Add `supply_fan_status` and `outside_air_temp_f` to the history load.
For
   each AHU, split the rows into *inside an fc13 episode* and *outside*, and report the row count, the percent of rows
   with the fan running, and the mean outside-air temperature in °C. What does it say about when fc13 fires?

<details><summary>Answers</summary>

1. AHU_2 has no `fc1` episodes at all. With a `LEFT JOIN` every row still appears with `episodes_open = 0`; with an
   `INNER JOIN` AHU_2 would vanish from the result, and a report built on it would look as though AHU_2 wasn't
   analyzed rather than healthy. Missing groups are a join's most common silent failure.
2. Result (both languages agree):

   ```
   equipment_id  in_episode   rows  pct_fan_running  mean_oa_c
          AHU_1       False  34330             51.5       15.9
          AHU_1        True   1206            100.0       26.3
          AHU_2       False  34582             49.3       17.2
          AHU_2        True    954            100.0       27.3
   ```

   Every row inside an `fc13` episode has the fan running (100%), and it's warm outside: 26–27 °C against 16–17 °C
   otherwise. The rule fires when the AHU is working in warm weather, which is when you'd expect a cooling-related
   rule to find trouble. SQL, with the `EXISTS` standing in for the join:

   ```sql
   SELECT h.equipment_id,
          EXISTS (SELECT 1 FROM ev WHERE ev.equipment_id = h.equipment_id
                    AND h.timestamp_utc BETWEEN ev.start_time_utc AND ev.end_time_utc) AS in_episode,
          count(*) AS rows, 100.0 * avg(supply_fan_status) AS pct_fan_running,
          avg((outside_air_temp_f - 32) * 5 / 9.0) AS mean_oa_c
   FROM h GROUP BY 1, 2
   ```

   pandas: merge the history columns onto `tagged`, add `in_episode = tagged.episodes_open > 0` and
   `oa_c = (outside_air_temp_f - 32) * 5 / 9`, then `groupby(["equipment_id", "in_episode"]).agg(...)`. This uses
   Day 6 (units), Day 7 (join), Day 8 (conditional aggregation) and today's interval join.

</details>

## Why it matters

Open-FDD tells you *that* a rule fired; the interval join is how you ask *what the equipment was doing* when it did:
the fan state, the weather, the setpoint, the schedule. Day 14 already compared your own rule with Open-FDD's
episodes this way, and later weeks do it again. Watch for the two traps from this week that bite here too:
a join on a repeated key multiplies rows (Day 7), and summing episode durations double counts where episodes
overlap.
