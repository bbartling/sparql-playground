"""Day 25, SQL: FC1 driven by the model. The UUIDs come from SPARQL; SQLite runs the rule on
`samples`.

    uv run python lessons/unit3-modeling/day25_sql.py

Needs var/timeseries.sqlite and model/building_50.ttl (`uv run bldgts model build && uv run bldgts
bootstrap`). lab.Api (the repo's FastAPI app, in-process) answers the SPARQL question "which
points are FC1's inputs?". The UUIDs it returns go into a TEMP table, and one parameterized query
pivots `samples`, converts to SI and runs Day 14's FC1. No column names or ids are written in this
script. Compare the printout with day25_pandas.py (and with Day 14: AHU_1 114.25 h in 53 episodes,
AHU_2 1.50 h)."""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lessons"))
import lab  # noqa: E402

# 1. Ask the model for FC1's inputs (same query as day25_pandas.py).
FC1_POINTS_SPARQL = """
PREFIX bts: <https://example.org/openfdd/bldgts#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>
SELECT ?ahu ?role ?point ?timeseriesId WHERE {
  ?point ref:hasExternalReference ?ref .
  ?ref ref:hasTimeseriesId ?timeseriesId .
  ?point bts:hasHaystackTag ?roleTag .
  ?roleTag bts:tagName "ofddRole" ; bts:tagValue ?role .
  FILTER(?role IN ("fan-status", "duct-static-pressure", "duct-static-pressure-sp"))
  ?point bts:hasHaystackTag ?direct .
  ?direct bts:tagName "equipRef" ; bts:tagValue ?ahu .
}
ORDER BY ?ahu ?role
"""
with lab.Api() as api:
    found = api.sparql(FC1_POINTS_SPARQL)
found["equipment_id"] = found["ahu"].str.rsplit("#", n=1).str[-1]  # IRI local name: AHU_1
found["point_id"] = found["point"].str.rsplit("#", n=1).str[-1]
fc1_inputs = found[["equipment_id", "role", "point_id", "timeseriesId"]].rename(
    columns={"timeseriesId": "timeseries_id"}
)

# The API's database, read-only. The UUIDs become a TEMP table the query joins to `samples`.
conn = sqlite3.connect(f"file:{lab.db_path().as_posix()}?mode=ro", uri=True)
conn.execute(
    "CREATE TEMP TABLE fc1_input (equipment_id TEXT, role TEXT, timeseries_id TEXT PRIMARY KEY)"
)
conn.executemany(
    "INSERT INTO fc1_input VALUES (?, ?, ?)",
    list(fc1_inputs[["equipment_id", "role", "timeseries_id"]].itertuples(index=False)),
)

PARAMS = {
    "role_fan": "fan-status",  # the rule's three inputs, by role: the only names the rule knows
    "role_dp": "duct-static-pressure",
    "role_sp": "duct-static-pressure-sp",
    "pa_per_inh2o": lab.PA_PER_INH2O,  # the historian logged inches of water; fault math is SI
    "tol": 25.0,  # how far below setpoint counts as a fault (~0.1 inH2O)
    "confirm": 2,  # 2 rows x 5 min = 10 minutes before a fault counts
}

# 2.-4. One query, one CTE per step: pivot long -> wide, SI, then Day 14's FC1.
FC1_SQL = """
CREATE TEMP TABLE fc1 AS
WITH wide AS (                                -- long -> wide: one row per (equipment, ts)
  SELECT i.equipment_id, s.ts,
         MAX(CASE WHEN i.role = :role_fan THEN s.value END) AS fan_status,
         MAX(CASE WHEN i.role = :role_dp  THEN s.value END) AS da_p_inwc,
         MAX(CASE WHEN i.role = :role_sp  THEN s.value END) AS da_p_sp_inwc
  FROM samples s
  JOIN fc1_input i ON i.timeseries_id = s.timeseries_id
  GROUP BY i.equipment_id, s.ts
), si AS (                                    -- SI units
  SELECT equipment_id, ts, fan_status,
         da_p_inwc * :pa_per_inh2o    AS duct_static_pa,
         da_p_sp_inwc * :pa_per_inh2o AS duct_static_sp_pa
  FROM wide
), base AS (                                  -- gate + raw fault
  SELECT equipment_id, ts,
         CASE WHEN fan_status = 1 AND duct_static_pa < duct_static_sp_pa - :tol
              THEN 1 ELSE 0 END AS raw_fault
  FROM si
), marks AS (                                 -- a new streak starts where raw_fault changes
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER w THEN 0 ELSE 1 END AS new_streak
  FROM base
  WINDOW w AS (PARTITION BY equipment_id ORDER BY ts)
), streaks AS (                               -- running sum of starts numbers the streaks
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id
  FROM marks
), ranked AS (                                -- row number inside each streak
  SELECT *, ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts) AS streak_len
  FROM streaks
)
SELECT equipment_id, ts, raw_fault, streak_id,
       CASE WHEN raw_fault = 1 AND streak_len >= :confirm THEN 1 ELSE 0 END AS fault
FROM ranked
"""
conn.execute(FC1_SQL, PARAMS)
conn.execute("CREATE INDEX temp.fc1_eq_ts ON fc1 (equipment_id, ts)")

# 5. Rows x 5 minutes = hours, and confirmed episodes
SUMMARY_SQL = """
SELECT equipment_id,
       sum(raw_fault) * 5 / 60.0 AS raw_fault_h,
       sum(fault) * 5 / 60.0     AS confirmed_fault_h,
       count(DISTINCT CASE WHEN fault = 1 THEN streak_id END) AS episodes
FROM fc1
GROUP BY equipment_id
ORDER BY equipment_id
"""
fc1 = pd.read_sql_query("SELECT * FROM fc1 ORDER BY equipment_id, ts", conn)
summary = pd.read_sql_query(SUMMARY_SQL, conn)

RESULTS = {"fc1_inputs": fc1_inputs, "fc1_per_row": fc1, "fc1_summary": summary}

print("FC1's inputs, found by the model:")
print(fc1_inputs.to_string(index=False))
print(f"\n{len(fc1):,} rows of input after the pivot.")
print("\nFC1 per AHU (hours, episodes). Day 14 printed the same numbers from hard-coded columns:")
print(summary.round(2).to_string(index=False))
