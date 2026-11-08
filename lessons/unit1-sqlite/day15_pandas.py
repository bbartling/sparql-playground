"""Day 15, pandas: data quality before you trust a rule, then the Unit 1 challenge (a DAT rule).

    uv run python lessons/unit1-sqlite/day15_pandas.py

Checks on both AHUs: dropouts (temperatures that read exactly 0 degF), a setpoint that reads 0
while the fan runs, out-of-range values, flatlined sensors (the streak trick from Day 13), the
5-minute time step, and coverage per month. Then the rule: |discharge air temp - setpoint| >
2.78 degC (5 degF) while the fan runs, confirmed for 30 minutes (6 rows), with and without the
quality gate.
Compare the printout with day15_sql.py: the numbers should match.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"

PA_PER_INH2O = 249.08891  # the historian logged inches of water; the math is SI (pascals)
FLAT_ROWS = 12  # an identical value for 12 rows x 5 min = 1 hour while the fan runs is suspicious
TOL_C = 2.78  # |discharge - setpoint| above this is a fault (5 degF is 2.78 degC)
CONFIRM_ROWS = 6  # 6 rows x 5 min = 30 minutes
STEP_S = 300  # the historian logs every 5 minutes
ZERO_F_IN_C = (0 - 32.0) * 5.0 / 9.0  # what a dropout looks like after conversion: -17.777...
TEMP_RANGE_C = (-40.0, 60.0)  # a sensor's physical range
STATIC_RANGE_PA = (0.0, 1500.0)
SPEED_RANGE_PCT = (0.0, 100.0)

# 1. Load: both AHUs, the columns we need, in (equipment, time) order.
COLUMNS = [
    "timestamp_utc",
    "supply_fan_status",
    "supply_fan_speed_pct",
    "da_p_inwc",
    "discharge_air_temp_f",
    "dat_reset_f",
    "mixed_air_temp_f",
    "return_air_temp_f",
    "outside_air_temp_f",
]
frames = []
for equip in ("AHU_1", "AHU_2"):
    df = pd.read_csv(DATA / equip / "history_wide.csv", usecols=COLUMNS)
    df.insert(0, "equipment_id", equip)
    frames.append(df)
h = pd.concat(frames, ignore_index=True)
h = h.sort_values(["equipment_id", "timestamp_utc"], ignore_index=True)
eq = h["equipment_id"]
running = h["supply_fan_status"] == 1


def f_to_c(f):
    return (f - 32.0) * 5.0 / 9.0


def streaks(value):
    """Day 13's trick: the streak id (runs of equal values per AHU) and the row number inside it."""
    new_streak = value.ne(value.groupby(eq).shift()).astype(int)
    streak_id = new_streak.groupby(eq).cumsum()
    return streak_id, value.groupby([eq, streak_id]).cumcount() + 1


# 2. SI units. Keep the raw degF columns too: the dropout test must look at the raw value.
q = h[["equipment_id", "timestamp_utc", "supply_fan_status"]].copy()
q["dat_c"] = f_to_c(h["discharge_air_temp_f"])
q["dat_sp_c"] = f_to_c(h["dat_reset_f"])
q["mat_c"] = f_to_c(h["mixed_air_temp_f"])
q["rat_c"] = f_to_c(h["return_air_temp_f"])
q["oat_c"] = f_to_c(h["outside_air_temp_f"])
q["duct_static_pa"] = h["da_p_inwc"] * PA_PER_INH2O

# 3. Dropouts: a duct temperature that reads exactly 0 degF (-17.78 degC). Test the RAW value.
q["dropout"] = (
    (h["discharge_air_temp_f"] == 0) | (h["mixed_air_temp_f"] == 0) | (h["return_air_temp_f"] == 0)
).astype(int)
# The comparison trap: the converted value is -17.7777..., so == -17.78 never matches anything.
trap_exact = (q["dat_c"] == -17.78).astype(int)
trap_tolerance = ((q["dat_c"] - ZERO_F_IN_C).abs() < 0.01).astype(int)

# 4. A setpoint of 0 degF while the fan runs is not a real setpoint (a missing value, shown as 0).
q["sp_zero"] = (running & (h["dat_reset_f"] == 0)).astype(int)

# 5. Out of range: outside what the sensor can physically report.
temps = q[["dat_c", "mat_c", "rat_c", "oat_c"]]
bad_temp = ((temps < TEMP_RANGE_C[0]) | (temps > TEMP_RANGE_C[1])).any(axis=1)
bad_static = (q["duct_static_pa"] < STATIC_RANGE_PA[0]) | (q["duct_static_pa"] > STATIC_RANGE_PA[1])
bad_speed = (h["supply_fan_speed_pct"] < SPEED_RANGE_PCT[0]) | (
    h["supply_fan_speed_pct"] > SPEED_RANGE_PCT[1]
)
q["out_of_range"] = (bad_temp | bad_static | bad_speed).astype(int)

# 6. Flatlines: streaks of an identical discharge temperature, 1 h+ with the fan running throughout.
flat_id, q["flat_len"] = streaks(h["discharge_air_temp_f"])
island = h.groupby([eq, flat_id])["supply_fan_status"]
island_rows = island.transform("size")
island_running = island.transform("sum")
q["flatline"] = ((island_rows >= FLAT_ROWS) & (island_running == island_rows)).astype(int)
flat_episodes = (
    q.assign(flat_id=flat_id)[q["flatline"] == 1]
    .groupby(["equipment_id", "flat_id"])
    .agg(start_utc=("timestamp_utc", "min"), rows=("flat_len", "max"), value_c=("dat_c", "first"))
    .reset_index()
)

# 7. Time step: seconds since the previous row of the same AHU. Every step should be 300.
ts = pd.to_datetime(h["timestamp_utc"], utc=True)
epoch_s = (ts - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()
q["step_s"] = epoch_s.groupby(eq).diff()
q["epoch_s"] = epoch_s

# 8. One line of checks per AHU.
checks = q.groupby("equipment_id").agg(
    dropout_rows=("dropout", "sum"),
    sp_zero_rows=("sp_zero", "sum"),
    out_of_range_rows=("out_of_range", "sum"),
    flatline_rows=("flatline", "sum"),
    step_gaps=("step_s", lambda s: int((s != STEP_S).sum() - s.isna().sum())),
    max_step_s=("step_s", "max"),
)
checks["flat_episodes"] = flat_episodes.groupby("equipment_id").size()
checks["dat_eq_minus_17_78"] = trap_exact.groupby(eq).sum()
checks["dat_within_0_01_of_zero_f"] = trap_tolerance.groupby(eq).sum()
checks = checks.fillna({"flat_episodes": 0}).reset_index()

# 9. Coverage per AHU per month: rows present vs rows expected, first to last timestamp.
q["month"] = q["timestamp_utc"].str[:7]
q["running"] = running.astype(int)
coverage = (
    q.groupby(["equipment_id", "month"])
    .agg(
        rows=("timestamp_utc", "size"),
        first_s=("epoch_s", "min"),
        last_s=("epoch_s", "max"),
        running_rows=("running", "sum"),
        dropout_rows=("dropout", "sum"),
        sp_zero_rows=("sp_zero", "sum"),
        flat_rows=("flatline", "sum"),
    )
    .reset_index()
)
coverage["expected_rows"] = (coverage["last_s"] - coverage["first_s"]) / STEP_S + 1
coverage["coverage_pct"] = 100.0 * coverage["rows"] / coverage["expected_rows"]
coverage = coverage.drop(columns=["first_s", "last_s"])

# 10. Challenge: |discharge - setpoint| > 2.78 degC while running, confirmed for 6 rows.
# Two variants: "ungated" trusts every row; "gated" skips dropouts and the missing (0) setpoint.
err_c = (q["dat_c"] - q["dat_sp_c"]).abs()
variants = {
    "ungated": running & (err_c > TOL_C),
    "gated": running & (q["dropout"] == 0) & (q["sp_zero"] == 0) & (err_c > TOL_C),
}
parts = []
for name, flag in variants.items():
    raw = flag.astype(int)
    streak_id, streak_len = streaks(raw)
    fault = ((raw == 1) & (streak_len >= CONFIRM_ROWS)).astype(int)
    parts.append(
        q[["equipment_id", "timestamp_utc", "month"]].assign(
            variant=name, raw_fault=raw, streak_id=streak_id, fault=fault
        )
    )
dat_rows = pd.concat(parts, ignore_index=True)
dat_rows["ungated_fault"] = (dat_rows["variant"] == "ungated") * dat_rows["fault"]
dat_rows["gated_fault"] = (dat_rows["variant"] == "gated") * dat_rows["fault"]
dat_month = (
    dat_rows.groupby(["equipment_id", "month"])[["ungated_fault", "gated_fault"]]
    .sum()
    .mul(5 / 60)
    .reset_index()
)
dat_month = dat_month.rename(
    columns={"ungated_fault": "ungated_fault_h", "gated_fault": "gated_fault_h"}
)
dat_rows = dat_rows.drop(columns=["ungated_fault", "gated_fault", "month"])

RESULTS = {
    "quality_rows": q.drop(columns=["epoch_s", "month", "running"]),
    "checks": checks,
    "flat_episodes": flat_episodes,
    "coverage": coverage,
    "dat_rows": dat_rows,
    "dat_month": dat_month,
}

print("Quality checks per AHU:")
print(checks.round(2).T.to_string(header=False))
print("\nThe 7 dropout rows on AHU_1 (every sensor reads 0 degF = -17.78 degC):")
dropped = q[(q["equipment_id"] == "AHU_1") & (q["dropout"] == 1)]
print(dropped[["timestamp_utc", "dat_c", "dat_sp_c"]].round(2).to_string(index=False))
print("\nCoverage per AHU per month (AHU_1):")
print(coverage[coverage["equipment_id"] == "AHU_1"].round(1).to_string(index=False))
print("\nChallenge: DAT rule fault hours per AHU per month (ungated vs gated):")
print(dat_month.round(2).to_string(index=False))
print("\nTotals:")
print(
    dat_month.groupby("equipment_id")[["ungated_fault_h", "gated_fault_h"]]
    .sum()
    .round(2)
    .to_string()
)
