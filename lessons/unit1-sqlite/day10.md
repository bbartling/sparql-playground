# Day 10 — Open-FDD events: episodes per rule, then which rows fall inside an episode

**Goal:** count Open-FDD's fault episodes and hours per rule, then mark which 5-minute history rows fall inside an
episode, in pandas (a short loop) and SQL (`BETWEEN` with `EXISTS`). Then finish Week 2 with a challenge that uses
everything.

## Read

Open-FDD writes its findings as **episodes**: one row per stretch of time a rule was in fault, with a start, an end
and the rule's name. They ship next to the CSVs in `data/BUILDING_50/*/fdd_events.csv`, and the SQL side has them as
the `fdd_events` table (columns `start_time_utc`, `end_time_utc`, `hvac_system`, `rule_name`, `duration_min`,
`sample_count`). `hvac_system` is `bld_50_AHU_1` for AHU_1. Counting is a plain `GROUP BY`:

```
          rule_name  episodes  hours
economizer_not_used         1    0.0
                fc1        80  484.1
               fc13        90  510.0
      sensor_bounds         2    0.0
```

That answers "how many, how long", but not "what was the AHU doing during them?" For that, the history rows and the
episodes need to meet: the history has one row per instant, the episodes one row per *interval*. A row is **inside**
an episode when `start <= timestamp <= end`.

The beginner approach is the one Day 14 used: **take the episodes one at a time**. For each episode, find the
history rows between its start and end and mark them. The timestamps are text in one format
(`2026-07-15 22:44:01+00:00`), so comparing the text compares the times.

| Step | `day10_sql.py` | `day10_pandas.py` |
|---|---|---|
| episodes per rule | `GROUP BY rule_name` | `events.groupby("rule_name").agg(...)` |
| row inside an episode | `h.timestamp_utc BETWEEN e.start_time_utc AND e.end_time_utc` | `(ts >= start) & (ts <= end)` |
| mark / count the rows | `WHERE EXISTS (SELECT 1 FROM fdd_events AS e WHERE ...)` | `for _, event in fc13_events.iterrows():` then `df.loc[inside, "in_episode"] = True` |

`EXISTS` asks "is there at least one episode around this row?", so a row inside several overlapping episodes still
counts once. The pandas loop gets the same answer: a row is marked True however many episodes mark it.

**Overlap.** Open-FDD's episodes overlap heavily: AHU_1's `fc13` has 90 episodes. That is why the summed `hours`
above (510 h) is so much larger than the time the rows are actually covered (1,206 rows × 5 min = 100.5 h): the
episodes overlap and the sum counts the overlap many times. Count rows (or merge the intervals), don't add up
`duration_min` when intervals overlap.

**Faster ways (for later).** The loop does 90 passes over 35,536 rows, which is instant here. With thousands of
episodes you would use a sorted search (`np.searchsorted`) or `pd.merge_asof` ("the latest episode that started
before this row"), and in SQL an index on the episode start time. `merge_asof` returns one match per row, so with
overlapping episodes it can miss a row that an earlier, longer episode still covers.

## Run

```bash
uv run python lessons/course.py run 10
```

That runs [`day10_pandas.py`](day10_pandas.py), then [`day10_sql.py`](day10_sql.py). Both print:

```
          rule_name  episodes  hours
economizer_not_used         1    0.0
                fc1        80  484.1
               fc13        90  510.0
      sensor_bounds         2    0.0
fc13 rows inside an episode: 1206
Hours those rows cover (5 min each): 100.5
Hours if you add up every episode:   510.0 (episodes overlap)
```

## Try it

1. Change `"fc13"` to `"fc1"` in both scripts. How many rows are inside an fc1 episode, and how does the covered
   time compare with the 484.1 hours you get by adding up the episodes?
2. AHU_2 has no `fc1` episodes at all. Point the scripts at AHU_2 (`AHU_2` in the CSV path, `bld_50_AHU_2` in the SQL)
   and use `"fc1"`. What do you get, and why does it matter that SQL's `COUNT(*)` gives `0` rather than no rows?
3. **Week 2 challenge.** Add `supply_fan_status` and `outside_air_temp_f` to the history load. Split AHU_1's rows
   into *inside an fc13 episode* and *outside*, and report the row count, the percent of rows with the fan running,
   and the mean outside-air temperature in °C for each group. What does it say about when fc13 fires?

<details><summary>Answers</summary>

1. Change the rule name and run both scripts; they still agree. The rows inside fc1 episodes cover far less time
   than 484.1 hours, because those episodes overlap too.
2. Zero rows inside an episode. A missing group is a join's most common silent failure: with an `INNER JOIN` AHU_2
   would vanish from a report, which would look as though AHU_2 wasn't analyzed rather than healthy. `EXISTS` and the
   `False` column keep every row.
3. Result (both languages agree):

   ```
   in_episode   rows  pct_fan_running  mean_oa_c
        False  34330             51.5       15.9
         True   1206            100.0       26.3
   ```

   Every row inside an `fc13` episode has the fan running (100%), and it's warm outside: 26.3 °C against 15.9 °C
   otherwise. The rule fires when the AHU is working in warm weather, which is when you'd expect a cooling-related
   rule to find trouble. In pandas: `df.groupby("in_episode")` with `agg(rows=("in_episode", "size"),
   fan=("supply_fan_status", "mean"), oa_f=("outside_air_temp_f", "mean"))`, then convert the mean temperature with
   Day 6's formula. In SQL: select `EXISTS (...)` as `in_episode` and `GROUP BY in_episode`. This uses Day 6 (units),
   Day 8 (conditions) and Day 9 (grouping) with today's episode matching.

</details>

## Why it matters

Open-FDD tells you *that* a rule fired; matching rows to episodes is how you ask *what the equipment was doing* when
it did: the fan state, the weather, the setpoint, the schedule. Day 14 already compared your own rule with
Open-FDD's episodes this way, and later weeks do it again. Watch for the two traps from this week that bite here
too: a join on a repeated key multiplies rows (Day 7), and summing episode durations double counts where episodes
overlap.
