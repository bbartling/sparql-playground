# Day 25 (pandas): FC1 driven by the model, through the app's API. No column names or ids below.
# Run from the repo root (once: uv run bldgts model build && uv run bldgts bootstrap):
#     uv run python lessons/unit3-modeling/day25_pandas.py
#
# FastAPI's TestClient runs this repo's app (`bldgts serve`) inside this script: requests go
# straight into the app, with no server and no network. SPARQL finds FC1's inputs by tag, the
# API returns each point's series, and then Day 14's rule runs.

from pathlib import Path

import pandas as pd
from bldgts.api.app import create_app
from bldgts.settings import Settings
from fastapi.testclient import TestClient

PA_PER_INH2O = 249.08891  # the historian logged inches of water; fault math is SI
TOLERANCE_PA = 25  # how far below setpoint counts as "too low"
CONFIRM_ROWS = 2  # the fault must last 2 rows in a row (10 minutes)

# The app's settings: read model/building_50.ttl and var/timeseries.sqlite, change nothing
settings = Settings(
    bootstrap_on_startup=False,  # the database is already loaded (bldgts bootstrap)
    allow_mutations=False,  # read-only
    snapshot_path=Path("var/day25-unused-snapshot.ttl"),  # start from the model file itself
    log_level="WARNING",
    log_json=False,
)

# 1. Ask the model for FC1's inputs: the rule's three roles, on every AHU
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
with TestClient(create_app(settings)) as api:
    response = api.post("/api/sparql", json={"query": fc1_query})
    input_rows = []
    for binding in response.json()["results"]["results"]["bindings"]:
        input_rows.append(
            {
                "equipment_id": binding["equip"]["value"].split("#")[-1],  # after the #: AHU_1
                "role": binding["role"]["value"],
                "point_id": binding["point"]["value"].split("#")[-1],
                "timeseries_id": binding["timeseries_id"]["value"],
            }
        )
    fc1_inputs = pd.DataFrame(input_rows).sort_values(["equipment_id", "role"])

    # 2. One GET per point. The API finds the point's reference and reads the series for us.
    pieces = []
    for _, point in fc1_inputs.iterrows():
        body = api.get("/api/points/" + point["point_id"] + "/timeseries").json()
        one_series = pd.DataFrame(body["samples"], columns=["ts", "value"])
        one_series["equipment_id"] = point["equipment_id"]
        one_series["role"] = point["role"]
        pieces.append(one_series)
        same_id = body["timeseries_id"] == point["timeseries_id"]
        print(
            "GET", point["point_id"], "->", len(one_series), "rows, same id as the model:", same_id
        )

# 3. Long -> wide (Day 23): one row per AHU and time, one column per role
long = pd.concat(pieces)
wide = long.pivot(index=["equipment_id", "ts"], columns="role", values="value").reset_index()

# 4. Day 14's rule, per AHU, with the pressures in pascals
wide["static_pa"] = wide["duct-static-pressure"] * PA_PER_INH2O
wide["setpoint_pa"] = wide["duct-static-pressure-sp"] * PA_PER_INH2O
fan_on = wide["fan-status"] == 1
too_low = wide["static_pa"] < wide["setpoint_pa"] - TOLERANCE_PA
wide["raw_fault"] = fan_on & too_low
changed = wide["raw_fault"] != wide["raw_fault"].shift()
new_ahu = wide["equipment_id"] != wide["equipment_id"].shift()
wide["streak_id"] = (changed | new_ahu).cumsum()
wide["row_in_streak"] = wide.groupby("streak_id").cumcount() + 1
wide["fault"] = wide["raw_fault"] & (wide["row_in_streak"] >= CONFIRM_ROWS)

# 5. Hours (rows x 5 minutes) and episodes per AHU
wide["confirmed_streak"] = wide["streak_id"].where(wide["fault"])
summary = wide.groupby("equipment_id").agg(
    raw_fault_h=("raw_fault", "sum"),
    confirmed_fault_h=("fault", "sum"),
    episodes=("confirmed_streak", "nunique"),
)
summary["raw_fault_h"] = summary["raw_fault_h"] * 5 / 60
summary["confirmed_fault_h"] = summary["confirmed_fault_h"] * 5 / 60
summary = summary.reset_index()
fc1_per_row = wide[["equipment_id", "ts", "raw_fault", "fault"]]

print("\nFC1's inputs, found by the model:")
print(fc1_inputs.to_string(index=False))
print("\nRows after the pivot:", len(wide))
print("\nFC1 per AHU (hours, episodes). Day 14 got the same from hard-coded columns:")
print(summary.round(2).to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"fc1_inputs": fc1_inputs, "fc1_per_row": fc1_per_row, "fc1_summary": summary}
