# Day 17 — Memory: lists, generators, DataFrames and chunks

**Goal:** measure how much memory the same query result costs as a list, as a stream and as a DataFrame; shrink the
DataFrame with better dtypes; and aggregate a big result in memory proportional to a chunk, not to the table.

## Read

Day 16 was about time. The other way a job fails is **memory**: the laptop swaps, or the container is killed. An FDD
job over a year of 5-minute data on a hundred AHUs is tens of millions of rows. Three ways to hold a query result:

| Shape | What Python holds | Memory grows with |
|---|---|---|
| `cursor.fetchall()` | a `list` of tuples, each tuple holding float objects | rows (and a lot of it per row) |
| `for row in cursor` | one tuple at a time (a **generator**-style stream) | nothing: O(1) |
| `pd.read_sql_query(...)` | NumPy arrays, one per column (but a list of tuples exists while loading) | rows x bytes per value |

A Python float is a 24-byte object, plus an 8-byte pointer in the tuple, plus the tuple's own header. A NumPy
`float64` is 8 bytes, period. That's why DataFrames beat lists of tuples for numbers. But the DataFrame is still O(rows),
and for text columns it's much worse: an `object` column stores a pointer per row to a separate Python string.

Two memory-saving moves, and one honest warning:

- **Right-size the dtypes.** `equipment_id` has 2 distinct values in 1 million rows: store it as `category` (small
  integer codes plus one lookup table). A 0/1 status fits in `int8`. `float32` halves a column, but has only about
  7 significant digits. That's fine for a temperature, risky for an epoch timestamp, and always something to *check*
  with parity rather than assume.
- **Stream in chunks.** If the answer is an aggregate (counts, sums, a few rows per equipment), you never need the
  whole table in memory. Read 50,000 rows, fold them into running totals, throw them away. Peak memory is
  O(chunk), and the result is the same as one big aggregate. Because sums and counts are *associative*, summing the
  chunk sums gives the total.
- **Warning:** `lab.peak_mib` uses `tracemalloc`, which sees memory allocated by Python and by NumPy/pandas buffers.
  It does **not** see memory SQLite allocates inside its own C library (page cache, sort buffers, the in-memory
  database itself). A SQL aggregate over a million rows reports about zero because Python really did hold about
  nothing; SQLite's own footprint just isn't measured here.

## Run

```python
import sqlite3

import numpy as np
import pandas as pd

import lab

conn = lab.connect()

N = 20_000 if lab.QUICK else 200_000  # rows per AHU; two AHUs
TOL_PA = 25.0

df_src = lab.synthetic_history(N, equips=2)
mem = sqlite3.connect(":memory:")
lab.to_sqlite(df_src, mem, "h", index=["equipment_id", "ts"])
print(f"{len(df_src):,} rows in table h")

ROWS_SQL = "SELECT equipment_id, ts, fan_status, duct_static, duct_static_sp FROM h"
```

The task for every version: the count of raw FC1 faults (running, static more than 25 Pa below setpoint) per AHU.
First the **reference answer**, one SQL aggregate:

```python
AGG_SQL = """
SELECT equipment_id,
       SUM(fan_status = 1 AND duct_static < duct_static_sp - :tol) AS fault_rows
FROM h GROUP BY equipment_id ORDER BY equipment_id
"""
ref = lab.query(mem, AGG_SQL, {"tol": TOL_PA})
print(ref.to_string(index=False))
assert (ref.fault_rows > 0).all()
```

**Three ways to hold the rows.** Each function returns the same per-AHU counts; `lab.peak_mib` reports the peak
Python-heap memory while it runs.

```python
def counts_fetchall():
    rows = mem.execute(ROWS_SQL).fetchall()  # list of N tuples, all alive at once
    out = {}
    for eq, _ts, fan, static, sp in rows:
        out[eq] = out.get(eq, 0) + (1 if fan == 1 and static < sp - TOL_PA else 0)
    return out


def counts_stream():
    out = {}
    for eq, _ts, fan, static, sp in mem.execute(ROWS_SQL):  # one tuple at a time
        out[eq] = out.get(eq, 0) + (1 if fan == 1 and static < sp - TOL_PA else 0)
    return out


def counts_dataframe():
    d = pd.read_sql_query(ROWS_SQL, mem)  # whole result as NumPy arrays
    hit = (d.fan_status == 1) & (d.duct_static < d.duct_static_sp - TOL_PA)
    return hit.groupby(d.equipment_id).sum().to_dict()


results = {
    "fetchall list": counts_fetchall,
    "cursor stream": counts_stream,
    "DataFrame": counts_dataframe,
}
mem_rows = []
for name, fn in results.items():
    got = fn()
    lab.assert_parity(
        pd.DataFrame({"equipment_id": list(got), "fault_rows": list(got.values())}), ref, label=name
    )
    mem_rows.append({"approach": name, "peak_MiB": lab.peak_mib(fn)})
mem_table = pd.DataFrame(mem_rows)
print(mem_table.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
peak = mem_table.set_index("approach").peak_MiB
assert peak["cursor stream"] < peak["fetchall list"] / 20
assert peak["DataFrame"] > peak["cursor stream"] * 20
```

Two surprises. The stream is flat: the loop holds one tuple, so its peak is about zero. And the DataFrame *peaks
higher* than the list, even though the finished DataFrame is much smaller than the list. `read_sql_query` has to
fetch every row as Python tuples first and then convert them into column arrays, so for a moment both copies exist.
The resting size of a DataFrame is small (next), but the peak while loading it is not. That is exactly what
`chunksize` fixes, below. The time cost of the stream is the interpreter loop from Day 16; its memory cost is zero.
Streaming trades speed for space.

And the SQL aggregate itself, for contrast. Python holds one 2-row result while SQLite scans every row:

```python
sql_peak = lab.peak_mib(lambda: lab.query(mem, AGG_SQL, {"tol": TOL_PA}))
print(f"SQL aggregate peak (Python heap only): {sql_peak:.3f} MiB")
assert sql_peak < peak["cursor stream"] + 1
```

That number is real but incomplete: it's the Python side. SQLite's own memory (the page cache, and here the entire
in-memory database) is invisible to `tracemalloc`. To see it you would watch the process, for example with `psutil`'s
resident set size, rather than the Python allocator.

**Shrinking the DataFrame.** `memory_usage(deep=True)` counts the real bytes, including the Python objects behind an
`object` column. Shallow `memory_usage()` would only count the pointers and badly under-report text.

```python
d = pd.read_sql_query(ROWS_SQL, mem)
before = d.memory_usage(deep=True)
print(d.dtypes.to_dict())

small = d.astype(
    {
        "equipment_id": "category",
        "fan_status": "int8",  # a 0/1 flag
        "duct_static": "float32",
        "duct_static_sp": "float32",
    }
)  # ts stays int64: epoch seconds (about 1.8e9) need 32+ bits, and float32 would corrupt them
after = small.memory_usage(deep=True)
cmp = pd.DataFrame({"before_MiB": before / 2**20, "after_MiB": after / 2**20}).drop(index="Index")
cmp.loc["total"] = cmp.sum()
print(cmp.round(2).to_string())
assert after.sum() < before.sum() * 0.5
assert before["equipment_id"] > 10 * after["equipment_id"]  # text object column vs category codes
```

The big win is `equipment_id`: an `object` column of strings becomes a column of 1-byte codes. The float columns halve.
Now the check that matters, because `float32` changed the *values*: does the fault answer survive?

```python
hit64 = (d.fan_status == 1) & (d.duct_static < d.duct_static_sp - TOL_PA)
hit32 = (small.fan_status == 1) & (small.duct_static < small.duct_static_sp - np.float32(TOL_PA))
small_counts = hit32.groupby(small.equipment_id, observed=True).sum()
lab.assert_parity(
    small_counts.rename("fault_rows").reset_index(),
    ref,
    label="float32 / int8 / category DataFrame",
)
print("float32 flips:", int((hit64 != hit32).sum()), "rows of", len(d))
print("mean static, float64 vs float32:", d.duct_static.mean(), small.duct_static.mean())
assert int((hit64 != hit32).sum()) == 0
```

On this data no row flips: the readings carry two decimals and the threshold is a round number, so float32's rounding
(about 3e-5 at 350 Pa) never crosses it. On data that sits *exactly on* a threshold, it could. The parity check is how
you find out, and why Open-FDD keeps one declared scale and dtype per column instead of guessing.

**Chunked reads.** The aggregate we want never needs the table in memory at once. `chunksize` makes
`read_sql_query` return an iterator of DataFrames; we fold each chunk into running totals. Parity against the SQL
aggregate shows nothing was lost.

```python
CHUNK = N // 8


def counts_chunked():
    total = pd.Series(dtype="int64")
    for chunk in pd.read_sql_query(ROWS_SQL, mem, chunksize=CHUNK):  # an iterator of DataFrames
        hit = (chunk.fan_status == 1) & (chunk.duct_static < chunk.duct_static_sp - TOL_PA)
        total = total.add(
            hit.groupby(chunk.equipment_id).sum(), fill_value=0
        )  # associative: add the partials
    return total.astype("int64").to_dict()


got = counts_chunked()
lab.assert_parity(
    pd.DataFrame({"equipment_id": list(got), "fault_rows": list(got.values())}),
    ref,
    label="chunked",
)
peak_chunked = lab.peak_mib(counts_chunked)
peak_full = peak["DataFrame"]
print(f"full DataFrame {peak_full:.2f} MiB, chunked ({CHUNK:,} rows) {peak_chunked:.2f} MiB")
assert peak_chunked < peak_full / 2
```

Memory scales with the **chunk** now: double the table and the peak stays put (only the loop runs longer). The price is
that this works for aggregates that can be folded (counts, sums, min/max). A rolling window or a streak that crosses a
chunk boundary needs the chunks to carry state across, which is what Day 18's loop does naturally and why streaming
a state machine is easy in plain Python.

## Try it

1. How big would the full DataFrame be for 100 AHUs x 1 year of 5-minute data (about 105,000 rows each) with five
   float64 columns plus an int64 `ts`? Compute it from `d.memory_usage`, no new data needed.
2. Make the chunked version also return the *run hours* per AHU (`fan_status == 1` rows x 5 / 60) and prove parity
   with a SQL aggregate.

<details><summary>Answers</summary>

```python
# 1. bytes per row of the numeric columns, times rows
numeric_bytes_per_row = 8 * 5 + 8  # five float64 + one int64
rows_total = 100 * 105_000
gib = rows_total * numeric_bytes_per_row / 2**30
print(
    f"{rows_total:,} rows x {numeric_bytes_per_row} B = {gib:.2f} GiB (plus the equipment_id column)"
)
assert 0.4 < gib < 0.6


# 2. chunked counts and run hours, folded together
def faults_and_hours():
    total = None
    for chunk in pd.read_sql_query(ROWS_SQL, mem, chunksize=CHUNK):
        running = chunk.fan_status == 1
        part = (
            pd.DataFrame(
                {
                    "fault_rows": (
                        running & (chunk.duct_static < chunk.duct_static_sp - TOL_PA)
                    ).astype(int),
                    "run_rows": running.astype(int),
                }
            )
            .groupby(chunk.equipment_id)
            .sum()
        )
        total = part if total is None else total.add(part, fill_value=0)
    total["run_hours"] = total.run_rows * 5 / 60
    return total.reset_index()[["equipment_id", "fault_rows", "run_hours"]]


sql_both = lab.query(
    mem,
    """SELECT equipment_id, SUM(fan_status = 1 AND duct_static < duct_static_sp - :tol) AS fault_rows,
              SUM(fan_status = 1) * 5 / 60.0 AS run_hours FROM h GROUP BY equipment_id""",
    {"tol": TOL_PA},
)
lab.assert_parity(
    faults_and_hours(), sql_both, keys=["equipment_id"], label="chunked fault rows + run hours"
)
```

1. About 0.5 GiB for 10.5 million rows: fine on a laptop, but tens of GiB across a portfolio of buildings. That is
   where chunking, dtypes and "let the database aggregate" stop being optional.
2. The partial results are small tables you can add: sums add. A *mean* you'd carry as (sum, count) and divide at the
   end; a median doesn't fold this way at all.

</details>

## Why it matters

Memory decides where a rule can run. A rule that needs the whole table as a DataFrame fits a laptop but not an edge
controller (Normal Framework on a Raspberry Pi 3 has under 1 GB for everything). Streaming and chunking are what let
the same logic run in both places. Day 20 puts time and memory side by side.
