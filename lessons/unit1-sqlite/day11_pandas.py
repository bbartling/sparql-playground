"""Day 11, pandas: three ways to find rows, and what an index buys.

    uv run python lessons/unit1-sqlite/day11_pandas.py

Two questions on AHU_1's history: "all rows in one week" (a time range) and "all rows where duct
static is above 1.7 inH2O" (a rare value). Each is answered by a boolean mask (look at every row),
by an index (set_index + sort_index + .loc), and by binary search (np.searchsorted), which is the
same idea a database index uses.
Compare the printout with day11_sql.py: the row counts should match; the timings will not.
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"

RANGE_START = "2026-05-01 00:00:00+00:00"  # the week we want: [start, end)
RANGE_END = "2026-05-08 00:00:00+00:00"
RANGE_LAST = (
    "2026-05-07 23:55:00+00:00"  # .loc slices include their end label, so name the last row
)
HIGH_INWC = 1.7  # a rare duct static pressure (inH2O)


def best_ms(fn, repeat=7):
    """Best of `repeat` runs, in milliseconds (the minimum is the least noisy)."""
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    return min(times)


# 1. Load: one AHU, three columns. The CSV is already in time order.
COLUMNS = ["timestamp_utc", "da_p_inwc", "discharge_air_temp_f"]
h = pd.read_csv(DATA / "AHU_1" / "history_wide.csv", usecols=COLUMNS)
h = h.sort_values("timestamp_utc", ignore_index=True)
print(f"AHU_1: {len(h):,} rows")

# 2. The time range three ways. All three must return the same 2,016 rows (7 days x 288).
times = h["timestamp_utc"].to_numpy()  # already sorted
indexed = h.set_index("timestamp_utc").sort_index()  # built once: O(n log n)


def by_mask():  # O(n): compare every row
    return h[(h["timestamp_utc"] >= RANGE_START) & (h["timestamp_utc"] < RANGE_END)]


def by_loc():  # O(log n + k): the index finds both ends, then slices
    return indexed.loc[RANGE_START:RANGE_LAST]


def by_search():  # O(log n + k): two binary searches, then a slice
    lo = np.searchsorted(times, RANGE_START, side="left")
    hi = np.searchsorted(times, RANGE_END, side="left")
    return h.iloc[lo:hi]


def build_index():
    return h.set_index("timestamp_utc").sort_index()


week = by_mask()
counts = (len(week), len(by_loc()), len(by_search()))
print("\nOne week of rows, by mask / .loc / searchsorted:", " / ".join(map(str, counts)))
print(f"  all three agree on the row count: {len(set(counts)) == 1}")
t_mask, t_loc, t_search, t_build = (best_ms(f) for f in (by_mask, by_loc, by_search, build_index))
print(f"  mask {t_mask:.3f} ms | .loc {t_loc:.3f} ms | searchsorted {t_search:.3f} ms")
print(f"  building the index once: {t_build:.3f} ms")

# 3. A rare value: a mask scans every row; a sorted copy answers with one binary search.
values = h["da_p_inwc"].to_numpy()


def rare_mask():  # O(n), every time
    return h[h["da_p_inwc"] > HIGH_INWC]


def build_sort():  # the "index": row numbers in value order, O(n log n)
    return np.argsort(values, kind="stable")


order = build_sort()
sorted_vals = values[order]


def rare_lookup():  # O(log n + k)
    return h.iloc[order[np.searchsorted(sorted_vals, HIGH_INWC, side="right") :]]


high = rare_mask()
print(
    f"\nRows with duct static > {HIGH_INWC} inH2O: {len(high)} (lookup finds {len(rare_lookup())})"
)
t_rare_mask, t_rare_lookup, t_rare_build = (
    best_ms(f) for f in (rare_mask, rare_lookup, build_sort)
)
print(f"  mask {t_rare_mask:.3f} ms | sorted lookup {t_rare_lookup:.3f} ms")
print(f"  building the sort once: {t_rare_build:.3f} ms")

# 4. Break-even: how many queries until the one-time build cost is paid back?
saving = t_rare_mask - t_rare_lookup
if saving > 0:
    print(f"  the sort pays for itself after about {t_rare_build / saving:.1f} queries")
else:
    print("  at this size the mask is already so cheap that the sort never pays for itself")

# 5. Scaling: the mask grows with n, the binary search barely moves.
print("\nScaling (random sorted floats, one lookup):")
print(f"{'n':>12} {'mask ms':>10} {'searchsorted ms':>16}")
rng = np.random.default_rng(0)
for n in (100_000, 1_000_000, 10_000_000):
    vals = np.sort(rng.random(n))
    t_scan = best_ms(lambda v=vals: v > 0.999, 3)
    t_seek = best_ms(lambda v=vals: np.searchsorted(v, 0.999), 3)
    print(f"{n:>12,} {t_scan:>10.3f} {t_seek:>16.5f}")

week_summary = pd.DataFrame({"rows": [len(week)], "avg_static_inwc": [week["da_p_inwc"].mean()]})
RESULTS = {
    "week_rows": week,
    "week_summary": week_summary,
    "high_static_rows": high,
}
