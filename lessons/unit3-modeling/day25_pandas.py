"""Day 25, pandas: FC1 driven by the model, through the app's API. No column names or ids in the
code.

    uv run python lessons/unit3-modeling/day25_pandas.py

Needs var/timeseries.sqlite and model/building_50.ttl (`uv run bldgts model build && uv run bldgts
bootstrap`). lab.Api runs the repo's FastAPI app in-process (no server, no network). SPARQL finds
FC1's input points by tag; each point's series comes from GET /api/points/{id}/timeseries; then
Day 14's FC1 logic runs in SI. Compare the printout with day25_sql.py (and with Day 14: AHU_1
114.25 h in 53 episodes, AHU_2 1.50 h)."""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lessons"))
import lab  # noqa: E402

TOL_PA = 25.0  # how far below setpoint counts as a fault (~0.1 inH2O)
CONFIRM_ROWS = 2  # 2 rows x 5 min = 10 minutes before a fault counts

# 1. Ask the model for FC1's inputs. Start from the points that have a timeseries reference: rdflib
#    evaluates patterns roughly in order, so a selective first pattern keeps every join small.
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

    # 2. One GET per series. The API reports the UUID it served, which should be the model's UUID.
    series = {}
    for r in found.itertuples():
        s = api.timeseries(r.point_id)
        series[(r.equipment_id, r.role)] = s.assign(equipment_id=r.equipment_id, role=r.role)
        same_id = s.attrs["timeseries_id"] == r.timeseriesId  # shown in the printout
        print(f"GET {r.point_id:<16} -> {len(s):>6} samples, API id == model id: {same_id}")

# 3. Long -> wide (Day 23), then SI (Day 6/14): inH2O -> Pa. Fan status is already 0/1.
long = pd.concat(series.values(), ignore_index=True)
wide = long.pivot(index=["equipment_id", "ts"], columns="role", values="value").reset_index()
h = pd.DataFrame(
    {
        "equipment_id": wide["equipment_id"],
        "ts": wide["ts"],
        "fan_status": wide["fan-status"],
        "duct_static_pa": lab.inh2o_to_pa(wide["duct-static-pressure"]),
        "duct_static_sp_pa": lab.inh2o_to_pa(wide["duct-static-pressure-sp"]),
    }
).sort_values(["equipment_id", "ts"], ignore_index=True)

# 4. Day 14's FC1: gate + raw fault, streak id, row within the streak, confirm
eq = h["equipment_id"]
raw = ((h["fan_status"] == 1) & (h["duct_static_pa"] < h["duct_static_sp_pa"] - TOL_PA)).astype(int)
new_streak = raw.ne(raw.groupby(eq).shift()).astype(int)
streak_id = new_streak.groupby(eq).cumsum()
streak_len = raw.groupby([eq, streak_id]).cumcount() + 1
fault = ((raw == 1) & (streak_len >= CONFIRM_ROWS)).astype(int)
fc1 = h[["equipment_id", "ts"]].assign(raw_fault=raw, streak_id=streak_id, fault=fault)

# 5. Aggregate: rows x 5 minutes = hours, and confirmed episodes
hours = fc1.groupby("equipment_id")[["raw_fault", "fault"]].sum() * 5 / 60
episodes = fc1[fc1["fault"] == 1].groupby("equipment_id")["streak_id"].nunique()
summary = (
    hours.rename(columns={"raw_fault": "raw_fault_h", "fault": "confirmed_fault_h"})
    .assign(episodes=episodes)
    .fillna({"episodes": 0})
    .reset_index()
)

RESULTS = {"fc1_inputs": fc1_inputs, "fc1_per_row": fc1, "fc1_summary": summary}

print("\nFC1's inputs, found by the model:")
print(fc1_inputs.to_string(index=False))
print(f"\n{len(h):,} rows of input after the pivot.")
print("\nFC1 per AHU (hours, episodes). Day 14 printed the same numbers from hard-coded columns:")
print(summary.round(2).to_string(index=False))
