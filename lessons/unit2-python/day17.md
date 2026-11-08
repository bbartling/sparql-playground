# Day 17 — Memory: lists, generators, DataFrames and chunks

**Goal:** measure how much memory the same rows cost as a list, as a stream and as a DataFrame; shrink the DataFrame
with better dtypes; and aggregate a big table in memory proportional to a chunk, not to the table.

## Read

Day 16 was about time. The other way a job fails is **memory**: the laptop swaps, or the container is killed. An FDD
job over a year of 5-minute data on a hundred AHUs is tens of millions of rows. Ways to hold the rows:

| Shape | What Python holds | Memory grows with |
|---|---|---|
| a `list` of tuples (`fetchall()`) | every row as a tuple of float objects | rows (and a lot of it per row) |
| a stream (`for row in cursor`, or `zip` over columns) | one tuple at a time | nothing: O(1) |
| a DataFrame (`read_csv`, `read_sql_query`) | NumPy arrays, one per column | rows x bytes per value |
| a chunked read (`chunksize=`) | one chunk of arrays at a time | the chunk size |
| a SQL aggregate | the answer (a couple of rows) | nothing: SQLite holds the data |

A Python float is a 24-byte object, plus an 8-byte pointer in the tuple, plus the tuple's own header. A NumPy
`float64` is 8 bytes, period. That's why DataFrames beat lists of tuples for numbers. But the DataFrame is still
O(rows), and for text columns it's much worse: an `object` column stores a pointer per row to a separate Python
string.

Two memory-saving moves, and one honest warning:

- **Right-size the dtypes.** `equipment_id` has 2 distinct values in 200,000 rows: store it as `category` (small
  integer codes plus one lookup table). A 0/1 status fits in `int8`. `float32` halves a column, but has only about
  7 significant digits. That's fine for a temperature, risky for an epoch timestamp, and always something to *check*
  rather than assume.
- **Stream in chunks.** If the answer is an aggregate (counts, sums, a few rows per equipment), you never need the
  whole table in memory. Read a chunk, fold it into running totals, throw it away. Peak memory is O(chunk), and the
  result is the same as one big aggregate. Because sums and counts are *associative*, summing the chunk sums gives
  the total.
- **Warning:** `lab.peak_mib` uses `tracemalloc`, which sees memory allocated by Python and by NumPy/pandas buffers.
  It does **not** see memory SQLite allocates inside its own C library (page cache, sort buffers, the in-memory
  database itself). A SQL aggregate over 200,000 rows reports about zero because Python really did hold about
  nothing; SQLite's own footprint just isn't measured by it.

The task is the same as Day 16 per AHU: the count of raw FC1 faults (fan running, static more than 25 Pa below
setpoint), plus run hours. The data is `lab.synthetic_history(100_000, equips=2)` (20,000 rows per AHU under the
test): two AHUs, identical in both scripts.

## Run

```bash
uv run python lessons/course.py run 17
```

That runs [`day17_pandas.py`](day17_pandas.py), then [`day17_sql.py`](day17_sql.py). The plain-Python ways of holding
rows live in the pandas script; the SQL script is the aggregate, plus the cost of pulling the rows out of SQLite.

| Step | `day17_pandas.py` | `day17_sql.py` |
|---|---|---|
| reference answer | `hits(df).groupby(df.equipment_id).sum()` | `SUM(fan_status = 1 AND ...) ... GROUP BY equipment_id` |
| rows as a list | `list(df.itertuples(index=False, name=None))` | `cursor.fetchall()` (transfer only) |
| rows as a stream | `for ... in zip(*(df[c] for c in COLS))` | `for _ in cursor` (transfer only) |
| whole DataFrame | `pd.read_csv(path)` | `pd.read_sql_query(ROWS_SQL, conn)` |
| smaller dtypes | `astype({"equipment_id": "category", "duct_static": "float32", ...})` | (SQLite stores what it stores) |
| chunks | `pd.read_csv(path, chunksize=CHUNK)`, fold the partial sums | `read_sql_query(..., chunksize=CHUNK)` (transfer only) |
| answers kept | `fault_counts`, `fault_hours` | `fault_counts`, `fault_hours` |

The pandas script writes the synthetic rows to a temporary CSV, so its chunked read is a real file read. The SQL
script's rows live in SQLite, so its chunked read comes from the database. Both print the per-AHU answer:

```
equipment_id  fault_rows  run_hours
       AHU_1        4993     4164.0
       AHU_2        5081     4164.0
```

Then the memory tables (MiB of Python heap at the peak; the numbers vary a little by Python version, but not by much):

```
        approach  peak_MiB             (day17_pandas.py)
  list of tuples     36.49
    stream (zip)      0.00
  read whole CSV     15.67
chunked CSV read      2.25

                   approach  peak_MiB (day17_sql.py)
SQL aggregate (2 rows back)     0.008
              fetchall list    45.414
              cursor stream     0.001
       read_sql_query whole    67.012
     read_sql_query chunked     6.189
```

Three things to see.

- **The stream is flat.** The loop holds one tuple, so its peak is about zero. Streaming trades speed for space (the
  interpreter loop is Day 16's slow one), but its memory cost is nothing.
- **A DataFrame's peak can be higher than its resting size.** `read_csv` parses straight into arrays (15.7 MiB). But
  `read_sql_query` has to fetch every row as Python tuples first and then convert them into column arrays, so for a
  moment both copies exist: 67 MiB, more than the 45 MiB list on its own. `chunksize` fixes that: 6 MiB, about a
  tenth of the whole read. Memory now scales with the **chunk**: double the table and the peak stays put (only the loop
  runs longer). The price is that this works for aggregates that can be folded (counts, sums, min/max). A rolling
  window or a streak that crosses a chunk boundary needs the chunks to carry state across, which is what Day 18's
  loop does naturally.
- **The SQL aggregate is the cheapest in Python memory**, 0.008 MiB: Python holds a 2-row result while SQLite scans
  every row. But that number is incomplete: it's the Python side. SQLite's own memory (the page cache, and here the
  entire in-memory database, 11.3 MiB as the second script prints from `PRAGMA page_count * page_size`) is invisible to
  `tracemalloc`. To see it you would watch the process, for example with `psutil`'s resident set size.

**Shrinking the DataFrame.** `memory_usage(deep=True)` counts the real bytes, including the Python objects behind an
`object` column. The pandas script prints the table:

```
                before_MiB  after_MiB
equipment_id         10.30       0.19
ts                    1.53       1.53
fan_status            1.53       0.19
duct_static           1.53       0.76
duct_static_sp        1.53       0.76
total                16.40       3.43
```

The big win is `equipment_id`: an `object` column of strings becomes a column of 1-byte codes. The float columns
halve, the flag drops 8x, and `ts` stays `int64` (epoch seconds need 32+ bits, and `float32` would corrupt them).
`float32` changed the *values*, so the script checks that the fault decision survives: it prints
`float32 flipped 0 of 200,000 fault decisions`. On this data no row flips: the readings carry two decimals and the
threshold is a round number, so float32's rounding (about 3e-5 at 350 Pa) never crosses it. On data that sits *exactly
on* a threshold, it could. Checking is how you find out, and why Open-FDD keeps one declared scale and dtype per
column instead of guessing.

## Try it

1. How big would the full DataFrame be for 100 AHUs x 1 year of 5-minute data (about 105,000 rows each) with five
   float64 columns plus an int64 `ts`? Compute it from the table above, no new data needed.
2. The chunked read in `day17_pandas.py` also returns run hours per AHU (`fan_status == 1` rows x 5 / 60), and
   `fault_hours` in `RESULTS` is compared with the SQL aggregate. Why is *run hours* easy to fold across chunks, and
   what about a median duct static?

<details><summary>Answers</summary>

1. Bytes per row of the numeric columns, times rows:

   ```python
   numeric_bytes_per_row = 8 * 5 + 8  # five float64 + one int64
   rows_total = 100 * 105_000
   gib = rows_total * numeric_bytes_per_row / 2**30  # about 0.47 GiB
   ```

   About 0.5 GiB for 10.5 million rows: fine on a laptop, but tens of GiB across a portfolio of buildings. That is
   where chunking, dtypes and "let the database aggregate" stop being optional.
2. The partial results are small tables you can add: sums add. `faults_and_hours()` keeps a `fault_rows` and a
   `run_rows` column per chunk, adds the chunks' tables, and converts rows to hours at the end. A *mean* you'd carry
   as (sum, count) and divide at the end; a median doesn't fold this way at all.

</details>

## Why it matters

Memory decides where a rule can run. A rule that needs the whole table as a DataFrame fits a laptop but not an edge
controller (Normal Framework on a Raspberry Pi 3 has under 1 GB for everything). Streaming and chunking are what let
the same logic run in both places. Day 20 puts time and memory side by side.
