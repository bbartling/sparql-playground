# Day 25 — Model-driven FC1 through the app's API (week 5 challenge)

**Goal:** run Day 14's FC1 rule with no column names and no ids written in the code: SPARQL finds the inputs, the
app's API (or SQL on its database) supplies the series. Then run the same rule against the CSV storage from Day 24.

## Read

Day 14 hard-coded `supply_fan_status`, `da_p_inwc` and `da_p_setpoint_inwc`. This week replaced each hard-coded fact
with a lookup: roles (Day 21), tags in RDF (Day 22), stable ids (Day 23), references to stores (Day 24). Today they
all work together.

**`lab.Api`** runs this repo's FastAPI app (`bldgts serve`) inside the Python process with FastAPI's `TestClient`:
requests go straight into the app, no server and no network. It reads the model `model/building_50.ttl` and the
database `var/timeseries.sqlite`. It offers two things we use:

- `api.sparql(query)` runs SPARQL against the model and returns a DataFrame. The query is Day 22's: roles and
  `equipRef`, starting from points that have a timeseries reference (pattern order, as before).
- `api.timeseries(point_id)` is `GET /api/points/{id}/timeseries`: the API looks up the point's reference, resolves it
  (the Day 24 job, done server-side) and returns `ts, value`.

Day 14's rule is unchanged. FC1 is the same four steps (gate and raw fault, streak id, row in streak, confirm) with
the same tolerance (25 Pa) and confirmation (2 rows). The only new work is **getting the data in the shape the rule
wants**, long → wide (Day 23) and inches of water → pascals (Day 6):

| Step | `day25_pandas.py` | `day25_sql.py` |
|---|---|---|
| find the inputs | `api.sparql(FC1_POINTS_SPARQL)` | the same query, via `lab.Api` |
| get the series | `api.timeseries(point_id)` ×6, one `GET` each | none: SQLite reads `samples` directly |
| use the ids | the API is told the point; it returns the UUID it served (the script prints it equals the model's) | UUIDs go into a `TEMP` table `fc1_input`, joined to `samples` |
| long → wide | `long.pivot(index=["equipment_id","ts"], columns="role")` | `MAX(CASE WHEN i.role = :role_dp THEN s.value END)` |
| SI + FC1 | numpy/pandas arithmetic, `groupby().shift()/cumsum()/cumcount()` | `CASE`, `LAG`, `SUM() OVER`, `ROW_NUMBER() OVER` |

Both routes have the same cost shape: O(n) rows moved and one sort for the windows. Through HTTP each series is also
serialized to JSON and back, so the API route is slower per row than reading SQLite directly. You pay for the
indirection to get a stable interface: the client never sees the database, the table or the UUIDs it didn't ask for.
The SQL script shows the other side: when you do own the database, the model's answer ("these UUIDs") feeds a
*parameterized* query, and no id is written in the SQL.

Where do the role names ("fan-status", ...) still appear? In the SPARQL filter and the SQL's `:role_*` parameters.
They are the rule's **input contract**: that is all the rule knows about the building. Everything else, which point,
which column, which store, which id, comes from the model.

## Run

Needs `var/timeseries.sqlite` and the model (`uv run bldgts model build && uv run bldgts bootstrap`).

```bash
uv run python lessons/course.py run 25
```

That runs [`day25_pandas.py`](day25_pandas.py), then [`day25_sql.py`](day25_sql.py). Both end with:

```
FC1 per AHU (hours, episodes). Day 14 printed the same numbers from hard-coded columns:
equipment_id  raw_fault_h  confirmed_fault_h  episodes
       AHU_1       120.00             114.25        53
       AHU_2         3.42               1.50         5
```

These are Day 14's numbers (AHU_1 114.25 h in 53 episodes, AHU_2 1.50 h), from a script that names no column. The
per-row fault flags are compared too, so the two scripts agree on every one of the 71,072 rows.

## Try it

1. Add the **duct static too high** rule (Day 14, Try it 2) to the pandas script. Which part of the pipeline changes,
   and does it need any new input from the model?
2. Run the script for AHU_2's `discharge-air-temp` and `discharge-air-temp-sp` instead of the static pressure
   roles. What do you change? (Mind the units: they are °F in the database.)

<details><summary>Answers</summary>

1. Only the comparison (`>` and `+ TOL_PA`). It uses the same three roles, so no new input.
2. The two role strings in the SPARQL `FILTER` and the roles in `wide`/`h`; and the conversion: temperatures use
   `(F - 32) * 5 / 9`, not `* 249.08891`. The tolerance would be a temperature *difference*, which has no 32 in it
   (Day 6).

</details>

## Week 5 challenge: the same rule, a different store

Day 24 gave every FC1 input point a second reference, to the AHU's CSV. Run FC1 **again, with the series read from the
CSV storage**, using the model to find the points and Day 24's resolver to read them. You should get AHU_1 114.25 h
in 53 episodes and AHU_2 1.50 h again. Try it before opening the answer.

<details><summary>Answer</summary>

Start from a copy of `day24_pandas.py`: it already builds the graph with the CSV references and defines `read_series`
and the `refs` table (one row per point per store). Append this. It changes exactly one thing, which store the
resolver reads (`WANT`); the rule itself is Day 14's:

```python
PA_PER_INH2O, TOL_PA, CONFIRM_ROWS = 249.08891, 25.0, 2
WANT = "CsvFile"  # <- the only change from the SQLite run: which store's reference to follow

ROLE_QUERY = (
    PREFIXES
    + """
SELECT DISTINCT ?equip ?role ?point WHERE {          # DISTINCT: each point now has two references
  ?point ref:hasExternalReference ?r .
  ?point bts:hasHaystackTag ?role_tag .
  ?role_tag bts:tagName "ofddRole" ; bts:tagValue ?role .
  FILTER(?role IN ("fan-status", "duct-static-pressure", "duct-static-pressure-sp"))
  ?point bts:hasHaystackTag ?equip_tag .
  ?equip_tag bts:tagName "equipRef" ; bts:tagValue ?equip .
}"""
)
frames = []
for r in g.query(ROLE_QUERY):
    ref = refs[(refs.point_iri == str(r.point)) & (refs.store_class == WANT)].iloc[0]
    series = read_series(ref.store_iri, ref.store_class, ref.timeseries_id)  # the resolver
    frames.append(series.assign(equipment_id=local(r.equip), role=str(r.role)))
long = pd.concat(frames, ignore_index=True)
wide = long.pivot(index=["equipment_id", "ts"], columns="role", values="value").reset_index()
h = pd.DataFrame(
    {
        "equipment_id": wide.equipment_id,
        "ts": wide.ts,
        "fan_status": wide["fan-status"],
        "duct_static_pa": wide["duct-static-pressure"] * PA_PER_INH2O,
        "duct_static_sp_pa": wide["duct-static-pressure-sp"] * PA_PER_INH2O,
    }
).sort_values(["equipment_id", "ts"], ignore_index=True)
# ... then Day 25's steps 4-5 unchanged: raw fault, streaks, confirm, hours and episodes.
```

The CSV series are in the same units and on the same timestamps as the database's, so the rule gives the same
answer: AHU_1 114.25 h, 53 episodes; AHU_2 1.50 h. Without the `DISTINCT` the pivot would raise "Index contains
duplicate entries", because each point would appear once per reference. For the SQL route, load the CSV into a
`TEMP` table as `day24_sql.py` does and join it instead of `samples`.

The lesson: the rule, the SPARQL and the pivot did not change. Only the store the resolver was told to prefer did.
That is what the model buys you.

</details>

Next: **Unit 4** goes deeper into graphs and SPARQL itself, then the BACnet scans that feed models like this one.
