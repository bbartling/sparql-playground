# Day 8 — CASE and conditional aggregation: pressure while running, hours while unoccupied

**Goal:** ask conditional questions ("static pressure *while the fan runs*", "run hours *while unoccupied*") with
`CASE` in SQL and with masks, `np.where`, `np.select` and `groupby` in pandas, and see why vectorized beats
row-by-row.

## Read

A fan that is off has no duct static pressure. If you average `da_p_inwc` over all rows you mix "the fan was off"
into "the pressure was low", and the number means nothing. Almost every fault rule starts by **gating**: judge only
the rows where the equipment is doing its job. That needs a condition inside the query.

**`CASE`** is SQL's if/else for one row: `CASE WHEN fan = 1 THEN 'running' ELSE 'off' END`. The first `WHEN` that
matches wins; `ELSE` is the default (leave it out and you get `NULL`). Use it two ways:

1. **As a column or `GROUP BY` key.** `GROUP BY CASE WHEN supply_fan_status = 1 ...` gives one group per state.
2. **Inside an aggregate: conditional aggregation.** In SQLite a comparison evaluates to 0 or 1, so
   `sum(supply_fan_status = 1 AND occ_c <> 1)` *counts the rows* where both hold (other databases spell it
   `sum(CASE WHEN ... THEN 1 ELSE 0 END)`). Many different counts come out of one scan: total rows, run rows, rows
   that run while unoccupied, rows occupied.

The pandas pieces:

| Idea | `day08_sql.py` | `day08_pandas.py` |
|---|---|---|
| a condition | `supply_fan_status = 1` | `running = h.supply_fan_status == 1` (a boolean *mask*) |
| combine | `AND`, `OR`, `NOT` | `&`, `\|`, `~` (parenthesize each side) |
| two outcomes | `CASE WHEN c THEN a ELSE b END` | `np.where(c, a, b)` |
| many outcomes | `CASE WHEN c1 THEN a WHEN c2 THEN b ELSE d END` | `np.select([c1, c2], [a, b], default=d)` |
| per-group counts | `GROUP BY equipment_id`, `sum(cond)` | `h.assign(flag=cond).groupby("equipment_id")["flag"].sum()` |
| fraction of rows | `100.0 * sum(occ_c = 1) / count(*)` | `(h.occ_c == 1).mean() * 100` |

Careful with `<>` and `NULL`: `occ_c <> 1` is `NULL`, not true, when `occ_c` is `NULL`. This data has no NULLs, but a
real export will; a `CASE` or a mask is where they quietly drop rows. (pandas masks do the same with `NaN`.)

**Vectorized vs row-by-row.** `np.select` evaluates the whole column in compiled loops. `df.apply(f, axis=1)` calls a
Python function once per row, creating a `Series` for each. Both are O(n), but the constants are very different: on
71,072 rows the vectorized version takes about 2 ms and `apply(axis=1)` about half a second, roughly 200× slower,
and the gap grows with the data. In pandas, reach for a mask or `np.select` first. SQL is already "vectorized": the
engine does the loop, and you describe the condition.

What Building 50 says (both printouts):

```
Duct static pressure by fan state (Pa):
equipment_id fan_state  rows  mean_static_pa  mean_setpoint_pa  mean_error_pa
       AHU_1       off 16643            35.5             329.9         -294.4
       AHU_1   running 18893           335.6             349.3          -13.7
       AHU_2       off 17541            37.6             197.9         -160.3
       AHU_2   running 17995           349.4             188.2          161.2
```

Averaging only the *running* rows shows it: AHU_1 sits 14 Pa under setpoint, AHU_2 about
161 Pa *over* it (Day 14 turns that into a rule). With the fan off the gap is meaningless, so a rule gates it out.

## Run

```bash
uv run python lessons/course.py run 8
```

That runs [`day08_pandas.py`](day08_pandas.py), then [`day08_sql.py`](day08_sql.py). The second table:

```
Run hours, occupancy:
equipment_id  rows   run_h  run_h_unoccupied  pct_occupied  pct_run_while_unoccupied
       AHU_1 35536 1574.42             58.58         51.26                      3.72
       AHU_2 35536 1499.58             11.17         51.30                      0.74
```

`occ_c` is the BAS's occupancy command (1 occupied, 0 unoccupied). Both AHUs are scheduled occupied about 51% of the
time and run about 1,500 hours. AHU_1 runs 58.6 hours while unoccupied, 3.7% of its run time; AHU_2 only 11.2 h. Some
unoccupied running is normal (morning warm-up, night purge) and some is a schedule override someone forgot about.
That ratio is exactly what an "AHU running while unoccupied" rule would look at.

After the tables the pandas script times mask vs `apply`; the SQL script times one conditional-aggregation query
against four separate `COUNT` queries (one scan versus four).

## Try it

1. Add a count to both scripts: rows where the fan is running but static pressure is below 50 Pa ("running with no
   pressure"). How many per AHU? How many of those are occupied?
2. Replace `np.select` with two nested `np.where` calls, and the `CASE` with a nested `CASE` (one `CASE` inside
   the `ELSE` of another). Which reads better with four states?

<details><summary>Answers</summary>

1. SQL: `sum(supply_fan_status = 1 AND duct_static_pa < 50)`; pandas: `(running & (h.duct_static_pa < 50))`
   summed per AHU. AHU_1: 460 rows, 209 of them occupied. AHU_2: 26 rows, 14 occupied. AHU_1's fan "runs" with no
   pressure far more often: a failed fan or a status point that lies. The difference is the kind of thing Day 14's
   FC1 rule flags.
2. `np.where(a, "x", np.where(b, "y", np.where(c, "z", "w")))` works, but each level hides one more condition; four
   states is where `np.select` (flat list of condition → label) and a flat `CASE` pull ahead.

</details>

## Why it matters

"While running", "while occupied", "while unoccupied" are the words every fault rule starts with. In Day 14 they
become the gate `supply_fan_status = 1`, and in later weeks they come from the data model instead of a hard-coded
column. Conditional aggregation is also how you build a dashboard row (hours run, hours faulted, percent occupied)
in one pass over the data. Day 9 groups the same rows by time instead of by condition.
