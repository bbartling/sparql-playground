"""Day 8, SQL: conditions. Static pressure while running vs off, run hours while unoccupied.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day08_sql.py

The same computation as day08_pandas.py, done by SQLite on the same rows. CASE picks a value per
row; CASE inside an aggregate (`sum(CASE WHEN ... THEN 1 ELSE 0 END)`) counts several things in
one pass.
Compare the printout with day08_pandas.py: the numbers should match.
"""

import os
import sqlite3
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = Path(os.environ.get("LESSONS_DB", ROOT / "var" / "lessons.sqlite"))
if not DB.exists():
    raise SystemExit(f"{DB} not found. Run:  uv run python lessons/course.py setup")
conn = sqlite3.connect(DB)

PARAMS = {
    "pa_per_inh2o": 249.08891
}  # Day 6: the historian logged inches of water; fault math is SI

# 1 + 2. Stack both AHUs and convert to SI. ahu_1 and ahu_2 are the CSVs loaded as tables.
#        (CREATE VIEW can't take bound parameters, so the constant is spliced into the text.)
H_VIEW_SQL = """
CREATE TEMP VIEW h AS
SELECT 'AHU_1' AS equipment_id, timestamp_utc, supply_fan_status, occ_c,
       da_p_inwc * {pa} AS duct_static_pa, da_p_setpoint_inwc * {pa} AS duct_static_sp_pa
FROM ahu_1
UNION ALL
SELECT 'AHU_2', timestamp_utc, supply_fan_status, occ_c,
       da_p_inwc * {pa}, da_p_setpoint_inwc * {pa}
FROM ahu_2
"""
conn.execute(H_VIEW_SQL.format(pa=repr(PARAMS["pa_per_inh2o"])))

# 3. CASE per row: the first WHEN that matches wins (np.select), ELSE is the default
STATES_SQL = """
SELECT equipment_id, timestamp_utc,
       CASE WHEN supply_fan_status = 1 AND occ_c = 1 THEN 'run_occ'
            WHEN supply_fan_status = 1 AND occ_c <> 1 THEN 'run_unocc'
            WHEN supply_fan_status <> 1 AND occ_c = 1 THEN 'off_occ'
            ELSE 'off_unocc' END AS state
FROM h
ORDER BY equipment_id, timestamp_utc
"""

# 4. Static pressure while running vs off: a CASE as the GROUP BY key
STATIC_SQL = """
SELECT equipment_id,
       CASE WHEN supply_fan_status = 1 THEN 'running' ELSE 'off' END AS fan_state,
       count(*) AS rows,
       avg(duct_static_pa)                      AS mean_static_pa,
       avg(duct_static_sp_pa)                   AS mean_setpoint_pa,
       avg(duct_static_pa - duct_static_sp_pa)  AS mean_error_pa
FROM h
GROUP BY equipment_id, fan_state
ORDER BY equipment_id, fan_state
"""

# 5. Conditional aggregation: several different counts in one pass, one row per AHU.
#    A comparison is 0 or 1 in SQLite, so sum(<condition>) counts the rows where it holds.
OCCUPANCY_SQL = """
SELECT equipment_id,
       count(*) AS rows,
       sum(supply_fan_status = 1) * 5 / 60.0                       AS run_h,
       sum(supply_fan_status = 1 AND occ_c <> 1) * 5 / 60.0        AS run_h_unoccupied,
       100.0 * sum(occ_c = 1) / count(*)                           AS pct_occupied,
       100.0 * sum(supply_fan_status = 1 AND occ_c <> 1) / sum(supply_fan_status = 1)
                                                                   AS pct_run_while_unoccupied
FROM h
GROUP BY equipment_id
ORDER BY equipment_id
"""

states = pd.read_sql_query(STATES_SQL, conn)
static_by_state = pd.read_sql_query(STATIC_SQL, conn)
occupancy = pd.read_sql_query(OCCUPANCY_SQL, conn)

RESULTS = {"states": states, "static_by_state": static_by_state, "occupancy": occupancy}

print("Duct static pressure by fan state (Pa):")
print(static_by_state.round(1).to_string(index=False))
print("\nRun hours, occupancy:")
print(occupancy.round(2).to_string(index=False))
print("\nRows per state:")
print(states.groupby(["equipment_id", "state"]).size().unstack().to_string())

# Timing (not part of RESULTS): conditional aggregation = one scan, vs one query (one scan) per
#    number.
t0 = time.perf_counter()
conn.execute(OCCUPANCY_SQL).fetchall()
t_one = time.perf_counter() - t0
SEPARATE = [
    "SELECT count(*) FROM h",
    "SELECT count(*) FROM h WHERE supply_fan_status = 1",
    "SELECT count(*) FROM h WHERE supply_fan_status = 1 AND occ_c <> 1",
    "SELECT count(*) FROM h WHERE occ_c = 1",
]
t0 = time.perf_counter()
for q in SEPARATE:
    conn.execute(q).fetchall()
t_four = time.perf_counter() - t0
print(f"\none query, conditional aggregation: {t_one * 1000:7.1f} ms")
print(f"four separate COUNT queries:        {t_four * 1000:7.1f} ms")
