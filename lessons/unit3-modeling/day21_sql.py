# Day 21 (SQL): one script for two AHUs whose column names differ.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit3-modeling/day21_sql.py
#
# AHU_1 calls its outside-air damper command `mad_c`; AHU_2 calls it `mad_c_pct`.
# column_map.json (one per AHU) says which column holds each role, so the script asks for a role.

import json
import sqlite3

import pandas as pd

conn = sqlite3.connect("var/lessons.sqlite")

ahus = ["AHU_1", "AHU_2"]

# 1. The hard-coded way: ask every AHU's table for the column `mad_c`
hardcoded_rows = []
for ahu in ahus:
    table = ahu.lower()  # the tables are called ahu_1 and ahu_2
    try:
        conn.execute("SELECT mad_c FROM " + table + " LIMIT 5")
        worked = 1
    except sqlite3.OperationalError:  # SQLite says "no such column"
        worked = 0
    hardcoded_rows.append({"equipment_id": ahu, "worked": worked})
hardcoded = pd.DataFrame(hardcoded_rows)

summary_rows = []
for ahu in ahus:
    table = ahu.lower()

    # 2. Look up the damper column and the fan column in each AHU's column_map.json
    with open("data/BUILDING_50/" + ahu + "/column_map.json") as f:
        points = json.load(f)["points"]
    damper_column = points["outside-air-damper"]
    fan_column = points["fan-status"]

    # A value can be a ? parameter, but a column name cannot. So the names are pasted into
    # the SQL text, after checking that they are real columns of the table (never paste
    # text you have not checked).
    real_columns = [row[1] for row in conn.execute("PRAGMA table_info(" + table + ")")]
    if damper_column not in real_columns or fan_column not in real_columns:
        raise ValueError("unknown column in column_map.json")

    # 3. Summarize the damper while the supply fan runs (each row is 5 minutes)
    sql = f"""
        SELECT COUNT(*),
               AVG({damper_column}),
               SUM({damper_column} > 50),
               SUM({damper_column} <= 0)
        FROM {table}
        WHERE {fan_column} = 1
    """
    run_rows, mean_damper, open_rows, closed_rows = conn.execute(sql).fetchone()
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
