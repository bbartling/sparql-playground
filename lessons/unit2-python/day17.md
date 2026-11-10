# Day 17 — Memory: lists, generators, DataFrames and chunks

**Goal:** measure how much memory the same rows cost as a list, as a stream and as a DataFrame; shrink the DataFrame
with better dtypes; and aggregate a big table in memory proportional to a chunk, not to the table.

## Read

Day 16 was about time. The other way a job fails is **memory**: the laptop swaps, or the container is killed. An FDD
job over a year of 5-minute data on a hundred AHUs is tens of millions of rows. Ways to hold the rows:

| Shape | What Python holds | Memory grows with |
|---|---|---|
| a `list` of tuples (`fetchall()`) | every row as a tuple of float objects | rows (and a lot of it per row) |
| a stream (`for row in cursor`, or `for row in df.itertuples()`) | one tuple at a time | nothing: O(1) |
| a DataFrame (`read_csv`, `read_sql_query`) | NumPy arrays, one per column | rows x bytes per value |
| a chunked read (`chunksize=`) | one chunk of arrays at a time | the chunk size |
| a SQL aggregate | the answer (a couple of rows) | nothing: SQLite holds the data |

A Python float is a 24-byte object, plus an 8-byte pointer in the tuple, plus the tuple's own header. A NumPy
`float64` is 8 bytes, period. That's why DataFrames beat lists of tuples for numbers. But the DataFrame is still
O(rows), and for text columns it's much worse: an `object` column stores a pointer per row to a separate Python
string.

Two memory-saving moves, and one honest warning:

- **Right-size the dtypes.** A 0/1 status fits in `int8`. `float32` halves a column, but has only about 7
  significant digits. That's fine for a pressure, risky for an epoch timestamp, and always something to *check*
  rather than assume. A text column with a few distinct values (`equipment_id`) can be stored as `category`: small
  integer codes plus one lookup table.
- **Stream in chunks.** If the answer is an aggregate (counts, sums, a few rows per equipment), you never need the
  whole table in memory. Read a chunk, fold it into running totals, throw it away. Peak memory is O(chunk), and the
  result is the same as one big aggregate. Because sums and counts are *associative*, summing the chunk sums gives
  the total.
- **Warning:** the scripts measure memory with `tracemalloc` (start it, do the work, read the peak). It sees memory
  allocated by Python and by NumPy/pandas buffers. It does **not** see memory SQLite allocates inside its own C
  library (page cache, sort buffers). A SQL aggregate over 100,000 rows reports about zero because Python really did
  hold about nothing; SQLite's own footprint just isn't measured by it.

The task is the same as Day 16: the count of raw FC1 faults (fan running, static more than 25 Pa below setpoint),
plus run hours, on the first 100,000 rows of the synthetic data (all AHU_1), identical in both scripts.

## Run

```bash
uv run python lessons/course.py run 17
```

That runs [`day17_pandas.py`](day17_pandas.py), then [`day17_sql.py`](day17_sql.py). The plain-Python ways of holding
rows live in the pandas script; the SQL script is the aggregate, plus the cost of pulling the rows out of SQLite.

| Step | `day17_pandas.py` | `day17_sql.py` |
|---|---|---|
| answer | 3. `(fan_on & too_low).sum()` | 1. `SUM(fan_status = 1 AND ...)` |
| rows as a list | 1. `list(df.itertuples(index=False, name=None))` | 2. `conn.execute(...).fetchall()` (transfer only) |
| rows as a stream | 2. `for ... in df.itertuples(...)` | 3. `for _ in conn.execute(...)` (transfer only) |
| whole DataFrame | 3. `pd.read_csv(path, nrows=N, usecols=columns)` | 4. `pd.read_sql_query(rows_sql, conn, ...)` |
| chunks | 4. `pd.read_csv(..., chunksize=10_000)`, add up the pieces | 5. `read_sql_query(..., chunksize=10_000)` (transfer only) |
| smaller dtypes | 5. `astype({"fan_status": "int8", "static_pa": "float32", ...})` | (SQLite stores what it stores) |

The pandas script prints (MiB of Python heap at the peak; the numbers vary a little by Python and pandas version):

```
AHU_1, first 100000 rows
  fault rows: 14428
  run hours:  4164.0
Peak Python memory (MiB)
  list of tuples: 11.45
  stream:         0.01
  whole DataFrame: 5.35
  chunked read:   1.5
DataFrame size (MiB): default dtypes 2.29 -> smaller dtypes 0.86
```

and the SQL script:

```
AHU_1, first 100000 rows
  fault rows: 14428
  run hours:  4164.0
Peak Python memory (MiB)
  SQL aggregate:  0.001
  fetchall list:  11.45
  cursor stream:  0.0
  whole DataFrame: 19.14
  chunked read:   2.55
```

Three things to see.

- **The stream is flat.** The loop holds one tuple, so its peak is about zero. Streaming trades speed for space (the
  interpreter loop is Day 16's slow one), but its memory cost is nothing.
- **A DataFrame's peak can be higher than its resting size.** `read_csv` parses straight into arrays (5.4 MiB). But
  `read_sql_query` has to fetch every row as Python tuples first and then convert them into column arrays, so for a
  moment both copies exist: 19 MiB, more than the 11 MiB list on its own. `chunksize` fixes that: about 2.5 MiB.
  Memory now scales with the **chunk**: double the table and the peak stays put (only the loop runs longer). The
  price is that this works for aggregates that can be folded (counts, sums, min/max). A rolling window or a streak
  that crosses a chunk boundary needs the chunks to carry state across, which is what Day 18's loop does naturally.
- **The SQL aggregate is the cheapest in Python memory**, 0.001 MiB: Python holds a 1-row result while SQLite scans
  every row. But that number is incomplete: it's the Python side. SQLite's own memory (its page cache) is invisible
  to `tracemalloc`. To see it you would watch the process, for example with `psutil`'s resident set size.

**Shrinking the DataFrame.** Step 5 stores the flag as `int8` (1 byte instead of 8) and the two pressures as
`float32` (4 instead of 8): 2.29 MiB becomes 0.86 MiB. Epoch timestamps would have to stay `int64` (they need 32+
bits, and `float32` would corrupt them). `float32` changes the *values* slightly (about 3e-5 at 350 Pa), so check that
the fault decision survives (Try it 3). On data that sits *exactly on* a threshold, it could flip. Checking is how
you find out, and why Open-FDD keeps one declared scale and dtype per column instead of guessing.

## Try it

1. How big would the full DataFrame be for 100 AHUs x 1 year of 5-minute data (about 105,000 rows each) with five
   float64 columns plus an int64 `ts`? Work it out from bytes per value, no new data needed.
2. The chunked read adds up `fault_rows` and `run_rows` per chunk. Why is *run hours* easy to fold across chunks,
   and what about a median duct static?
3. After step 5, count the fault rows again on `small` and compare with `fault_rows`. How many decisions flipped?

<details><summary>Answers</summary>

1. Bytes per row of the numeric columns, times rows:

   ```python
   numeric_bytes_per_row = 8 * 5 + 8  # five float64 + one int64
   rows_total = 100 * 105_000
   gib = rows_total * numeric_bytes_per_row / 2**30  # about 0.47 GiB
   ```

   About 0.5 GiB for 10.5 million rows: fine on a laptop, but tens of GiB across a portfolio of buildings. That is
   where chunking, dtypes and "let the database aggregate" stop being optional.
2. Sums add: each chunk's run rows plus the next chunk's is the total, and hours = rows x 5 / 60 at the end. A
   *mean* you'd carry as (sum, count) and divide at the end; a median doesn't fold this way at all.
3. None: `((small["fan_status"] == 1) & (small["static_pa"] < small["setpoint_pa"] - TOLERANCE_PA)).sum()` is also
   14,428. The readings carry two decimals and the threshold is a round number, so float32's rounding never crosses
   it.

</details>

## Why it matters

Memory decides where a rule can run. A rule that needs the whole table as a DataFrame fits a laptop but not an edge
controller (Normal Framework on a Raspberry Pi 3 has under 1 GB for everything). Streaming and chunking are what let
the same logic run in both places. Day 20 puts time and memory side by side.
