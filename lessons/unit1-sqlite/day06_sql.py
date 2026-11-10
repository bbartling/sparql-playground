# Day 6 (SQL): convert AHU_1's US units to SI (degC, Pa, fractions 0-1).
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day06_sql.py

import sqlite3

conn = sqlite3.connect("var/lessons.sqlite")

settings = {"pa_per_inh2o": 249.08891}  # 1 inch of water = 249.09 pascals

# 1-4. Convert each column to SI and average it, all in one query
query = """
SELECT AVG((discharge_air_temp_f - 32) * 5 / 9.0),   -- a temperature: minus 32
       AVG((outside_air_temp_f - 32) * 5 / 9.0),
       AVG(da_p_inwc * :pa_per_inh2o),               -- a pressure: multiply
       AVG(supply_fan_speed_pct / 100.0),            -- percent -> 0 to 1
       AVG((discharge_air_temp_f - dat_reset_f) * 5 / 9.0),         -- a difference: no 32
       AVG(((discharge_air_temp_f - dat_reset_f) - 32) * 5 / 9.0)   -- the common mistake
FROM ahu_1
"""
dat_c, oat_c, static_pa, fan_speed, error_k, error_wrong_k = conn.execute(
    query, settings
).fetchone()

print("Average discharge air temperature (C):", round(dat_c, 3))
print("Average outside air temperature (C):  ", round(oat_c, 3))
print("Average duct static pressure (Pa):    ", round(static_pa, 3))
print("Average supply fan speed (fraction):  ", round(fan_speed, 3))
print("Average DAT error, right (K):         ", round(error_k, 3))
print("Average DAT error, wrong (K):         ", round(error_wrong_k, 3))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "dat_c": dat_c,
    "oat_c": oat_c,
    "static_pa": static_pa,
    "fan_speed_frac": fan_speed,
    "dat_error_k": error_k,
    "dat_error_wrong_k": error_wrong_k,
}
