# Day 21 (pandas): one script for two AHUs whose column names differ.
# Run from the repo root:
#     uv run python lessons/unit3-modeling/day21_pandas.py
#
# AHU_1 calls its outside-air damper command `mad_c`; AHU_2 calls it `mad_c_pct`.
# column_map.json (one per AHU) says which column holds each role, so the script asks for a role.

import json

import pandas as pd

ahus = ["AHU_1", "AHU_2"]

# 1. The hard-coded way: ask every AHU for the column `mad_c`
hardcoded_rows = []
for ahu in ahus:
    path = "data/BUILDING_50/" + ahu + "/history_wide.csv"
    try:
        pd.read_csv(path, usecols=["mad_c"], nrows=5)
        worked = True
    except ValueError:  # pandas raises this when a column does not exist
        worked = False
    hardcoded_rows.append({"equipment_id": ahu, "worked": worked})
hardcoded = pd.DataFrame(hardcoded_rows)

# 2. Look up the damper column and the fan column in each AHU's column_map.json
summary_rows = []
for ahu in ahus:
    with open("data/BUILDING_50/" + ahu + "/column_map.json") as f:
        points = json.load(f)["points"]
    damper_column = points["outside-air-damper"]
    fan_column = points["fan-status"]

    # 3. Read only those two columns and give them the same names for every AHU
    df = pd.read_csv(
        "data/BUILDING_50/" + ahu + "/history_wide.csv", usecols=[fan_column, damper_column]
    )
    df = df.rename(columns={fan_column: "fan_status", damper_column: "oa_damper_pct"})

    # 4. Summarize the damper while the supply fan runs (each row is 5 minutes)
    running = df[df["fan_status"] == 1]
    run_rows = len(running)
    mean_damper = running["oa_damper_pct"].mean()
    open_rows = (running["oa_damper_pct"] > 50).sum()
    closed_rows = (running["oa_damper_pct"] <= 0).sum()
    summary_rows.append(
        {
            "equipment_id": ahu,
            "damper_column": damper_column,
            "run_rows": run_rows,
            "run_hours": run_rows * 5 / 60,
            "mean_damper_pct": mean_damper,
            "open_over_50_h": open_rows * 5 / 60,
            "closed_h": closed_rows * 5 / 60,
        }
    )
summary = pd.DataFrame(summary_rows)
damper_columns = summary[["equipment_id", "damper_column"]]

print("Hard-coded `mad_c` on each AHU:")
print(hardcoded.to_string(index=False))
print("\nDamper column per AHU, from column_map.json:")
print(damper_columns.to_string(index=False))
print("\nOutside-air damper while the supply fan runs (one script, both AHUs):")
print(summary.round(2).to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "hardcoded_worked": hardcoded,
    "damper_columns": damper_columns,
    "damper_summary": summary,
}
