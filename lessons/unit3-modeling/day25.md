# Day 25 — Model-driven FC1 through the app's API (week 5 challenge)

**Goal:** run Day 14's FC1 rule with no column names and no ids written in the code: SPARQL finds the inputs, the
app's API (or SQL on its database) supplies the series. Then run the same rule against the CSV storage from Day 24.

## Read

Day 14 hard-coded `supply_fan_status`, `da_p_inwc` and `da_p_setpoint_inwc`. This week replaced each hard-coded fact
with a lookup: roles (Day 21), tags in RDF (Day 22), stable ids (Day 23), references to stores (Day 24). Today they
all work together.

**FastAPI's `TestClient`** runs this repo's app (`bldgts serve`) inside the Python process: requests go straight
into the app, no server and no network. The app reads the model `model/building_50.ttl` and the database
`var/timeseries.sqlite`; the pandas script starts it read-only (`allow_mutations=False`). We use two of its routes:

- `POST /api/sparql` runs SPARQL against the model and returns the standard SPARQL JSON results. The query is Day 22's:
  roles and `equipRef`, starting from points that have a timeseries reference (pattern order, as before).
- `GET /api/points/{id}/timeseries`: the API looks up the point's reference, resolves it (the Day 24 job, done
  server-side) and returns its samples, `ts, value`, plus the `timeseries_id` it served.

Day 14's rule is unchanged. FC1 is the same four steps (gate and raw fault, streak id, row in streak, confirm) with
the same tolerance (25 Pa) and confirmation (2 rows), now on both AHUs. The only new work is **getting the data in
the shape the rule wants**, long → wide (Day 23) and inches of water → pascals (Day 6):

| Step | `day25_pandas.py` | `day25_sql.py` |
|---|---|---|
| 1. find the inputs | `api.post("/api/sparql", json={"query": fc1_query})` | the same query, with rdflib on the model file |
| 2. get the series | `api.get("/api/points/" + point_id + "/timeseries")` ×6, one `GET` each | none: SQLite reads `samples` directly (read-only) |
| use the ids | the API is told the point; it returns the UUID it served (the script prints it equals the model's) | UUIDs go into a `TEMP` table `fc1_input`, joined to `samples` |
| 3. long → wide | `long.pivot(index=["equipment_id", "ts"], columns="role", values="value")` | `MAX(CASE WHEN i.role = 'fan-status' THEN s.value END) ...` |
| 4-5. SI + FC1 | pandas arithmetic, `shift()` / `cumsum()` / `cumcount()` | `LAG`, `SUM() OVER`, `ROW_NUMBER() OVER`, all `PARTITION BY equipment_id` |

Both routes have the same cost shape: O(n) rows moved and one sort for the windows. Through HTTP each series is also
serialized to JSON and back, so the API route is slower per row than reading SQLite directly. You pay for the
indirection to get a stable interface: the client never sees the database, the table or the UUIDs it didn't ask for.
The SQL script shows the other side: when you do own the database, the model's answer ("these UUIDs") goes into a
table the query joins, and no id is written in the SQL.

Where do the role names ("fan-status", ...) still appear? In the SPARQL filter and the pivot (the SQL's `CASE WHEN i.role = ...` lines, pandas' column names).
They are the rule's **input contract**: that is all the rule knows about the building. Everything else, which point,
which column, which store, which id, comes from the model.

## Run
Needs `var/timeseries.sqlite` and the model (`uv run bldgts model build && uv run bldgts bootstrap`).

```bash
uv run python lessons/course.py run 25
```

That runs [`day25_pandas.py`](day25_pandas.py), then [`day25_sql.py`](day25_sql.py). The pandas script first prints
one line per `GET` (`GET AHU_1_DA_P -> 35536 rows, same id as the model: True`, ...). It may also print a
`DeprecationWarning` from Starlette, the web library under FastAPI; it is harmless. Both scripts end with:

```
FC1's inputs, found by the model:
equipment_id                    role        point_id                        timeseries_id
       AHU_1    duct-static-pressure      AHU_1_DA_P 52422584-9894-50bd-9696-2fbb8b062518
       AHU_1 duct-static-pressure-sp   AHU_1_DA_P_SP 761c2b61-4982-5157-bc66-2010cf6e2a47
       AHU_1              fan-status AHU_1_SF_Status 9ebf80dd-7821-510b-b2c0-cd0151e093c9
       AHU_2    duct-static-pressure      AHU_2_DA_P f8a0d594-2fff-567a-9853-71ba66233eba
       AHU_2 duct-static-pressure-sp   AHU_2_DA_P_SP 0c281cac-4d5e-5892-9456-bb9d1038fae8
       AHU_2              fan-status AHU_2_SF_Status 4bac9a08-337e-5f6b-a577-fa044776ab05

Rows after the pivot: 71072

FC1 per AHU (hours, episodes). Day 14 got the same from hard-coded columns:
equipment_id  raw_fault_h  confirmed_fault_h  episodes
       AHU_1       120.00             114.25        53
       AHU_2         3.42               1.50         5
```

These are Day 14's numbers (AHU_1 114.25 h in 53 episodes; AHU_2 1.50 h when Day 14 is pointed at AHU_2), from
scripts that name no column. The per-row fault flags are compared too, so the two scripts agree on every one of the
71,072 rows.

## Try it

1. Add the **duct static too high** rule (Day 14, Try it 2) to the pandas script. Which part of the pipeline changes,
   and does it need any new input from the model?
2. Run the script for AHU_2's `discharge-air-temp` and `discharge-air-temp-sp` instead of the static pressure
   roles. What do you change? (Mind the units: they are °F in the database.)

<details><summary>Answers</summary>

1. Only the comparison (`>` and `+ TOLERANCE_PA`). It uses the same three roles, so no new input.
2. The role strings in the SPARQL `FILTER` and the role column names used after the pivot; and the conversion: temperatures use
   `(F - 32) * 5 / 9`, not `* 249.08891`. The tolerance would be a temperature *difference*, which has no 32 in it
   (Day 6).

</details>

## Week 5 challenge: the same rule, a different store

Day 24 gave every FC1 input point a second reference, to the AHU's CSV. Run FC1 **again, with the series read from the
CSV storage**, using the model to find the points and Day 24's resolver to read them. You should get AHU_1 114.25 h
in 53 episodes and AHU_2 1.50 h again. Try it before opening the answer.

<details><summary>Answer</summary>

Start from a copy of `day24_pandas.py`: it already adds the CSV references to the graph, and its step 4 (the
resolver) has read every FC1 input from both stores into the `series` dict, keyed by `(point_id, store_class)`.
Append this. It changes exactly one thing, which store's series the rule uses (`STORE`); the rest is Day 25's:

```python
PA_PER_INH2O = 249.08891
TOLERANCE_PA = 25
CONFIRM_ROWS = 2
STORE = "CsvFile"  # <- the only change from Day 25: which store's series to use

# Each FC1 input point, with its AHU and role (DISTINCT: one row per point)
roles_query = (
    PREFIXES
    + """
SELECT DISTINCT ?point ?equip ?role WHERE {
  ?point bts:hasHaystackTag ?role_tag .
  ?role_tag bts:tagName "ofddRole" ; bts:tagValue ?role .
  FILTER(?role IN ("fan-status", "duct-static-pressure", "duct-static-pressure-sp"))
  ?point bts:hasHaystackTag ?equip_tag .
  ?equip_tag bts:tagName "equipRef" ; bts:tagValue ?equip .
}
"""
)
pieces = []
for row in g.query(roles_query):
    point_id = str(row.point).split("#")[-1]
    one_series = series[(point_id, STORE)].copy()  # step 4's resolver already read it
    one_series["equipment_id"] = str(row.equip).split("#")[-1]
    one_series["role"] = str(row.role)
    pieces.append(one_series)

long = pd.concat(pieces)
wide = long.pivot(index=["equipment_id", "ts"], columns="role", values="value").reset_index()
# ... then Day 25's steps 4-5, unchanged: pascals, raw fault, streaks, hours and episodes.
```

The CSV series are in the same units and on the same timestamps as the database's, so the rule gives the same
answer: AHU_1 114.25 h, 53 episodes; AHU_2 1.50 h. Without the `DISTINCT`, a query that also matched the references
would return each point once per reference, and the pivot would raise "Index contains duplicate entries". For the SQL route, load the CSV into a
`TEMP` table as `day24_sql.py` does and join it instead of `samples`.

The lesson: the rule, the SPARQL and the pivot did not change. Only the store the resolver was told to prefer did.
That is what the model buys you.

</details>

Next: **Unit 4** goes deeper into graphs and SPARQL itself, then the BACnet scans that feed models like this one.
