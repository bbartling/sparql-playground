# Day 15 (pandas): data-quality checks, then the Unit 1 challenge: a discharge air temp rule.
# Run from the repo root:
#     uv run python lessons/unit1-sqlite/day15_pandas.py

import pandas as pd

FLAT_ROWS = 12  # the same value for 12 rows x 5 min = 1 hour, fan running, is suspicious
TOLERANCE_C = 2.78  # more than this far from setpoint is a fault (5 degF = 2.78 degC)
CONFIRM_ROWS = 6  # 6 rows x 5 min = 30 minutes
TEMP_RANGE_C = (-40, 60)  # what a temperature sensor can physically report
ZERO_F_IN_C = (0 - 32) * 5 / 9  # a dropout, after converting: -17.777...

# 1. Read AHU_1's data, only the columns we need
columns = [
    "timestamp_utc",
    "supply_fan_status",
    "discharge_air_temp_f",
    "dat_reset_f",  # the discharge air temperature setpoint
    "mixed_air_temp_f",
    "return_air_temp_f",
]
df = pd.read_csv("data/BUILDING_50/AHU_1/history_wide.csv", usecols=columns)
fan_on = df["supply_fan_status"] == 1

# 2. Convert temperatures to degC
df["dat_c"] = (df["discharge_air_temp_f"] - 32) * 5 / 9
df["dat_setpoint_c"] = (df["dat_reset_f"] - 32) * 5 / 9

# 3. Dropout: a temperature that reads exactly 0 degF (test the raw value, before converting)
df["dropout"] = (
    (df["discharge_air_temp_f"] == 0)
    | (df["mixed_air_temp_f"] == 0)
    | (df["return_air_temp_f"] == 0)
)
exact_matches = (df["dat_c"] == -17.78).sum()  # the trap: never matches
tolerance_matches = ((df["dat_c"] - ZERO_F_IN_C).abs() < 0.01).sum()

# 4. Missing setpoint: the fan runs but the setpoint reads 0 degF
df["setpoint_zero"] = fan_on & (df["dat_reset_f"] == 0)

# 5. Out of range: a discharge temperature no sensor could report
out_of_range = (df["dat_c"] < TEMP_RANGE_C[0]) | (df["dat_c"] > TEMP_RANGE_C[1])

# 6. Flatline: the same discharge temperature for 12+ rows while the fan ran the whole time
flat_id = (df["discharge_air_temp_f"] != df["discharge_air_temp_f"].shift()).cumsum()
streak_rows = df.groupby(flat_id)["timestamp_utc"].transform("size")
streak_fan_rows = df.groupby(flat_id)["supply_fan_status"].transform("sum")
flatline = (streak_rows >= FLAT_ROWS) & (streak_fan_rows == streak_rows)
flat_episodes = flat_id[flatline].nunique()

# 7. Time step: seconds between rows. Every step should be 300.
seconds = pd.to_datetime(df["timestamp_utc"]).diff().dt.total_seconds()
step_gaps = (seconds.dropna() != 300).sum()

# 8. The rule: fan on and |discharge - setpoint| > 2.78 degC, confirmed for 6 rows.
# "ungated" trusts every row; "gated" skips dropout rows and rows with no setpoint.
error_c = (df["dat_c"] - df["dat_setpoint_c"]).abs()
raw_ungated = fan_on & (error_c > TOLERANCE_C)
raw_gated = raw_ungated & ~df["dropout"] & ~df["setpoint_zero"]

for name, raw in [("ungated", raw_ungated), ("gated", raw_gated)]:
    streak_id = (raw != raw.shift()).cumsum()
    row_in_streak = raw.groupby(streak_id).cumcount() + 1
    df[name + "_fault"] = raw & (row_in_streak >= CONFIRM_ROWS)

# 9. Fault hours: rows x 5 / 60, in total and per month
df["month"] = df["timestamp_utc"].str[:7]
monthly = df.groupby("month")[["ungated_fault", "gated_fault"]].sum() * 5 / 60
monthly.columns = ["ungated_fault_h", "gated_fault_h"]
monthly = monthly.reset_index()
ungated_h = df["ungated_fault"].sum() * 5 / 60
gated_h = df["gated_fault"].sum() * 5 / 60

print("AHU_1 data-quality checks")
print("  dropout rows (a temperature reads 0 F):", df["dropout"].sum())
print("  setpoint reads 0 while the fan runs:   ", df["setpoint_zero"].sum())
print("  discharge temp out of range:           ", out_of_range.sum())
print("  flatline rows (1 h+ the same value):   ", flatline.sum())
print("  flatline episodes:                     ", flat_episodes)
print("  time steps that are not 300 s:         ", step_gaps)
print("  longest time step (s):                 ", seconds.max())
print("  dat_c == -17.78 matches:               ", exact_matches)
print("  dat_c within 0.01 of -17.78 matches:   ", tolerance_matches)
print("Challenge: discharge air temp fault hours")
print(monthly.round(2).to_string(index=False))
print("  total, trusting every row (h):", round(ungated_h, 2))
print("  total, quality gate on (h):   ", round(gated_h, 2))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "dropout_rows": df["dropout"].sum(),
    "setpoint_zero_rows": df["setpoint_zero"].sum(),
    "out_of_range_rows": out_of_range.sum(),
    "flatline_rows": flatline.sum(),
    "flat_episodes": flat_episodes,
    "step_gaps": step_gaps,
    "max_step_s": seconds.max(),
    "exact_matches": exact_matches,
    "tolerance_matches": tolerance_matches,
    "ungated_fault_h": ungated_h,
    "gated_fault_h": gated_h,
    "monthly_fault_hours": monthly,
}
