"""Day 17, pandas side: how much memory the same rows cost as a list, a stream and a DataFrame.

    uv run python lessons/unit2-python/day17_pandas.py

The task for every version is the same: the count of raw FC1 faults (fan running, duct static more
than 25 Pa below setpoint) per AHU, plus run hours. Same synthetic rows as day17_sql.py (two AHUs).

The Python-side versions live here: a list of tuples, a lazy stream, a whole DataFrame, a DataFrame
with smaller dtypes, and a chunked read that never holds the whole table. Compare with day17_sql.py.
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lessons"))
import lab  # noqa: E402

TOL_PA = 25.0  # how far below setpoint counts as a fault
N = 20_000 if lab.QUICK else 100_000  # rows per AHU; two AHUs
CHUNK = N // 8  # rows per chunk when reading in pieces
COLS = ["equipment_id", "ts", "fan_status", "duct_static", "duct_static_sp"]

# 1. Data: the same synthetic history as the SQL script. We also write it to a CSV so we can show
#    a real chunked read (SQL's cursor has its own way, see day17_sql.py).
df = lab.synthetic_history(N, equips=2)[COLS]
tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
csv_path = Path(tmp.name) / "h.csv"
df.to_csv(csv_path, index=False)
print(f"{len(df):,} rows")


# 2. The reference answer: the whole DataFrame in memory, one groupby
def hits(d, tol=TOL_PA):
    return (d.fan_status == 1) & (d.duct_static < d.duct_static_sp - tol)


fault_counts = (
    hits(df).groupby(df.equipment_id).sum().astype("int64").rename("fault_rows").reset_index()
)
print(fault_counts.to_string(index=False))


# 3. Three ways to hold the rows. Each returns the same per-AHU counts; peak_mib measures the
#    Python-heap peak while it runs.
def counts_list():
    rows = list(df.itertuples(index=False, name=None))  # a list of N tuples, all alive at once
    out = {}
    for eq, _ts, fan, static, sp in rows:
        out[eq] = out.get(eq, 0) + (1 if fan == 1 and static < sp - TOL_PA else 0)
    return out


def counts_stream():
    out = {}
    for eq, _ts, fan, static, sp in zip(*(df[c] for c in COLS), strict=True):  # one row at a time
        out[eq] = out.get(eq, 0) + (1 if fan == 1 and static < sp - TOL_PA else 0)
    return out


def counts_dataframe():
    d = pd.read_csv(csv_path)  # the whole file as NumPy arrays
    return hits(d).groupby(d.equipment_id).sum().to_dict()


approaches = {
    "list of tuples": counts_list,
    "stream (zip)": counts_stream,
    "read whole CSV": counts_dataframe,
}
mem_rows, agree = [], {}
for name, fn in approaches.items():
    got = fn()
    agree[name] = {k: int(v) for k, v in got.items()} == dict(
        zip(fault_counts.equipment_id, fault_counts.fault_rows, strict=True)
    )
    mem_rows.append({"approach": name, "peak_MiB": lab.peak_mib(fn)})


# 4. Shrinking the DataFrame. memory_usage(deep=True) counts the real bytes, including the Python
#    objects behind an `object` column.
d = pd.read_csv(csv_path)
before = d.memory_usage(deep=True)
small = d.astype(
    {
        "equipment_id": "category",  # 2 distinct values -> 1-byte codes plus a lookup table
        "fan_status": "int8",  # a 0/1 flag
        "duct_static": "float32",
        "duct_static_sp": "float32",
    }
)  # ts stays int64: epoch seconds (~1.8e9) need 32+ bits, and float32 would corrupt them
after = small.memory_usage(deep=True)
sizes = pd.DataFrame({"before_MiB": before / 2**20, "after_MiB": after / 2**20}).drop(index="Index")
sizes.loc["total"] = sizes.sum()
hit64 = hits(d)
hit32 = (small.fan_status == 1) & (small.duct_static < small.duct_static_sp - np.float32(TOL_PA))
flips = int((hit64 != hit32).sum())


# 5. Chunked read: fold each chunk into running totals, never hold the whole table.
def faults_and_hours():
    total = None
    for chunk in pd.read_csv(csv_path, chunksize=CHUNK):  # an iterator of DataFrames
        part = (
            pd.DataFrame(
                {
                    "fault_rows": hits(chunk).astype(int),
                    "run_rows": (chunk.fan_status == 1).astype(int),
                }
            )
            .groupby(chunk.equipment_id)
            .sum()
        )
        total = part if total is None else total.add(part, fill_value=0)  # sums are associative
    total["run_hours"] = total.run_rows * 5 / 60
    total["fault_rows"] = total.fault_rows.astype("int64")
    return total.reset_index()[["equipment_id", "fault_rows", "run_hours"]]


fault_hours = faults_and_hours()
mem_rows.append({"approach": "chunked CSV read", "peak_MiB": lab.peak_mib(faults_and_hours)})
mem_table = pd.DataFrame(mem_rows)

RESULTS = {"fault_counts": fault_counts, "fault_hours": fault_hours}

print("\nfault rows and run hours per AHU (from the chunked read):")
print(fault_hours.round(3).to_string(index=False))
print("\nPeak Python-heap memory while computing the same per-AHU counts:")
print(mem_table.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
print("\nDataFrame resident size, default dtypes vs smaller dtypes:")
print(sizes.round(2).to_string())
print("\nchecks (printed, not asserted):")
print("  every approach gives the reference counts:", agree)
print(
    "  chunked counts equal the whole-table counts:",
    fault_hours.fault_rows.tolist() == fault_counts.fault_rows.tolist(),
)
print(f"  float32 flipped {flips} of {len(d):,} fault decisions")
print(
    f"  mean static, float64 vs float32: {d.duct_static.mean():.6f} {small.duct_static.mean():.6f}"
)
peak = mem_table.set_index("approach").peak_MiB
print(f"  stream peak {peak['stream (zip)']:.2f} MiB vs list {peak['list of tuples']:.2f} MiB")
print(f"  chunked peak {peak['chunked CSV read']:.2f} MiB, whole {peak['read whole CSV']:.2f} MiB")
tmp.cleanup()
