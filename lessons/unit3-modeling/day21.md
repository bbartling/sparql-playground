# Day 21 — Why hard-coded names break: one AHU's `mad_c` is the other's `mad_c_pct`

**Goal:** see a rule that works on one AHU fail on the next, then fix it with the smallest possible model: a map
from *role* ("outside-air damper") to *column* ("mad_c" or "mad_c_pct").

## Read

Weeks 1–4 typed column names into every script: `supply_fan_status`, `da_p_inwc`, `mad_c`. That was honest and it
worked, because we picked columns that happen to exist under the same name on both AHUs. Not every column does.
AHU_1's outside-air damper command is `mad_c`. AHU_2's is `mad_c_pct`. Same physical thing, same unit (percent open),
different name in the BAS export. Ask both AHUs for `mad_c` and one of them fails:

| | `day21_pandas.py` | `day21_sql.py` |
|---|---|---|
| ask for `mad_c` on AHU_2 | `pd.read_csv(..., usecols=[..., "mad_c"])` raises `ValueError` | `SELECT mad_c FROM ahu_2` raises `no such column` |

You can patch this with `if equip == "AHU_2": col = "mad_c_pct"`. Do that for 30 columns and 40 AHUs and the `if`s
*are* the data model, written in code and copied into every script. A change of building means editing every script.

The way out is to keep the facts **out of the rule**. The rule says "I need the outside-air damper and the fan
status". Something else, a **model**, says which column holds each. The smallest model is already in the data folder:
`data/BUILDING_50/AHU_*/column_map.json`, a dictionary from role to column:

```json
"outside-air-damper": "mad_c"          // AHU_1
"outside-air-damper": "mad_c_pct"      // AHU_2
```

Open-FDD calls the left-hand side a **role** (`fan-status`, `duct-static-pressure`, ...). Now the script loops over
AHUs, looks up the column for each role, and reads *that*. One script, any number of AHUs, and the only thing that
changes between buildings is the map.

How each half uses the map:

| Step | `day21_pandas.py` | `day21_sql.py` |
|---|---|---|
| role → column | `col_map[equip][role]` | the same dict, from the same JSON |
| load by role | `read_csv(usecols=[...]).rename(columns={col: shared_name})` | `SELECT "mad_c_pct" AS oa_damper_pct FROM "ahu_2"` |
| stack AHUs | `pd.concat` | `UNION ALL` |
| summary | `groupby("equipment_id").agg(...)` | `GROUP BY equipment_id` |

**Renaming vs building SQL.** pandas just renames the loaded columns to shared names, so everything after the load is
identical for both AHUs. SQL has no "rename after the fact": the query text itself must differ per AHU, so the
script *builds* it from the map. That brings a rule you should never forget: a **value** can be a bound parameter
(`:eq0`), but an **identifier** (a table or column name) cannot. `SELECT :col FROM t` returns the string, not the
column. So identifiers get pasted into the SQL text, and text pasted into SQL is how SQL injection happens. The
defence is a **whitelist**: accept a name only if it is a real column of the real table (`PRAGMA table_info`), then
quote it (`"`, doubled if it appears inside). The script's `quote_ident` does both. Today the map is a file you trust,
but the habit costs nothing and matters the first time a name comes from a user or a web form.

## Run

```bash
uv run python lessons/course.py run 21
```

That runs [`day21_pandas.py`](day21_pandas.py), then [`day21_sql.py`](day21_sql.py). It reads only the CSVs and
`var/lessons.sqlite`. Both print the failed hard-coded attempt, the damper column per AHU and the summary:

```
Hard-coded `mad_c` on each AHU:        AHU_1 worked, AHU_2 did not
Damper column per AHU, from column_map.json:
equipment_id damper_column
       AHU_1         mad_c
       AHU_2     mad_c_pct
Outside-air damper while the supply fan runs (one script, both AHUs):
equipment_id damper_column  run_rows  run_hours  mean_damper_pct  open_over_50_h  closed_h
       AHU_1         mad_c     18893    1574.42            42.88          605.83    357.83
       AHU_2     mad_c_pct     17995    1499.58            51.90          696.42    347.75
```

(The error *message* differs between pandas and SQLite; only whether it worked is compared.) While the fan runs,
AHU_1's damper averages 43% open and AHU_2's 52%. Both spend about 350 running hours fully closed.

## Try it

1. Add the mixed-air temperature (role `mixed-air-temp`) to both scripts and report its mean while the fan runs.
   Which lines change? Which don't?
2. In the SQL script, change one role's column in the map to `"mad_c; DROP TABLE ahu_1"` (just in the Python dict).
   What happens, and why is that good?

<details><summary>Answers</summary>

1. Add `"mixed-air-temp": "mat"` to `ROLES` (the shared name is yours to choose) and one more aggregate in the
   summary. The loading code doesn't change: it loops over `ROLES`. In the SQL script the generated `SELECT` gains one
   more column automatically. Adding a role is data, not control flow.
2. `quote_ident` raises `ValueError: unknown column ...` before any SQL runs, because that string is not a column of
   the table. Without the whitelist, the string would have been pasted into the query text.

</details>

## Why it matters

A column map is a model: it separates *what the rule needs* from *where this building keeps it*. But it is one JSON
file per AHU, it only knows columns in one CSV, and it can't say that the supply fan is *part of* AHU_1 or that a
sensor reads in °F. Tomorrow you meet a richer model: Haystack tags written as RDF.
