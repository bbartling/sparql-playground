"""Day 7, pandas: stack two AHUs, then join them on time to compare their outside-air sensors.

    uv run python lessons/unit1-sqlite/day07_pandas.py

Both AHUs measure the same weather, so their outside-air temperatures should nearly agree.
`concat` stacks the rows (one table, an equipment_id column); `merge` lines them up side by side
by timestamp.
Compare the printout with day07_sql.py: the numbers should match.
"""

import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"

# 1. Load + stack: one CSV per AHU, an equipment_id column says which rows came from where (UNION
#    ALL)
COLUMNS = ["timestamp_utc", "outside_air_temp_f"]
frames = []
for equip in ("AHU_1", "AHU_2"):
    df = pd.read_csv(DATA / equip / "history_wide.csv", usecols=COLUMNS)
    df.insert(0, "equipment_id", equip)
    frames.append(df)
stacked = pd.concat(frames, ignore_index=True)

# 2. SI units (Day 6)
stacked["outside_air_temp_c"] = (stacked["outside_air_temp_f"] - 32) * 5 / 9

# 3. What the stacked table holds, per AHU
stack_summary = (
    stacked.groupby("equipment_id")
    .agg(
        rows=("timestamp_utc", "size"),
        first_ts=("timestamp_utc", "min"),
        last_ts=("timestamp_utc", "max"),
        mean_oa_c=("outside_air_temp_c", "mean"),
        min_oa_c=("outside_air_temp_c", "min"),
    )
    .reset_index()
)

# 4. Join on timestamp: one row per timestamp, one column per AHU (an inner join, 1:1).
#    validate="1:1" makes pandas raise if either side has a repeated timestamp.
a = stacked[stacked.equipment_id == "AHU_1"][["timestamp_utc", "outside_air_temp_c"]]
b = stacked[stacked.equipment_id == "AHU_2"][["timestamp_utc", "outside_air_temp_c"]]
pairs = a.merge(b, on="timestamp_utc", suffixes=("_ahu_1", "_ahu_2"), validate="1:1")
pairs = pairs.rename(
    columns={"outside_air_temp_c_ahu_1": "oa_ahu_1_c", "outside_air_temp_c_ahu_2": "oa_ahu_2_c"}
)
# a difference of two converted temperatures is already in kelvin (Day 6's delta rule)
pairs["diff_k"] = pairs["oa_ahu_1_c"] - pairs["oa_ahu_2_c"]

# 5. How far apart are they?
absd = pairs["diff_k"].abs()
gap = pd.DataFrame(
    {
        "paired_rows": [len(pairs)],
        "mean_abs_diff_k": [absd.mean()],
        "max_abs_diff_k": [absd.max()],
        "rows_over_2k": [int((absd > 2).sum())],
        "rows_over_20k": [int((absd > 20).sum())],
    }
)

# 6. Join explosion: the first day (280 rows per AHU), joined on the HOUR instead of the timestamp.
#    The hour repeats 12 times per AHU, so every row matches 12 rows on the other side.
day_a = a[a.timestamp_utc < "2026-03-17"].assign(hour=lambda d: d.timestamp_utc.str[:13])
day_b = b[b.timestamp_utc < "2026-03-17"].assign(hour=lambda d: d.timestamp_utc.str[:13])
by_ts = day_a.merge(day_b, on="timestamp_utc")
by_hour = day_a.merge(day_b, on="hour")
try:
    day_a.merge(day_b, on="hour", validate="1:1")
    blocked = False
except pd.errors.MergeError:
    blocked = True
explosion = pd.DataFrame(
    {
        "rows_per_side": [len(day_a)],
        "joined_on_timestamp": [len(by_ts)],
        "joined_on_hour": [len(by_hour)],
        "validate_blocked": [blocked],
    }
)

RESULTS = {
    "stack_summary": stack_summary,
    "oa_pairs": pairs,
    "oa_gap": gap,
    "explosion": explosion,
}

print("Stacked table, per AHU:")
print(stack_summary.round(2).to_string(index=False))
print("\nOutside-air temperature, AHU_1 minus AHU_2 (K):")
print(gap.round(2).to_string(index=False))
print("\nJoin explosion on one day of data:")
print(explosion.to_string(index=False))

# Timing (not part of RESULTS): hash join (merge) vs a hand-written nested loop on 1,500 rows per
#    side.
n = 1500
left = a.head(n)["timestamp_utc"].tolist()
right = b.head(n)["timestamp_utc"].tolist()
t0 = time.perf_counter()
loops = sum(1 for x in left for y in right if x == y)
t_loop = time.perf_counter() - t0
t0 = time.perf_counter()
merged = a.head(n).merge(b.head(n), on="timestamp_utc")
t_merge = time.perf_counter() - t0
t0 = time.perf_counter()
a.merge(b, on="timestamp_utc", validate="1:1")
t_full = time.perf_counter() - t0
print(
    f"\nnested loop, {n} x {n} rows: {t_loop * 1000:8.1f} ms  "
    f"({loops} matches, {n * n:,} comparisons)"
)
print(f"merge (hash join), same:    {t_merge * 1000:8.1f} ms  ({len(merged)} matches)")
print(f"merge, all {len(a):,} rows:   {t_full * 1000:8.1f} ms")
