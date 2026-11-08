"""Day 6, SQL: convert AHU_1's FDD columns from US units to SI (degC, Pa, fractions 0-1).

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day06_sql.py

The same conversions as day06_pandas.py, as a TEMP VIEW: a saved SELECT that every later query can
use as if it were a table. SQLite does all the work; pandas only turns the result rows into a
table for printing.
Compare the printout with day06_pandas.py: the numbers should match.
"""

import os
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = Path(os.environ.get("LESSONS_DB", ROOT / "var" / "lessons.sqlite"))
if not DB.exists():
    raise SystemExit(f"{DB} not found. Run:  uv run python lessons/course.py setup")
conn = sqlite3.connect(DB)

PARAMS = {"pa_per_inh2o": 249.08891}  # 1 inch of water column = 249.08891 pascals

# 1 + 2. Load and convert in one view. ahu_1 is the CSV loaded as a table, same column names.
#        Absolute temperatures use (F - 32) * 5/9. Pressure is a plain factor. Percent is / 100.
SI_VIEW_SQL = """
CREATE TEMP VIEW ahu_1_si AS
SELECT timestamp_utc,
       (discharge_air_temp_f - 32) * 5 / 9.0 AS discharge_air_temp_c,
       (dat_reset_f - 32) * 5 / 9.0          AS dat_setpoint_c,
       (outside_air_temp_f - 32) * 5 / 9.0   AS outside_air_temp_c,
       da_p_inwc * :pa_per_inh2o             AS duct_static_pa,
       da_p_setpoint_inwc * :pa_per_inh2o    AS duct_static_sp_pa,
       supply_fan_speed_pct / 100.0          AS supply_fan_speed_frac,
       chw_valve_pct / 100.0                 AS chw_valve_frac
FROM ahu_1
"""
# SQLite can't bind parameters inside CREATE VIEW, so put the number in the text (it's a constant).
conn.execute(SI_VIEW_SQL.replace(":pa_per_inh2o", repr(PARAMS["pa_per_inh2o"])))

# 3. The delta trap: DAT error is a temperature DIFFERENCE. A difference has no 32 in it: x degF =
#    x * 5/9 K.
#    Right: convert the difference, or subtract two converted values (same answer).
#    Wrong: push the difference through the absolute formula.
DELTA_SQL = """
SELECT timestamp_utc,
       (discharge_air_temp_f - dat_reset_f) * 5 / 9.0        AS dat_error_k,
       (SELECT discharge_air_temp_c - dat_setpoint_c FROM ahu_1_si s
        WHERE s.timestamp_utc = a.timestamp_utc)              AS dat_error_k_check,
       ((discharge_air_temp_f - dat_reset_f) - 32) * 5 / 9.0 AS dat_error_wrong
FROM ahu_1 a
ORDER BY timestamp_utc
"""

# 4. Summaries: means in SI, and the 5 degF demo
MEANS_SQL = """
SELECT 'discharge_air_temp_c' AS "column", avg(discharge_air_temp_c) AS mean FROM ahu_1_si UNION ALL
SELECT 'dat_setpoint_c', avg(dat_setpoint_c) FROM ahu_1_si UNION ALL
SELECT 'outside_air_temp_c', avg(outside_air_temp_c) FROM ahu_1_si UNION ALL
SELECT 'duct_static_pa', avg(duct_static_pa) FROM ahu_1_si UNION ALL
SELECT 'duct_static_sp_pa', avg(duct_static_sp_pa) FROM ahu_1_si UNION ALL
SELECT 'supply_fan_speed_frac', avg(supply_fan_speed_frac) FROM ahu_1_si UNION ALL
SELECT 'chw_valve_frac', avg(chw_valve_frac) FROM ahu_1_si
"""
FIVE_F_SQL = "SELECT 5.0 AS delta_f, 5 * 5 / 9.0 AS right_k, (5 - 32) * 5 / 9.0 AS wrong_k"

si = pd.read_sql_query("SELECT * FROM ahu_1_si ORDER BY timestamp_utc", conn)
deltas = pd.read_sql_query(DELTA_SQL, conn)
means = pd.read_sql_query(MEANS_SQL, conn)
five_f = pd.read_sql_query(FIVE_F_SQL, conn)
raw = pd.read_sql_query("SELECT * FROM ahu_1 ORDER BY timestamp_utc LIMIT 3", conn)

RESULTS = {"ahu_1_si": si, "dat_error": deltas, "si_means": means, "five_f": five_f}

print("A 5 degF *difference*:")
print(five_f.round(2).to_string(index=False))
print("\nFirst rows, US units then SI:")
print(
    raw[
        [
            "timestamp_utc",
            "discharge_air_temp_f",
            "dat_reset_f",
            "outside_air_temp_f",
            "da_p_inwc",
            "da_p_setpoint_inwc",
            "supply_fan_speed_pct",
            "chw_valve_pct",
        ]
    ]
    .round(2)
    .to_string(index=False)
)
print(si.head(3).round(2).to_string(index=False))
print("\nMean of each SI column:")
print(means.round(3).to_string(index=False))
print("\nDAT error (K), right vs wrong, over all rows:")
print(deltas[["dat_error_k", "dat_error_wrong"]].describe().loc[["mean", "min", "max"]].round(2))
