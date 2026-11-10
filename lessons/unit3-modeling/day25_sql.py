# Day 25 (SQL): FC1 driven by the model, straight from the app's database. No column names or ids
# below.
# Run from the repo root (once: uv run bldgts model build && uv run bldgts bootstrap):
#     uv run python lessons/unit3-modeling/day25_sql.py
#
# The same SPARQL as day25_pandas.py finds FC1's inputs (rdflib runs it: SQL can't read RDF).
# Their UUIDs go into a TEMP table, and one query reads `samples`, pivots and runs Day 14's rule.

import sqlite3

import pandas as pd
from rdflib import Graph

# 1. Ask the model for FC1's inputs: the rule's three roles, on every AHU
g = Graph()
g.parse("model/building_50.ttl")
fc1_query = """
PREFIX bts: <https://example.org/openfdd/bldgts#>
PREFIX ref: <https://brickschema.org/schema/Brick/ref#>
SELECT ?equip ?role ?point ?timeseries_id WHERE {
  ?point ref:hasExternalReference ?ref .
  ?ref ref:hasTimeseriesId ?timeseries_id .
  ?point bts:hasHaystackTag ?role_tag .
  ?role_tag bts:tagName "ofddRole" ; bts:tagValue ?role .
  FILTER(?role IN ("fan-status", "duct-static-pressure", "duct-static-pressure-sp"))
  ?point bts:hasHaystackTag ?equip_tag .
  ?equip_tag bts:tagName "equipRef" ; bts:tagValue ?equip .
}
"""
input_rows = []
for row in g.query(fc1_query):
    input_rows.append(
        {
            "equipment_id": str(row.equip).split("#")[-1],  # keep the part after the #: AHU_1
            "role": str(row.role),
            "point_id": str(row.point).split("#")[-1],
            "timeseries_id": str(row.timeseries_id),
        }
    )
fc1_inputs = pd.DataFrame(input_rows).sort_values(["equipment_id", "role"])

# 2. The app's database, read-only. The model's answer goes into a TEMP table `fc1_input`.
conn = sqlite3.connect("file:var/timeseries.sqlite?mode=ro", uri=True)
conn.execute("CREATE TEMP TABLE fc1_input (equipment_id TEXT, role TEXT, timeseries_id TEXT)")
for _, point in fc1_inputs.iterrows():
    conn.execute(
        "INSERT INTO fc1_input VALUES (?, ?, ?)",
        [point["equipment_id"], point["role"], point["timeseries_id"]],
    )

settings = {
    "pa_per_inh2o": 249.08891,  # the historian logged inches of water; fault math is SI
    "tolerance_pa": 25,  # how far below setpoint counts as "too low"
    "confirm_rows": 2,  # the fault must last 2 rows in a row (10 minutes)
}

# 3-4. One query, one WITH block per step: long -> wide, pascals, then Day 14's rule
fc1_sql = """
CREATE TEMP TABLE fc1 AS
WITH
step3 AS (                -- 3. long -> wide: one row per AHU and time, one column per role
  SELECT i.equipment_id, s.ts,
         MAX(CASE WHEN i.role = 'fan-status' THEN s.value END) AS fan_status,
         MAX(CASE WHEN i.role = 'duct-static-pressure' THEN s.value END) AS static_inwc,
         MAX(CASE WHEN i.role = 'duct-static-pressure-sp' THEN s.value END) AS setpoint_inwc
  FROM samples AS s
  JOIN fc1_input AS i ON i.timeseries_id = s.timeseries_id
  GROUP BY i.equipment_id, s.ts
),
step4a AS (               -- 4a. raw fault, with the pressures in pascals
  SELECT equipment_id, ts,
         fan_status = 1
           AND static_inwc * :pa_per_inh2o < setpoint_inwc * :pa_per_inh2o - :tolerance_pa
           AS raw_fault
  FROM step3
),
step4b AS (               -- 4b. mark rows where the value changes (a new streak starts)
  SELECT *,
         raw_fault IS NOT LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts)
           AS new_streak
  FROM step4a
),
step4c AS (               -- 4c. a running total of those marks numbers each streak
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id
  FROM step4b
)
SELECT equipment_id, ts, raw_fault, streak_id,   -- 4d. count rows in each streak, confirm
       raw_fault = 1
         AND ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts)
             >= :confirm_rows AS fault
FROM step4c
"""
conn.execute(fc1_sql, settings)

# 5. Hours (rows x 5 minutes) and episodes per AHU
summary_sql = """
SELECT equipment_id,
       SUM(raw_fault) * 5 / 60.0 AS raw_fault_h,
       SUM(fault) * 5 / 60.0 AS confirmed_fault_h,
       COUNT(DISTINCT CASE WHEN fault = 1 THEN streak_id END) AS episodes
FROM fc1
GROUP BY equipment_id
"""
summary = pd.read_sql_query(summary_sql, conn)
fc1_per_row = pd.read_sql_query("SELECT equipment_id, ts, raw_fault, fault FROM fc1", conn)

print("FC1's inputs, found by the model:")
print(fc1_inputs.to_string(index=False))
print("\nRows after the pivot:", len(fc1_per_row))
print("\nFC1 per AHU (hours, episodes). Day 14 got the same from hard-coded columns:")
print(summary.round(2).to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"fc1_inputs": fc1_inputs, "fc1_per_row": fc1_per_row, "fc1_summary": summary}
