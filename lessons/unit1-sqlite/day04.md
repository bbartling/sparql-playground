# Day 4 — Summary stats: COUNT, MIN, MAX, AVG, SUM

**Goal:** summarize a column in one row, in pandas and in SQL, and turn a status point into run hours.

## Read

**Aggregate functions** fold many rows into one value. pandas has a method for each:

| SQL | pandas (on a column `v`) | Notes |
|---|---|---|
| `count(*)` | `len(df)` | rows |
| `count(col)` | `v.count()` | rows where the value is not NULL / NaN |
| `min(col)`, `max(col)` | `v.min()`, `v.max()` | ignore NULLs / NaN |
| `avg(col)` | `v.mean()` | mean of the non-NULL values |
| `sum(col)` | `v.sum()` | total (SQL: NULL for no rows; pandas: 0) |
| `round(x, n)` | `round(x, n)` | for reading, not storage. **Never round before comparing** |

Without `GROUP BY` (tomorrow), an aggregate query returns exactly one row.

**NULLs.** A missing reading is `NULL` in SQL and `NaN` in pandas. Both skip it in `min`, `max`, `avg` and `sum`, and
both agree that `count(col)` counts only the values that are there, while `count(*)` counts rows. So the mean of
`1, <missing>, 3` is 2.0, not 4/3. The Building 50 columns have no gaps, so try it on three made-up values:
`pd.Series([1, None, 3]).mean()` in pandas, `SELECT AVG(x) FROM (SELECT 1 AS x UNION ALL SELECT NULL UNION ALL
SELECT 3)` in SQL. Both give 2.0. In real data a flat-lined or
missing sensor often shows up as NULLs, or as a suspicious constant like `0` or `-999`; only the first is skipped
for you.

**Run hours.** A status point is 1 when running and 0 when off. With one reading every 5 minutes,
`sum(status) × 5 / 60` is the **run hours**. Use `60.0`, not `60`, in SQL: with two integers SQLite divides as
integers and drops the remainder (`7 * 5 / 60` is `0`). Python 3's `/` is always true division; its `//` is the one
that floors. Different engines, different gotchas.

**How each engine does it.** Both are one pass over the rows, O(n). SQLite computes every aggregate in the `SELECT`
list in the *same* pass, while it streams the rows off the table, and returns a single row. pandas works on columns in
memory: each of `min`, `max`, `mean` is its own fast, vectorized pass (a compiled C loop, not a Python `for`), and
the rows had to be loaded into Python first. So SQL moves one row of results; pandas moves all the input. Nothing
here is faster in an *algorithmic* sense. The aggregate is O(n) either way, and no index helps with `avg()`. What
differs is how much data crosses from the database into your program.

## Run
```bash
uv run python lessons/course.py run 4
```

That runs [`day04_pandas.py`](day04_pandas.py), then [`day04_sql.py`](day04_sql.py). Both print:

```
Outside air temperature (F): average 61.28 min 17.8308 max 98.8608
Supply fan run hours: 1574.4
Fraction of time the fan ran: 0.532
```

How each step maps across:

| Step | `day04_sql.py` | `day04_pandas.py` |
|---|---|---|
| 2. three stats in one pass | `SELECT AVG(c), MIN(c), MAX(c) FROM ahu_1` | `df[c].mean()`, `df[c].min()`, `df[c].max()` |
| 3. run hours | `SUM(supply_fan_status) * 5 / 60.0` | `df["supply_fan_status"].sum() * 5 / 60` |
| 4. fraction of time on | `AVG(supply_fan_status)` | `df["supply_fan_status"].mean()` |

The dataset covers about 2,961 hours (35,536 readings × 5 minutes), so AHU_1's fan ran 1,574 of them, 53.2% of
the time. (The average of a 0/1 column is the fraction of rows that are 1.)

The averages are printed rounded, but the checks behind these lessons compare the raw values to 1e-9: rounding before
you compare turns "equal" into "equal to 3 decimals".

## Try it

1. What are AHU_2's average outside air temperature and its duct static/setpoint averages? How do they compare with
   AHU_1's? (Add AHU_2 to the SQL with a second `FROM`, or `UNION ALL`.)
2. How many hours was AHU_1 scheduled occupied? Occupancy is column `occ_c` (1 = occupied). Compare with the fan's run
   hours.

<details><summary>Answers</summary>

1. AHU_2: outside air 63.42 °F (AHU_1: 61.28), duct static 0.785 inH2O against a setpoint average of 0.775. The two
   outside-air averages differ by 2 °F even though both AHUs sit in the same building: they are different sensors in
   different places, so even the "same" quantity needs checking before you compare it. And AHU_2's average static is
   at its setpoint, where AHU_1's static is far below its (1.366). That gap is today's hint at a problem on AHU_1.
   But it includes all the hours the fan was off, when static is near zero. Day 8 asks the fair question: what is
   static *while the fan runs*?

   ```sql
   SELECT avg(outside_air_temp_f), avg(da_p_inwc), avg(da_p_setpoint_inwc) FROM ahu_2
   ```

2. 1,518.0 occupied hours (`sum(occ_c) * 5 / 60.0`) against 1,574.4 fan hours: the fan runs 56 hours more than the
   schedule says the building is occupied, on top of any hours it runs for warm-up or night purge. (AHU_2: 1,519.25
   occupied hours, 1,499.6 fan hours.) Whether that is waste or sensible depends on the sequence of operations, and it
   is the kind of question Week 3's gating makes precise.

</details>

## Why it matters

Averages over everything hide what matters. A static pressure reading near 0 because the fan is off pulls the average
down just like a real problem does. Most of fault detection is asking "the average **of what, when**?" That is
filtering (Days 8–9) and gating (Week 3). Run hours are the first example of a number a building owner actually reads:
hours the fan ran, hours a fault was active, hours of energy at a given load.
