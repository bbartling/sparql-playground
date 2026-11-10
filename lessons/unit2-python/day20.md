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
| Idea | one pass, a tiny state machine: `streak_length` | column ops: `shift`, `cumsum`, `cumcount` | window functions: `LAG`, `SUM OVER`, `ROW_NUMBER` |
| State | one integer, carried along | none: streak ids are *recomputed* with `cumsum` | none: window frames recompute it |
| Work | 1 pass, interpreter speed | ~5 passes over whole arrays, C speed | sort/partition, several window passes |
| Memory | O(1) (streams the rows) | O(n) (needs all rows in arrays) | the database engine's (not in Python) |
| Data starts | in Python objects | has to be loaded first | where it already is |

A state machine is the natural way to say "count consecutive rows" in a loop, and the awkward way to say it in
column operations (Day 13 needed a trick: compare with the previous row, running-sum the changes). SQL and pandas are
both doing that trick. Whether the trick costs more than the interpreter overhead is what the tables below show.

The data is Day 16's synthetic AHUs, the same rows in both scripts. The showdown uses AHU_1 only, so the loop never
has to notice a change of AHU; the challenge at the end takes both AHUs, one at a time in pandas and with
`PARTITION BY equipment_id` in SQL.

## Run

```bash
uv run python lessons/course.py run 20
```

That runs [`day20_pandas.py`](day20_pandas.py) (the loop and the pandas rule), then [`day20_sql.py`](day20_sql.py) (the
window SQL). It is the longest pair of the week (several seconds each). `RESULTS` in both holds `totals_by_size`
(confirmed rows and episodes at every size), `first_fault_ts` (the first confirmed fault) and `longest_episode` (the
challenge below). The unit test compares them; you compare the timings. The pandas script prints:

```
rows: 1000 | fault rows: 286 | episodes: 2
  loop agrees: True
  seconds: loop 0.0001 | pandas 0.0014
rows: 10000 | fault rows: 1430 | episodes: 10
  loop agrees: True
  seconds: loop 0.0013 | pandas 0.0013
rows: 100000 | fault rows: 14300 | episodes: 100
  loop agrees: True
  seconds: loop 0.012 | pandas 0.0059
rows: 500000 | fault rows: 70928 | episodes: 496
  loop agrees: True
  seconds: loop 0.0588 | pandas 0.0343
```

and the SQL script the same counts with its own timing (on the machine this was written on):

```
rows: 100000 | fault rows: 14300 | episodes: 100
  seconds: window SQL 0.2479
rows: 500000 | fault rows: 70928 | episodes: 496
  seconds: window SQL 1.2679
```

**Reading the timings.** Times vary by machine and run, so they are printed, never compared. Down the sizes, about
10x per 10x of rows means O(n). Less than that at the small sizes means fixed overhead (starting a query, allocating
arrays) is still a big part of the time; more than that would mean worse than linear (sorting adds a log factor). The
loop grows about 10x per step from the start; pandas barely grows at first (overhead), then about 5x per 5x; the
window SQL about 10x per step.

At 500,000 rows: pandas on data already in memory 0.034 s, the plain loop 0.059 s, window SQL 1.27 s. Three readings
of the same numbers:

- *If the data is already a DataFrame*, pandas wins, but only by about 2x over the loop. The loop's penalty is smaller
  than on Day 16's plain counting would suggest, because a state machine is *one* pass, while the pandas version needs
  several full-array passes (`shift`, `!=`, `cumsum`, `groupby(...).cumcount()`).
- *If the data lives in the database*, add Day 16's cost of moving it out (about 1.5 s for a million rows) to the
  pandas number before comparing; the loop pays a similar price to pull rows out of a cursor.
- *Window SQL is the slowest here*, about 35x pandas and 20x the loop: SQLite sorts the rows, then makes several
  window passes, each of which materializes intermediate rows (the script also copies the rows into temp tables `h`
  and `fc1` for each size). SQL's strength is not this kind of row-to-row logic. It is the *selective* query that an
  index answers without reading most of the table (Day 11), and the aggregate that runs where the data is (Day 16).

**So when does each one win?**

- **SQL** when the data already lives in the database and you want a small answer: a total, a top-10, one
  AHU's last week. The index finds the rows without reading the rest (Day 11), nothing is copied into Python, and the
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

**Stop early.** Step 3 finds the *first* confirmed fault in AHU_1's first 200,000 rows: the loop stops (`break`) at
the first hit, pandas and the window SQL compute every row first. All three find the same timestamp. Compare their
times, then delete the `break` (so the loop reads the whole table) and compare again.

<details><summary>Answer</summary>

The scripts print:

```
First confirmed fault in 200,000 rows: ts 1773727500
  pandas finds the same one: True
  seconds: loop with early exit 0.0001
  seconds: pandas (computes every row first) 0.0125
```

and `seconds: window SQL 0.4939`. The first confirmed fault is row 361 (ts 1773727500 is 108,300 s, about 30 hours,
after the start), so the loop reads 361 rows of 200,000 and stops: about 100x faster than pandas, and thousands of
times faster than SQL. pandas and the window SQL have no equivalent: they compute every row's state before you can
ask for the first. `SELECT MIN(ts)` takes as long as the whole query (and a `LIMIT 1` would not help for the same
reason). Without the `break` the loop reads all 200,000 rows, about twice the 100,000-row time above, and it is
slower than pandas again. The loop's win is in *not needing the rest of the data at all*, which matters most when
the answer is near the start or each row costs a network call.

</details>

## Week 4 challenge

Find the **longest confirmed fault episode** for each AHU: its length in rows and in minutes, in the first 20,000
rows of each AHU. An episode is a maximal run of consecutive raw-fault rows that lasts at least `CONFIRM_ROWS` rows.
Implement it three ways, and say which one you would ship if the data were (a) one building's database, (b) a
notebook of a month of data, (c) a stream on a controller.

- **pandas** (step 4 in `day20_pandas.py`): number the streaks, get the size of each with `groupby("streak_id")`,
  keep the raw-fault ones that last long enough, take the max, for each AHU in turn.
- **SQL** (step 4 in `day20_sql.py`): `GROUP BY equipment_id, streak_id HAVING COUNT(*) >= :confirm_rows`, then `MAX`.
- **Loop** (your turn): a streaming loop that tracks the current and the best run.

Both scripts print the same table (`longest_episode` in `RESULTS`):

```
equipment_id  longest_rows  longest_min
       AHU_1           144          720
       AHU_2           144          720
```

<details><summary>Answer</summary>

Both AHUs have a longest episode of 144 rows = 12 hours: the 12-hour fan schedule (06:00-18:00) lies entirely inside
the weak-fan window, so the whole run is one episode (synthetic data: a real building would be messier).

The key step in all three is the same trick as Day 14: a new streak starts where the raw flag changes, the running sum
of starts numbers the streaks, and the size of a streak is its length. In pandas that is `(raw != raw.shift()).cumsum()`;
in SQL `LAG` then `SUM() OVER`; in the loop, step 2a's `streak_length`, plus one more variable:

```python
longest = 0
for i in range(n):
    # ... step 2a's lines that update raw and streak_length ...
    if raw and streak_length >= CONFIRM_ROWS and streak_length > longest:
        longest = streak_length
```

Which to ship: (a) one building's database: **SQL**, next to the data, with an index, returning two numbers.
(b) a notebook with a month of data: **pandas**, because you'll want to plot the episodes next. (c) a stream on a
controller: the **loop**, with O(1) memory and early updates the moment each episode ends. All three give the same
answer, which is the point of having two scripts to compare.

</details>

Week 4 in one sentence: the answer is the same everywhere, and *where the data is, how much of it you hold in memory,
and what shape the logic has* decide which tool gets there cheapest.
