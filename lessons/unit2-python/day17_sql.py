"""Day 17, SQL side: the same per-AHU counts as aggregates, and what pulling the rows out costs.

    uv run python lessons/unit2-python/day17_sql.py

The task for every version is the same: the count of raw FC1 faults (fan running, duct static more
than 25 Pa below setpoint) per AHU, plus run hours. Same synthetic rows as day17_pandas.py, loaded
into an in-memory SQLite table first (setup). SQLite does the computation; Python holds 2 rows.

The memory comparison measures the Python heap only (tracemalloc). It cannot see SQLite's own
memory, so we also print the size of the database itself. Compare with day17_pandas.py.
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lessons"))
import lab  # noqa: E402

PARAMS = {"tol": 25.0}  # how far below setpoint counts as a fault
N = 20_000 if lab.QUICK else 100_000  # rows per AHU; two AHUs
CHUNK = N // 8  # rows per chunk when pulling rows out in pieces
ROWS_SQL = "SELECT equipment_id, ts, fan_status, duct_static, duct_static_sp FROM h"

COUNTS_SQL = """
SELECT equipment_id,
       SUM(fan_status = 1 AND duct_static < duct_static_sp - :tol) AS fault_rows
FROM h GROUP BY equipment_id ORDER BY equipment_id
"""

HOURS_SQL = """
SELECT equipment_id,
       SUM(fan_status = 1 AND duct_static < duct_static_sp - :tol) AS fault_rows,
       SUM(fan_status = 1) * 5 / 60.0 AS run_hours
FROM h GROUP BY equipment_id ORDER BY equipment_id
"""

# 1. Data: the same synthetic history as the pandas script, loaded into SQLite (setup)
conn = sqlite3.connect(":memory:")
lab.to_sqlite(lab.synthetic_history(N, equips=2), conn, "h", index=["equipment_id", "ts"])
print(f"{conn.execute('SELECT count(*) FROM h').fetchone()[0]:,} rows in table h")

# 2. The answers: one GROUP BY each. SQLite scans every row; Python receives two rows.
fault_counts = pd.read_sql_query(COUNTS_SQL, conn, params=PARAMS)
fault_hours = pd.read_sql_query(HOURS_SQL, conn, params=PARAMS)
print(fault_counts.to_string(index=False))


# 3. Peak Python-heap memory: the aggregate against pulling the rows out (transfer only, no maths)
def sql_aggregate():
    return pd.read_sql_query(COUNTS_SQL, conn, params=PARAMS)


def pull_fetchall():
    return len(conn.execute(ROWS_SQL).fetchall())  # a list of N tuples, all alive at once


def pull_stream():
    return sum(1 for _ in conn.execute(ROWS_SQL))  # one tuple at a time


def pull_dataframe():
    return len(pd.read_sql_query(ROWS_SQL, conn))  # whole result as NumPy arrays


def pull_chunked():
    return sum(len(c) for c in pd.read_sql_query(ROWS_SQL, conn, chunksize=CHUNK))


mem_table = pd.DataFrame(
    [
        {"approach": name, "peak_MiB": lab.peak_mib(fn)}
        for name, fn in {
            "SQL aggregate (2 rows back)": sql_aggregate,
            "fetchall list": pull_fetchall,
            "cursor stream": pull_stream,
            "read_sql_query whole": pull_dataframe,
            "read_sql_query chunked": pull_chunked,
        }.items()
    ]
)

# 4. What tracemalloc cannot see: the in-memory database itself
page_count = conn.execute("PRAGMA page_count").fetchone()[0]
page_size = conn.execute("PRAGMA page_size").fetchone()[0]
db_mib = page_count * page_size / 2**20

RESULTS = {"fault_counts": fault_counts, "fault_hours": fault_hours}

print("\nfault rows and run hours per AHU:")
print(fault_hours.round(3).to_string(index=False))
print("\nPeak Python-heap memory (the rows are pulled out but not computed on):")
print(mem_table.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
print(f"\nSQLite's own memory, which tracemalloc cannot see: the database is {db_mib:.1f} MiB")
peak = mem_table.set_index("approach").peak_MiB
print()
print("observation: peak MiB by approach:", peak.round(3).to_dict())
