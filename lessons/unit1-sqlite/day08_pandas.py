"""Day 8, pandas: conditions. Static pressure while running vs off, run hours while unoccupied.

    uv run python lessons/unit1-sqlite/day08_pandas.py

SQL's CASE becomes boolean masks, np.where (two outcomes) and np.select (many). Conditional
aggregation (`sum(CASE WHEN ... THEN 1 END)`) becomes "sum a mask", or "filter, then groupby".
Compare the printout with day08_sql.py: the numbers should match.
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"

PA_PER_INH2O = 249.08891  # Day 6: the historian logged inches of water; fault math is SI

# 1. Load + stack both AHUs
COLUMNS = ["timestamp_utc", "supply_fan_status", "da_p_inwc", "da_p_setpoint_inwc", "occ_c"]
frames = []
for equip in ("AHU_1", "AHU_2"):
    df = pd.read_csv(DATA / equip / "history_wide.csv", usecols=COLUMNS)
    df.insert(0, "equipment_id", equip)
    frames.append(df)
h = pd.concat(frames, ignore_index=True)

# 2. SI units
h["duct_static_pa"] = h["da_p_inwc"] * PA_PER_INH2O
h["duct_static_sp_pa"] = h["da_p_setpoint_inwc"] * PA_PER_INH2O

# 3. Masks: one boolean per condition. np.where picks one of two values, np.select the first
#    matching of many.
running = h["supply_fan_status"] == 1
occupied = h["occ_c"] == 1
h["fan_state"] = np.where(running, "running", "off")
h["state"] = np.select(
    [running & occupied, running & ~occupied, ~running & occupied],
    ["run_occ", "run_unocc", "off_occ"],
    default="off_unocc",
)
states = h[["equipment_id", "timestamp_utc", "state"]]

# 4. Static pressure while running vs off (a CASE as the GROUP BY key)
h["static_error_pa"] = h["duct_static_pa"] - h["duct_static_sp_pa"]
static_by_state = (
    h.groupby(["equipment_id", "fan_state"])
    .agg(
        rows=("timestamp_utc", "size"),
        mean_static_pa=("duct_static_pa", "mean"),
        mean_setpoint_pa=("duct_static_sp_pa", "mean"),
        mean_error_pa=("static_error_pa", "mean"),
    )
    .reset_index()
)

# 5. Conditional aggregation: several different counts in one pass, one row per AHU
by_ahu = h.assign(run_unocc=running & ~occupied, run=running, occ=occupied).groupby("equipment_id")
occupancy = pd.DataFrame(
    {
        "rows": by_ahu.size(),
        "run_h": by_ahu["run"].sum() * 5 / 60,
        "run_h_unoccupied": by_ahu["run_unocc"].sum() * 5 / 60,
        "pct_occupied": by_ahu["occ"].mean() * 100,
    }
).reset_index()
occupancy["pct_run_while_unoccupied"] = 100 * occupancy["run_h_unoccupied"] / occupancy["run_h"]

RESULTS = {"states": states, "static_by_state": static_by_state, "occupancy": occupancy}

print("Duct static pressure by fan state (Pa):")
print(static_by_state.round(1).to_string(index=False))
print("\nRun hours, occupancy:")
print(occupancy.round(2).to_string(index=False))
print("\nRows per state:")
print(states.groupby(["equipment_id", "state"]).size().unstack().to_string())

# Timing (not part of RESULTS): the same classification as a vectorized mask and as a row-by-row
#    apply.
sample = h[["supply_fan_status", "occ_c"]]


def classify(row):
    if row["supply_fan_status"] == 1:
        return "run_occ" if row["occ_c"] == 1 else "run_unocc"
    return "off_occ" if row["occ_c"] == 1 else "off_unocc"


t0 = time.perf_counter()
vec = np.select(
    [running & occupied, running & ~occupied, ~running & occupied],
    ["run_occ", "run_unocc", "off_occ"],
    default="off_unocc",
)
t_vec = time.perf_counter() - t0
t0 = time.perf_counter()
rowwise = sample.apply(classify, axis=1)
t_apply = time.perf_counter() - t0
print(f"\nvectorized np.select, {len(h):,} rows: {t_vec * 1000:8.1f} ms")
print(
    f"apply(axis=1), same rows:      {t_apply * 1000:8.1f} ms  "
    f"(same answer: {(rowwise == vec).all()})"
)
