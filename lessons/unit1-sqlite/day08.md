# Day 8 — CASE and conditional counts: run hours, unoccupied runtime, percent occupied

**Goal:** ask conditional questions ("static pressure *while the fan runs*", "run hours *while unoccupied*") with
`CASE` in SQL and True/False conditions in pandas.

## Read

A fan that is off has no duct static pressure. If you average `da_p_inwc` over all rows you mix "the fan was off"
into "the pressure was low", and the number means nothing. Almost every fault rule starts by **gating**: judge only
the rows where the equipment is doing its job. That needs a condition inside the query.

**In pandas** a condition is a column of True/False, one per row: `fan_on = df["supply_fan_status"] == 1`. Combine
conditions with `&` (and), `|` (or) and `~` (not). Then:

- `fan_on.sum()` counts the True rows (True counts as 1),
- `fan_on.mean()` is the fraction of True rows,
- `df[fan_on]` keeps only those rows, so `df[fan_on]["da_p_inwc"].mean()` averages only while the fan runs.

**In SQL** the tool is **`CASE`**, SQL's if/else for one row: `CASE WHEN fan = 1 THEN 1 ELSE 0 END`. The first `WHEN`
that matches wins; `ELSE` is the default (leave it out and you get `NULL`). Put it inside an aggregate and you get
**conditional aggregation**:

- `SUM(CASE WHEN condition THEN 1 ELSE 0 END)` counts the rows where the condition holds,
- `AVG(CASE WHEN condition THEN value END)` averages only those rows, because `AVG` skips the `NULL`s that a
  `CASE` without an `ELSE` produces.

Many different counts come out of one pass over the table: total rows, running rows, rows that run while
unoccupied, occupied rows.

| Idea | `day08_sql.py` | `day08_pandas.py` |
|---|---|---|
| a condition | `supply_fan_status = 1` | `fan_on = df["supply_fan_status"] == 1` |
| combine | `AND`, `OR`, `NOT` | `&`, `\|`, `~` |
| count rows | `SUM(CASE WHEN c THEN 1 ELSE 0 END)` | `c.sum()` |
| fraction of rows | `100.0 * SUM(...) / COUNT(*)` | `c.mean() * 100` |
| average only some rows | `AVG(CASE WHEN c THEN x END)` | `df[c]["x"].mean()` |

Careful with `<>` and `NULL`: `occ_c <> 1` is `NULL`, not true, when `occ_c` is `NULL`. This data has no NULLs, but a
real export will; a `CASE` or a condition is where they quietly drop rows.

What AHU_1 says: it ran 1,574.42 hours, of which 58.58 hours were while unoccupied (3.72% of its run time), and it
was scheduled occupied 51.26% of the time. `occ_c` is the BAS's occupancy command (1 occupied, 0 unoccupied). Some
unoccupied running is normal (morning warm-up, night purge) and some is a schedule override someone forgot about.
That ratio is exactly what an "AHU running while unoccupied" rule would look at.

## Run

```bash
uv run python lessons/course.py run 8
```

That runs [`day08_pandas.py`](day08_pandas.py), then [`day08_sql.py`](day08_sql.py). Both print:

```
Run hours: 1574.42
Run hours while unoccupied: 58.58
Percent of rows occupied: 51.26
Percent of run time unoccupied: 3.72
Average static while the fan runs (Pa): 335.6
```

Each row is 5 minutes, so rows × 5 / 60 = hours. Averaged over *all* rows the static pressure is only 195 Pa (Day 6),
because the fan is off nearly half the time; while it runs it is 335.6 Pa.

## Try it

1. Add the average static pressure while the fan is *off* (`supply_fan_status <> 1`) to both scripts. What do you
   expect, and what do you get?
2. Count the rows where the fan is running but static pressure is below 50 Pa ("running with no pressure"). How
   many of those are occupied?
3. Speed (pandas only): the same classification written row by row with `df.apply(my_function, axis=1)` is far slower
   than a True/False column: on 71,072 rows roughly half a second against a few milliseconds. In pandas, reach for
   conditions first. SQL is already "vectorized": the engine does the loop, and you describe the condition.

<details><summary>Answers</summary>

1. SQL: `AVG(CASE WHEN supply_fan_status <> 1 THEN da_p_inwc * :pa_per_inh2o END)`; pandas:
   `df[~fan_on]["da_p_inwc"].mean() * PA_PER_INH2O`. About 35.5 Pa: the fan is off, so there is almost no pressure.
2. SQL: `SUM(CASE WHEN supply_fan_status = 1 AND da_p_inwc * 249.08891 < 50 THEN 1 ELSE 0 END)`; pandas:
   `(fan_on & (df["da_p_inwc"] * PA_PER_INH2O < 50)).sum()`. AHU_1: 460 rows, 209 of them occupied. A fan that "runs"
   with no pressure is a failed fan or a status point that lies, the kind of thing Day 14's FC1 rule flags.

</details>

## Why it matters

"While running", "while occupied", "while unoccupied" are the words every fault rule starts with. In Day 14 they
become the gate `supply_fan_status = 1`, and in later weeks they come from the data model instead of a hard-coded
column. Conditional aggregation is also how you build a dashboard row (hours run, hours faulted, percent occupied)
in one pass over the data. Day 9 groups the same rows by time instead of by condition.
