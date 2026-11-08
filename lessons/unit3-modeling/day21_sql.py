"""Day 21, SQL: an outside-air damper summary across AHUs whose column names differ.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit3-modeling/day21_sql.py

The same computation as day21_pandas.py, done by SQLite. The column names come from
column_map.json, so the SQL text is *built*. A value can be a bound parameter (:eq0), but a table
or column name cannot, so every name from the map is checked against the table's real columns (a
whitelist) and then quoted. Compare the printout with day21_pandas.py: the numbers should match."""

import json
import os
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"
DB = Path(os.environ.get("LESSONS_DB", ROOT / "var" / "lessons.sqlite"))
if not DB.exists():
    raise SystemExit(f"{DB} not found. Run:  uv run python lessons/course.py setup")
conn = sqlite3.connect(DB)

EQUIPMENT = {"AHU_1": "ahu_1", "AHU_2": "ahu_2"}  # equipment id -> table (the whitelist of tables)

# 1. The hard-coded way: ask for `mad_c` on every AHU. It works for AHU_1 and fails for AHU_2.
tried = []
for equip, table in EQUIPMENT.items():
    try:
        conn.execute(f'SELECT timestamp_utc, supply_fan_status, mad_c FROM "{table}" LIMIT 5')
        tried.append((equip, 1, "ok"))
    except sqlite3.OperationalError as err:
        tried.append((equip, 0, str(err)))
hardcoded = pd.DataFrame(tried, columns=["equipment_id", "worked", "message"])

# 2. The first model: column_map.json says which column holds each role, per AHU.
ROLES = {"fan-status": "fan_status", "outside-air-damper": "oa_damper_pct"}  # role -> our own name
col_map = {e: json.loads((DATA / e / "column_map.json").read_text())["points"] for e in EQUIPMENT}
damper_columns = pd.DataFrame(
    [(e, col_map[e]["outside-air-damper"]) for e in EQUIPMENT],
    columns=["equipment_id", "damper_column"],
)


def quote_ident(name: str, allowed: set[str]) -> str:
    """Identifiers can't be bound as parameters: accept a name that really exists, then quote it."""
    if name not in allowed:
        raise ValueError(f"unknown column {name!r}")
    return '"' + name.replace('"', '""') + '"'


# 3. Load by role: build one SELECT per AHU from the map, and stack them with UNION ALL.
selects, params = [], {}
for i, (equip, table) in enumerate(EQUIPMENT.items()):
    real = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
    cols = {name: quote_ident(col_map[equip][role], real) for role, name in ROLES.items()}
    params[f"eq{i}"] = equip  # a value, so it is bound
    selects.append(
        f"SELECT :eq{i} AS equipment_id, timestamp_utc, "
        + ", ".join(f"{cols[name]} AS {name}" for name in ROLES.values())
        + f' FROM "{table}"'
    )
OA_SQL = "CREATE TEMP TABLE oa AS " + "\nUNION ALL\n".join(selects)
conn.execute(OA_SQL, params)

# 4. One summary for both AHUs: only rows where the supply fan runs
SUMMARY_SQL = """
SELECT o.equipment_id, d.damper_column,
       count(*)                                    AS run_rows,
       count(*) * 5 / 60.0                         AS run_hours,
       avg(o.oa_damper_pct)                        AS mean_damper_pct,
       sum(o.oa_damper_pct > 50) * 5 / 60.0        AS open_over_50_h,
       sum(o.oa_damper_pct <= 0) * 5 / 60.0        AS closed_h
FROM oa o
JOIN (SELECT :e1 AS equipment_id, :c1 AS damper_column
      UNION ALL SELECT :e2, :c2) d ON d.equipment_id = o.equipment_id
WHERE o.fan_status = 1
GROUP BY o.equipment_id
ORDER BY o.equipment_id
"""
dc = dict(zip(damper_columns.equipment_id, damper_columns.damper_column, strict=True))
summary = pd.read_sql_query(
    SUMMARY_SQL, conn, params={"e1": "AHU_1", "c1": dc["AHU_1"], "e2": "AHU_2", "c2": dc["AHU_2"]}
)

RESULTS = {
    "hardcoded_worked": hardcoded[["equipment_id", "worked"]],
    "damper_columns": damper_columns,
    "damper_summary": summary,
}

print("Hard-coded `mad_c` on each AHU:")
print(hardcoded.to_string(index=False))
print("\nDamper column per AHU, from column_map.json:")
print(damper_columns.to_string(index=False))
print("\nThe SQL built from the map:")
print(OA_SQL)
print("\nOutside-air damper while the supply fan runs (one query, both AHUs):")
print(summary.round(2).to_string(index=False))
