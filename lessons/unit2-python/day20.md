# Day 20 — Scaling showdown, and the Week 4 challenge

**Goal:** run Day 14's FC1 confirmation-streak rule as a plain Python state machine, as vectorized pandas and as
SQLite window SQL on data that grows 10x per step; compare the times and how they grow; and decide, with numbers, when
each one is the right tool.

## Read

This is the same rule as Day 14: raw fault = fan running and duct static more than 25 Pa below setpoint; a fault is
**confirmed** once the raw fault has held for 2 consecutive rows. All the rule's cleverness is in "consecutive":
each row's answer depends on the rows before it. That's the part that makes the tools differ.

| | Plain Python (`day20_pandas.py`) | pandas (`day20_pandas.py`) | SQLite (`day20_sql.py`) |
|---|---|---|---|
| Idea | one pass, a tiny state machine: `streak_len` | column ops: `shift`, `cumsum`, `cumcount` | window functions: `LAG`, `SUM OVER`, `ROW_NUMBER` |
| State | one integer, carried along | none: streak ids are *recomputed* with `cumsum` | none: window frames recompute it |
| Work | 1 pass, interpreter speed | ~5 passes over whole arrays, C speed | sort/partition, several window passes |
| Memory | O(1) (streams the rows) | O(n) (needs all rows in arrays) | the database engine's (not in Python) |
| Data starts | in Python objects | has to be loaded first | where it already is |

A state machine is the natural way to say "count consecutive rows" in a loop, and the awkward way to say it in
column operations (Day 13 needed a trick: compare with the previous row, running-sum the changes). SQL and pandas are
both doing that trick. Whether the trick costs more than the interpreter overhead is what the tables below show.

The data is `lab.synthetic_history`, the same rows in both scripts. The loop in `day20_pandas.py` resets its state when
the AHU changes (like `PARTITION BY` does for SQL), so it can be checked row by row on two AHUs.

## Run

```bash
uv run python lessons/course.py run 20
```

That runs [`day20_pandas.py`](day20_pandas.py) (the loop and the pandas rule), then [`day20_sql.py`](day20_sql.py) (the
window SQL). It is the longest pair of the week (about 35 seconds in all: the million-row steps dominate). `RESULTS`
in both holds `per_row` (every row's confirmed-fault flag on two AHUs of 5,000 rows), `totals_by_size`
(confirmed rows and episodes at every benchmark size), `first_fault` (the first confirmed fault in a table) and
`longest_episode` (the challenge below). Compared with each other by the unit test; you compare the timings.

Both scripts print the totals at every size, the same in both:

```
   rows  fault_rows  episodes
   1000          72         1
  10000         479         4
 100000        4924        36
1000000       49684       348
```

`streak_id` restarts at 1 for each AHU (the window is partitioned), so counting episodes across AHUs needs
`COUNT(DISTINCT equipment_id || ':' || streak_id)` in SQL; counting plain `streak_id` merges different AHUs'
episodes into one. In the loop, the equivalent is the `if eq != cur_eq:` reset at the top of the body: without it, a
streak at the end of AHU_1 would carry into the start of AHU_2.

**The showdown.** Synthetic data, 10x more rows each step, one AHU. SQL loading is **setup** and timed apart from the
query (`sql_load`). On the machine this was written on (seconds):

```
              loop    pandas              (day20_pandas.py)
rows
1000     0.0005124  0.002609
10000     0.005097  0.003933
100000     0.05864   0.03202
1000000     0.5769    0.2743

         sql_load sql_window              (day20_sql.py)
rows
1000     0.005301   0.005588
10000     0.02772    0.04336
100000     0.2854     0.5476
1000000     3.042      5.953
```

and the growth table each script prints (time at this size over time at the previous, 10x smaller size). How to read
it: about 10 means O(n): ten times the data, ten times the time. Smaller than 10 at the first rows means fixed
overhead (starting a query, allocating arrays) is still a big part of the time. Bigger than 10 would mean worse than
linear: sorting adds a log factor, and once arrays stop fitting in CPU cache each pass slows down. Here, the loop's
growth is 10-12 at every step (1 pass at interpreter speed), pandas is 1.5, then 8, then 9 as it leaves the overhead
regime, and the window SQL is 8 to 13 (that last bit of extra is the sort).

At a million rows: pandas on resident data 0.27 s, the plain loop 0.58 s, window SQL 6.0 s (plus 3.0 s to load it, a
cost Day 16 measured). Three readings of the same table:

- *If the data is already a DataFrame*, pandas wins, by about 2x over the loop. The loop's penalty is smaller than on
  Day 16's trivial counting because a state machine is *one* pass, while the pandas version needs several full-array
  passes (`shift`, `ne`, `cumsum`, `groupby.cumcount`). The vectorized version is still quicker, but not by 50x.
- *If the data lives in the database*, add Day 16's cost of moving it out (2.5 s for a million rows) to the pandas
  number before comparing; the loop pays a similar price to pull rows out of a cursor.
- *Window SQL is the slowest of all here*, about 20x pandas and 10x the loop: SQLite sorts the rows, then makes four
  window passes, each of which materializes intermediate rows. SQL's strength is not this kind of row-to-row logic. It
  is the *selective* query that an index answers without reading most of the table (Day 12), and the aggregate that
  runs where the data is (Day 16).

**So when does each one win?**

- **SQL** when the data already lives in the database and you want a small answer: a total, a top-10, one
  AHU's last week. The index finds the rows without reading the rest (Day 12), nothing is copied into Python, and the
  result is one small table. Also when many people or programs need the same logic: the query ships with the data.
  It loses on cost-per-row for complicated row-to-row logic, and it is awkward to step through.
- **pandas** for in-memory column math and exploratory work: it is the fastest once the data is in arrays, and
  the interactive loop (change a line, look at a plot) is why it's the oracle in Open-FDD's parity tests. It loses
  when the data doesn't fit in memory (Day 17), or when moving the data in costs more than the calculation (Day 16).
- **A plain loop** when the data streams past once and the state is complicated or the data is small: it needs O(1)
  memory (Day 17), it can **stop early** (next), and a state machine with ten fields is easier to read than ten window
  functions. Its per-row cost is high, but it is flat. If a loop is the right *shape* and merely slow, tools like numba
  or Cython compile exactly this kind of loop to machine code; that's a story for another course.

Open-FDD ships the pandas version as the reference and the SQL version where the data lives. Both are correct, and the
parity test is what lets you pick per situation.

## Try it

**Stop early.** How long does each version take to find the *first* confirmed fault timestamp in a 200,000-row table
(20,000 under the test)? Compare the loop that returns at the first hit with the loop that reads everything, with
pandas, and with the window SQL. The scripts print it, and both find the same timestamp (`first_fault`).

<details><summary>Answer</summary>

On the machine this was written on, for 200,000 rows:

```
loop, early exit               0.0389 s
loop, whole table              0.1198 s
pandas (computes every row)    0.0745 s
SQL, MIN(ts) over the faults   1.0152 s       (the totals query: 1.0804 s)
```

The early-exit loop does a fraction of the work, because the first confirmed fault is about a third of the way into
the table (that is where the synthetic weak-fan window starts), so two thirds are never read. It is faster than the
vectorized pandas version here, though pandas beats the full loop. pandas and the window SQL have no equivalent:
they compute every row's state before you can ask for the first. `SELECT MIN(ts)` takes as long as the whole query (and
a `LIMIT 1` would not help for the same reason). Early exit is the loop's unique strength: it would matter far more if
the first fault were near the start or each row cost a network call. The loop's win is in *not needing the rest of
the data at all*.

</details>

## Week 4 challenge

Find the **longest confirmed fault episode** for each AHU: its length in rows and in minutes, on a table with two AHUs
of 20,000 rows each (5,000 under the test). An episode is a maximal run of consecutive raw-fault rows that lasts at
least `CONFIRM` rows. Implement it three ways, and say which one you would ship if the data were (a) one building's
database, (b) a notebook of a month of data, (c) a stream on a controller.

- **Loop** (`longest_loop` in `day20_pandas.py`): a streaming loop that tracks the current and the best run, per AHU.
- **pandas** (`longest_pandas`): the size of each streak with `groupby([eq, streak])`, keep the raw-fault ones that
  last long enough, take the max per AHU.
- **SQL** (`LONGEST_SQL` in `day20_sql.py`): `GROUP BY equipment_id, streak_id HAVING COUNT(*) >= :confirm`, then `MAX`.

Both scripts print the same table (`longest_episode` in `RESULTS`), and the pandas script also checks its loop and
pandas versions agree:

```
equipment_id  longest_rows  longest_min
       AHU_1           144        720.0
       AHU_2           144        720.0
```

<details><summary>Answer</summary>

Both AHUs have a longest episode of 144 rows = 12 hours: the 12-hour fan schedule (06:00-18:00) lies entirely inside
the weak-fan window, so the whole run is one episode (synthetic data: a real building would be messier).

The key step in all three is the same trick as Day 14: a new streak starts where the raw flag changes, the running sum of
starts numbers the streaks, and the size of a streak is its length. In pandas that is `raw.ne(raw.groupby(eq).shift())`
then `cumsum`; in SQL `LAG` then `SUM() OVER`; in the loop, `run = run + 1 if raw == prev_raw else 1`.

Which to ship: (a) one building's database: **SQL**, next to the data, with an index, returning two numbers.
(b) a notebook with a month of data: **pandas**, because you'll want to plot the episodes next. (c) a stream on a
controller: the **loop**, with O(1) memory and early updates the moment each episode ends. All three give the same
answer, which is the point of having two scripts to compare.

</details>

Week 4 in one sentence: the answer is the same everywhere, and *where the data is, how much of it you hold in memory,
and what shape the logic has* decide which tool gets there cheapest.
