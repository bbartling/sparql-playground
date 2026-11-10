# Day 10 (SQL): Open-FDD events. Episodes per rule, then which rows fall inside an episode.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day10_sql.py

import sqlite3

import pandas as pd

conn = sqlite3.connect("var/lessons.sqlite")

# 1-2. Count episodes and add up their minutes, per rule (fdd_events has one row per episode)
per_rule_query = """
SELECT rule_name,
       COUNT(*) AS episodes,
       SUM(duration_min) / 60.0 AS hours
FROM fdd_events
WHERE hvac_system = 'bld_50_AHU_1'
GROUP BY rule_name
ORDER BY rule_name
"""
per_rule = pd.read_sql_query(per_rule_query, conn)

# 3-4. Count the history rows that have an fc13 episode around them (start <= time <= end).
#      The timestamps are text in one format, so comparing the text compares the times.
rows_query = """
SELECT COUNT(*)
FROM ahu_1 AS h
WHERE EXISTS (
    SELECT 1
    FROM fdd_events AS e
    WHERE e.hvac_system = 'bld_50_AHU_1'
      AND e.rule_name = 'fc13'
      AND h.timestamp_utc BETWEEN e.start_time_utc AND e.end_time_utc
)
"""
rows_in_episode = conn.execute(rows_query).fetchone()[0]

# 5. Each row is 5 minutes, so rows x 5 / 60 = hours
covered_hours = rows_in_episode * 5 / 60
summed_hours = per_rule[per_rule["rule_name"] == "fc13"]["hours"].iloc[0]

print(per_rule.round(1).to_string(index=False))
print("fc13 rows inside an episode:", rows_in_episode)
print("Hours those rows cover (5 min each):", round(covered_hours, 1))
print("Hours if you add up every episode:  ", round(summed_hours, 1), "(episodes overlap)")

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "per_rule": per_rule,
    "rows_in_episode": rows_in_episode,
    "covered_hours": covered_hours,
    "summed_hours": summed_hours,
}
