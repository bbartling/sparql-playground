"""Day 14, pandas: FC1 (duct static too low while the fan runs) on both AHUs.

    uv run python lessons/unit1-sqlite/day14_pandas.py

Reads the historian's CSV exports straight into DataFrames. Column names are hard-coded on purpose:
this is how a first FDD script looks. (Week 5 replaces them with a model lookup.)
Compare the printout with day14_sql.py: the numbers should match.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"

PA_PER_INH2O = 249.08891  # the historian logged inches of water; fault math is SI (pascals)
TOL_PA = 25.0  # how far below setpoint counts as a fault (~0.1 inH2O)
CONFIRM_ROWS = 2  # 2 rows x 5 min = 10 minutes before a fault counts

# 1. Load: one CSV per AHU, only the columns FC1 needs. Same column names on both AHUs.
COLUMNS = ["timestamp_utc", "supply_fan_status", "da_p_inwc", "da_p_setpoint_inwc"]
frames = []
for equip in ("AHU_1", "AHU_2"):
    df = pd.read_csv(DATA / equip / "history_wide.csv", usecols=COLUMNS)
    df.insert(0, "equipment_id", equip)
    frames.append(df)
h = pd.concat(frames, ignore_index=True)
h = h.sort_values(["equipment_id", "timestamp_utc"], ignore_index=True)

# 2. SI units
h["duct_static_pa"] = h["da_p_inwc"] * PA_PER_INH2O
h["duct_static_sp_pa"] = h["da_p_setpoint_inwc"] * PA_PER_INH2O

# 3. Gate + raw fault: fan running and static more than TOL_PA below setpoint
eq = h["equipment_id"]
raw = (h["supply_fan_status"] == 1) & (h["duct_static_pa"] < h["duct_static_sp_pa"] - TOL_PA)
raw = raw.astype(int)

# 4. Confirm: number the streaks (runs of equal raw values), then the rows inside each streak
new_streak = raw.ne(raw.groupby(eq).shift()).astype(int)  # first row of each AHU starts a streak
streak_id = new_streak.groupby(eq).cumsum()
streak_len = raw.groupby([eq, streak_id]).cumcount() + 1
fault = ((raw == 1) & (streak_len >= CONFIRM_ROWS)).astype(int)
fc1 = h[["equipment_id", "timestamp_utc"]].assign(raw_fault=raw, streak_id=streak_id, fault=fault)

# 5. Aggregate: rows x 5 minutes = hours, and confirmed episodes
hours = fc1.groupby("equipment_id")[["raw_fault", "fault"]].sum() * 5 / 60
episodes = fc1[fc1["fault"] == 1].groupby("equipment_id")["streak_id"].nunique()
summary = (
    hours.rename(columns={"raw_fault": "raw_fault_h", "fault": "confirmed_fault_h"})
    .assign(episodes=episodes)
    .fillna({"episodes": 0})
    .reset_index()
)

# 6. Compare with Open-FDD: its FC1 episodes for this data, and how many contain one of our faults
events = pd.concat(
    [pd.read_csv(DATA / e / "fdd_events.csv") for e in ("AHU_1", "AHU_2")], ignore_index=True
)
events = events[events["rule_name"] == "fc1"].copy()
events["equipment_id"] = events["hvac_system"].str.replace("bld_50_", "", regex=False)
openfdd = (
    events.groupby("equipment_id")
    .agg(episodes=("rule_name", "size"), hours=("duration_min", "sum"))
    .assign(hours=lambda d: d["hours"] / 60)
    .reset_index()
)

found = np.zeros(len(events), dtype=bool)
for equip, ev in events.groupby("equipment_id"):
    # binary search: sorted fault times; an event contains a fault if one falls in [start, end]
    times = np.sort(
        fc1.loc[(fc1.equipment_id == equip) & (fc1.fault == 1), "timestamp_utc"].to_numpy()
    )
    lo = np.searchsorted(times, ev["start_time_utc"].to_numpy(), side="left")
    hi = np.searchsorted(times, ev["end_time_utc"].to_numpy(), side="right")
    found[events.index.get_indexer(ev.index)] = hi > lo
overlap = pd.DataFrame({"openfdd_episodes": [len(events)], "also_found_by_us": [int(found.sum())]})

RESULTS = {"fc1_per_row": fc1, "fc1_summary": summary, "openfdd_fc1": openfdd, "overlap": overlap}

print("FC1 per AHU (hours, episodes):")
print(summary.round(2).to_string(index=False))
print("\nOpen-FDD's FC1 episodes for the same data:")
print(openfdd.round(1).to_string(index=False))
print("\nOpen-FDD episodes that contain at least one of our confirmed fault rows:")
print(overlap.to_string(index=False))
