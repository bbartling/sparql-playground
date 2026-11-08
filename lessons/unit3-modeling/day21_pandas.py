"""Day 21, pandas: an outside-air damper summary across AHUs whose column names differ.

    uv run python lessons/unit3-modeling/day21_pandas.py

AHU_1's damper command is the column `mad_c`; AHU_2's is `mad_c_pct`. A script with the name typed
in works for one AHU and fails on the other. column_map.json (role -> column, one per AHU) is the
first, smallest "model": the script asks for a *role* and the map says which column holds it.
Compare the printout with day21_sql.py: the numbers should match."""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"
EQUIPMENT = ("AHU_1", "AHU_2")

# 1. The hard-coded way: ask for `mad_c` on every AHU. It works for AHU_1 and fails for AHU_2.
HARD_CODED = ["timestamp_utc", "supply_fan_status", "mad_c"]
tried = []
for equip in EQUIPMENT:
    try:
        pd.read_csv(DATA / equip / "history_wide.csv", usecols=HARD_CODED, nrows=5)
        tried.append((equip, True, "ok"))
    except ValueError as err:
        tried.append((equip, False, str(err)))
hardcoded = pd.DataFrame(tried, columns=["equipment_id", "worked", "message"])

# 2. The first model: column_map.json says which column holds each role, per AHU.
ROLES = {"fan-status": "fan_status", "outside-air-damper": "oa_damper_pct"}  # role -> our own name
col_map = {e: json.loads((DATA / e / "column_map.json").read_text())["points"] for e in EQUIPMENT}
damper_columns = pd.DataFrame(
    [(e, col_map[e]["outside-air-damper"]) for e in EQUIPMENT],
    columns=["equipment_id", "damper_column"],
)

# 3. Load by role: look up each AHU's column names, read only those, rename to the shared names.
frames = []
for equip in EQUIPMENT:
    by_role = {col_map[equip][role]: name for role, name in ROLES.items()}  # column -> shared name
    df = pd.read_csv(DATA / equip / "history_wide.csv", usecols=["timestamp_utc", *by_role]).rename(
        columns=by_role
    )
    df.insert(0, "equipment_id", equip)
    frames.append(df)
oa = pd.concat(frames, ignore_index=True)

# 4. One summary for both AHUs: only rows where the supply fan runs (the damper is moot when off)
running = oa[oa["fan_status"] == 1]
summary = (
    running.groupby("equipment_id")["oa_damper_pct"]
    .agg(run_rows="size", mean_damper_pct="mean")
    .assign(
        open_over_50_h=running.assign(hit=running["oa_damper_pct"] > 50)
        .groupby("equipment_id")["hit"]
        .sum()
        * 5
        / 60,
        closed_h=running.assign(hit=running["oa_damper_pct"] <= 0)
        .groupby("equipment_id")["hit"]
        .sum()
        * 5
        / 60,
    )
    .reset_index()
    .merge(damper_columns, on="equipment_id")
)
summary.insert(2, "run_hours", summary["run_rows"] * 5 / 60)
summary = summary[
    [
        "equipment_id",
        "damper_column",
        "run_rows",
        "run_hours",
        "mean_damper_pct",
        "open_over_50_h",
        "closed_h",
    ]
]

RESULTS = {
    "hardcoded_worked": hardcoded[["equipment_id", "worked"]],
    "damper_columns": damper_columns,
    "damper_summary": summary,
}

print("Hard-coded `mad_c` on each AHU:")
print(hardcoded.to_string(index=False, max_colwidth=60))
print("\nDamper column per AHU, from column_map.json:")
print(damper_columns.to_string(index=False))
print("\nOutside-air damper while the supply fan runs (one script, both AHUs):")
print(summary.round(2).to_string(index=False))
