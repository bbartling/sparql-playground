---
name: Brick timeseries SPARQL tutorial (brickts) — build plan
overview: "Build a near-production tutorial app in this repo. BUILDING_50 AHU_1 CSV → long/narrow SQLite (TSDB stand-in behind a TimeseriesStore Protocol). An AI-authored Brick 1.5 model with ref-schema external refs (ref:storedAt → ref:Database/brick:Database). FastAPI with read-only SPARQL, class/tag point lookup, timeseries JSON resolved through the graph, and Open-FDD fault applicability. A static SPARQL UI. An analyst client that runs open-fdd FC1. pytest, ruff, CI, Dockerfile, README tutorial. Locked decisions: agent_spec/ARCHITECTURE.md."
todos:
  - id: s0-data
    content: "S0 Data — unzip /home/ben/Downloads/BUILDING_50_openfdd.zip to /tmp/b50. Copy BUILDING_50/manifest.json and AHU_1/{history_wide.csv,columns.csv,column_map.json,fdd_faults.csv,fdd_events.csv} to data/BUILDING_50/. Write data/datasets.json. Add var/ and *.sqlite* to .gitignore"
    status: pending
  - id: s1-scaffold
    content: "S1 Scaffold — pyproject (deps already added via uv add), [project.scripts] brickts=brickts.cli:main, ruff config, settings.py (pydantic-settings, BRICKTS_ prefix), logging.py (JSON)"
    status: pending
  - id: s2-store
    content: "S2 TimeseriesStore Protocol + SqliteTimeseriesStore (WAL, WITHOUT ROWID PK(timeseries_id,ts), parameterized, upsert) + registry by Database IRI/bts:backend"
    status: pending
  - id: s3-model
    content: "S3 Model — model/site.ttl (Site, Building, Floors, AHU_1, parts, 46 zones, Database node). model/points/BUILDING_50__AHU_1.csv (83 rows, table below). brickts model build → model/building_50.ttl. SHACL validate"
    status: pending
  - id: s4-ingest
    content: "S4 Bootstrap/ingest — wide CSV → long rows via the mapping CSV; idempotent via ingest_log sha256; --force; optional startup bootstrap"
    status: pending
  - id: s5-graph
    content: "S5 GraphService — model + cached Brick ontology union; copy-on-write mutations under a lock; atomic snapshot; periodic flusher; validation SPARQL checks"
    status: pending
  - id: s6-sparql-guard
    content: "S6 Read-only SPARQL guard — query forms allowlist; reject update/SERVICE/FROM; length cap, row cap, timeout, semaphore"
    status: pending
  - id: s7-api
    content: "S7 FastAPI — /health, /api/sparql (+examples), /api/equipment, points by class/tags, timeseries, faults, model validate/ttl, gated mutations, lifespan flush"
    status: pending
  - id: s8-faults
    content: "S8 Fault applicability from open_fdd.rules.RULES + ROLE_REQUIREMENTS role→Brick table"
    status: pending
  - id: s9-ui
    content: "S9 Static SPARQL UI at /ui — textarea, Ctrl+Enter, presets, table, errors, count/timing, CSV/JSON download, click point → SVG plot"
    status: pending
  - id: s10-client
    content: "S10 scripts/analyst_client.py — faults list, then class/tag lookup of DSP/DSP-SP/SF speed, timeseries, open_fdd run_rule FC1, print summary"
    status: pending
  - id: s11-tests
    content: "S11 pytest suite (list below) + ruff clean"
    status: pending
  - id: s12-docs-ops
    content: "S12 README tutorial (+screenshot docs/ui.png), refresh AGENTS.md, Dockerfile + compose.yaml, .github/workflows/ci.yml"
    status: pending
  - id: s13-ship
    content: "S13 Run bootstrap + serve + client end-to-end. Commit on feature/brick-timeseries-tutorial, push, PR to develop. Report: branch, PR URL, tree, tests, FC1 summary, open questions"
    status: pending
isProject: false
---

# Brick timeseries SPARQL tutorial — build plan

Locked decisions live in [`agent_spec/ARCHITECTURE.md`](../../agent_spec/ARCHITECTURE.md) (A1–A17). The agent guide and invariants live in [`AGENTS.md`](../../AGENTS.md). Reference repo `/home/ben/Desktop/open-fdd` is **read-only**.

## Current repo state (2026-10-09)

- Remote: `origin https://github.com/bbartling/sparql-playground.git`. Default branch is `develop`. Working branch is `feature/brick-timeseries-tutorial`.
- Committed: `LICENSE`, the stub `README.md`, `.gitignore` (Python template; already ignores `.venv`, `db.sqlite3`), this plan, `AGENTS.md`, and `agent_spec/ARCHITECTURE.md`.
- **Untracked scaffold (keep it and build on it):**
  - `pyproject.toml`, from `uv init --lib`. Deps were added with ranges: fastapi, uvicorn[standard], pydantic, pydantic-settings, rdflib>=7.1, brickschema>=0.8 (bundles **Brick 1.5**), pandas, open-fdd[oracle]>=4.4.9, and httpx. Dev deps: pytest and ruff.
  - `uv.lock`, `.python-version` (3.12), `src/brickts/__init__.py` (uv placeholder; replace it), `src/brickts/py.typed`, and `.venv`.
- Verified facts:
  - `open_fdd.rules.run_rule("FC1", df, poll_seconds=300)` works when `df.attrs["equipment_type"]="ahu"`.
  - Brick 1.5 has `ref:TimeseriesReference`, `ref:hasExternalReference`, `ref:hasTimeseriesId`, and `ref:storedAt`. It has **no** `ref:Database` or `brick:Database` class, so the node is typed with both (A6).
  - Classes carry `brick:hasAssociatedTag` (tag ns `https://brickschema.org/schema/BrickTag#`).
  - Supply and Discharge classes are linked with `owl:equivalentClass`, so class paths must follow `(rdfs:subClassOf|owl:equivalentClass)*`.
  - Open-FDD's React UI has no SPARQL page today, so the UI presets below are original.

## File layout

```
.github/workflows/ci.yml          # uv sync --frozen; ruff check; ruff format --check; pytest
Dockerfile  compose.yaml          # python:3.12-slim + uv; volume for /app/var; healthcheck /health
data/datasets.json                # [{building, equipment, csv, mapping}]
data/BUILDING_50/manifest.json
data/BUILDING_50/AHU_1/{history_wide.csv,columns.csv,column_map.json,fdd_faults.csv,fdd_events.csv}
model/site.ttl                    # authored: Site/Building/Floors/AHU_1/parts/zones/Database
model/points/BUILDING_50__AHU_1.csv
model/building_50.ttl             # rendered by `brickts model build`, committed
src/brickts/
  settings.py logging.py cli.py ingest.py
  store/{base.py,sqlite.py,registry.py}
  graph/{service.py,ontology.py,sparql_guard.py,validate.py,render.py,namespaces.py}
  sparql/examples/*.rq            # UI presets + validation queries (single source)
  services/{points.py,timeseries.py,faults.py}
  api/{app.py,schemas.py,deps.py,routers/{health.py,sparql.py,equipment.py,points.py,faults.py,model.py}}
  static/{index.html,app.js,style.css}
scripts/analyst_client.py
tests/{conftest.py,test_store_sqlite.py,test_bootstrap.py,test_model.py,test_sparql_guard.py,
       test_api.py,test_graph_service.py,test_faults.py,test_client_fc1.py,test_ui.py}
docs/ui.png  README.md  AGENTS.md
```

Settings (env `BRICKTS_*`): `data_dir=data`, `db_path=var/timeseries.sqlite`, `model_path=model/building_50.ttl`, `snapshot_path=var/graph.snapshot.ttl`, `serialize_interval_s=60` (0 = off), `serialize_on_mutation=true`, `bootstrap_on_startup=true`, `sparql_max_rows=10000`, `sparql_timeout_s=10`, `sparql_max_query_chars=20000`, `sparql_max_concurrency=4`, `timeseries_max_rows=200000`, `allow_mutations=false`, `log_level=INFO`, `log_json=true`.

## CSV → Brick mapping (AHU_1, 83 value columns, 35,536 rows at 5-min intervals, 2026-03-16 → 2026-07-17 UTC)

The timeseries id for each column is `uuid5(NAMESPACE_URL, "urn:openfdd:BUILDING_50:AHU_1:<source_column>")`, frozen in the mapping CSV. The IRI namespace is `bldg: <https://example.org/openfdd/BUILDING_50#>`. Units are QUDT (`DEG_F`, `IN_H2O`, `PERCENT`); "–" means no unit (binary or enumerated). Parts in `site.ttl`:

- `AHU_1_Supply_Fan` (`Supply_Fan`)
- `AHU_1_Return_Fan` (`Return_Fan`)
- `AHU_1_OA_Damper` (`Outside_Damper`)
- `AHU_1_EA_Damper` (`Exhaust_Damper`)
- `AHU_1_CHW_Valve` (`Chilled_Water_Valve`)

Each part is `brick:isPartOf bldg:AHU_1`, with the inverse `hasPart`.

| source_column | point_id | Brick class | unit | owner | Open-FDD role |
|---|---|---|---|---|---|
| 50ahu1aalrm | AHU_1_Alarm | Alarm | – | AHU_1 | |
| bld_p_setpoint_inwc | AHU_1_BLD_P_SP | Building_Air_Static_Pressure_Setpoint | IN_H2O | AHU_1 | |
| bld_pressure_inwc | AHU_1_BLD_P | Building_Air_Static_Pressure_Sensor | IN_H2O | AHU_1 | |
| chw_valve_pct | AHU_1_CHW_Valve_Cmd | Valve_Position_Command | PERCENT | AHU_1_CHW_Valve | cooling-valve |
| da_p_inwc | AHU_1_DA_P | Supply_Air_Static_Pressure_Sensor | IN_H2O | AHU_1 | duct-static-pressure |
| da_p_setpoint_inwc | AHU_1_DA_P_SP | Supply_Air_Static_Pressure_Setpoint | IN_H2O | AHU_1 | duct-static-pressure-sp |
| dat_reset_f | AHU_1_DAT_SP | Supply_Air_Temperature_Setpoint | DEG_F | AHU_1 | discharge-air-temp-sp |
| dat_x1_f | AHU_1_DAT_Reset_OAT_Low | Outside_Air_Temperature_Low_Reset_Setpoint | DEG_F | AHU_1 | |
| dat_x2_f | AHU_1_DAT_Reset_OAT_High | Outside_Air_Temperature_High_Reset_Setpoint | DEG_F | AHU_1 | |
| dat_y1_f | AHU_1_DAT_Reset_SAT_High | Supply_Air_Temperature_High_Reset_Setpoint | DEG_F | AHU_1 | |
| dat_y2_f | AHU_1_DAT_Reset_SAT_Low | Supply_Air_Temperature_Low_Reset_Setpoint | DEG_F | AHU_1 | |
| discharge_air_temp_f | AHU_1_DA_T | Supply_Air_Temperature_Sensor | DEG_F | AHU_1 | discharge-air-temp |
| dischargeair_alarm | AHU_1_DA_Alarm | Supply_Air_Temperature_Alarm | – | AHU_1 | |
| ex_dmpr_pos_fan_enable_pct | AHU_1_EA_Damper_Fan_Enable_Pos | Damper_Position_Setpoint | PERCENT | AHU_1_EA_Damper | |
| hu_50_duration_n_emergency_inactive_pointemergencyoverride_self | AHU_1_Emergency_Override | Status | – | AHU_1 | |
| lowdapalarm | AHU_1_Low_DA_P_Alarm | Pressure_Alarm | – | AHU_1 | |
| mad_c | AHU_1_OA_Damper_Cmd | Damper_Position_Command | PERCENT | AHU_1_OA_Damper | outside-air-damper |
| mixed_air_temp_f | AHU_1_MA_T | Mixed_Air_Temperature_Sensor | DEG_F | AHU_1 | mixed-air-temp |
| oa_minimum_position_pct | AHU_1_OA_Damper_Min_Pos | Min_Position_Setpoint_Limit | PERCENT | AHU_1_OA_Damper | |
| occ_c | AHU_1_Occ_Cmd | Occupancy_Command | – | AHU_1 | occupied |
| outside_air_temp_f | AHU_1_OA_T | Outside_Air_Temperature_Sensor | DEG_F | AHU_1 | outside-air-temp |
| return_air_temp_f | AHU_1_RA_T | Return_Air_Temperature_Sensor | DEG_F | AHU_1 | return-air-temp |
| return_fan_speed_pct | AHU_1_RF_Speed_Cmd | Fan_Speed_Command | PERCENT | AHU_1_Return_Fan | return-fan-cmd |
| return_fan_status | AHU_1_RF_Status | Fan_Status | – | AHU_1_Return_Fan | |
| returnfan | AHU_1_RF_Run_Status | Start_Stop_Status | – | AHU_1_Return_Fan | |
| returnfanaalrm | AHU_1_RF_Alarm | Alarm | – | AHU_1_Return_Fan | |
| returnfanstatus | AHU_1_RF_OnOff_Status | Fan_On_Off_Status | – | AHU_1_Return_Fan | |
| rf_c | AHU_1_RF_Cmd | Start_Stop_Command | – | AHU_1_Return_Fan | |
| sf_c | AHU_1_SF_Cmd | Start_Stop_Command | – | AHU_1_Supply_Fan | |
| supply_fan_speed_pct | AHU_1_SF_Speed_Cmd | Fan_Speed_Command | PERCENT | AHU_1_Supply_Fan | fan-cmd |
| supply_fan_status | AHU_1_SF_Status | Fan_Status | – | AHU_1_Supply_Fan | fan-status |
| supplyfan | AHU_1_SF_Run_Status | Start_Stop_Status | – | AHU_1_Supply_Fan | |
| supplyfanalarm | AHU_1_SF_Alarm | Alarm | – | AHU_1_Supply_Fan | |
| supplyfanstatus | AHU_1_SF_OnOff_Status | Fan_On_Off_Status | – | AHU_1_Supply_Fan | |
| tstat | AHU_1_Tstat_Status | Thermostat_Status | – | AHU_1 | |
| unoccupied_cool_setpt_f | AHU_1_Unocc_Clg_SP | Unoccupied_Air_Temperature_Cooling_Setpoint | DEG_F | AHU_1 | |
| zone_t50_<floor>_<vav>_space_temp_f (46 columns) | Zone_<VAV>_ZN_T | Zone_Air_Temperature_Sensor | DEG_F | Zone_<VAV> (HVAC_Zone) | |
| zone_t50_first_floor_vav_107_space_temp_f_2 | Zone_VAV_107_ZN_T_2 | Zone_Air_Temperature_Sensor | DEG_F | Zone_VAV_107 | |
| zone_t50_nan_pt6969_space_temp_f | Zone_AHU_1_ZN_T | Zone_Air_Temperature_Sensor | DEG_F | Zone_AHU_1 | |

Zone rules:

- `<VAV>` is the upper-cased slug (for example `VAV_100`, `VAVH_2D316`, `VAVHM_110`).
- There are 46 `brick:HVAC_Zone` nodes. Each is `brick:isPartOf` a Floor (`Floor_1`, `Floor_2`, or `Floor_3`, from first/second/third) and fed by AHU_1 (`bldg:AHU_1 brick:feeds ?zone`, plus the inverse `isFedBy`).
- Zone points are **not** in the AHU part tree. `points?include_fed_zones=true` includes them.
- Labels come from `columns.csv` `point_name`, with the `bld_50_AHU_1 ` prefix stripped.

## Key sketches

**Ref-schema pattern (rendered for every point):**

```turtle
bldg:timeseries_db a ref:Database, brick:Database ;
  rdfs:label "SQLite timeseries store (tutorial stand-in for a TSDB)" ;
  bts:backend "sqlite" ; bts:connectionEnv "BRICKTS_DB_PATH" ;
  bts:schemaDescription "samples(timeseries_id TEXT, ts INTEGER epoch-s UTC, value REAL)" .
bldg:AHU_1_DA_P a brick:Supply_Air_Static_Pressure_Sensor ;
  rdfs:label "AHU1 DA-P" ; brick:hasUnit unit:IN_H2O ; brick:isPointOf bldg:AHU_1 ;
  ref:hasExternalReference [ a ref:TimeseriesReference ;
      ref:hasTimeseriesId "<uuid5>" ; ref:storedAt bldg:timeseries_db ] .
bldg:AHU_1 brick:hasPoint bldg:AHU_1_DA_P .
```

**Read-only SPARQL guard (`graph/sparql_guard.py`):**

```python
ALLOWED = {"SelectQuery", "AskQuery", "ConstructQuery", "DescribeQuery"}
def prepare(text: str, s: Settings) -> Query:
    if len(text) > s.sparql_max_query_chars: raise SparqlRejected("query too long")
    try: parsed = parseQuery(text)
    except ParseException as e:
        try: parseUpdate(text); raise SparqlRejected("updates are not allowed")
        except ParseException: raise SparqlSyntaxError(str(e)) from e
    q = parsed[1]
    if q.name not in ALLOWED: raise SparqlRejected(f"{q.name} not allowed")
    if q.get("datasetClause"): raise SparqlRejected("FROM / FROM NAMED not allowed")
    if _contains(parsed, "ServiceGraphPattern"): raise SparqlRejected("SERVICE not allowed")
    query = translateQuery(parsed)
    if query.algebra.name == "SelectQuery":   # cap rows; fallback: truncate while iterating
        query.algebra.p = CompValue("Slice", p=query.algebra.p, start=0, length=s.sparql_max_rows + 1)
    return query
# router: async with sem: await asyncio.wait_for(run_in_threadpool(state.union.query, query), timeout)
# 400 syntax/forbidden, 504 timeout; response = SPARQL 1.1 JSON results + meta{row_count,truncated,elapsed_ms}
```

**Applicable faults (`services/faults.py`):**

```python
ROLE_REQUIREMENTS = {  # role -> (brick class, optional owner class)
  "duct-static-pressure": ("Supply_Air_Static_Pressure_Sensor", None),
  "duct-static-pressure-sp": ("Supply_Air_Static_Pressure_Setpoint", None),
  "fan-cmd": ("Fan_Speed_Command", "Supply_Fan"), "fan-status": ("Fan_Status", "Supply_Fan"),
  "return-fan-cmd": ("Fan_Speed_Command", "Return_Fan"),
  "discharge-air-temp": ("Supply_Air_Temperature_Sensor", None),
  "discharge-air-temp-sp": ("Supply_Air_Temperature_Setpoint", None),
  "mixed-air-temp": ("Mixed_Air_Temperature_Sensor", None),
  "return-air-temp": ("Return_Air_Temperature_Sensor", None),
  "outside-air-temp": ("Outside_Air_Temperature_Sensor", None),
  "outside-air-damper": ("Damper_Position_Command", "Outside_Damper"),
  "cooling-valve": ("Valve_Position_Command", "Chilled_Water_Valve"),
  "heating-valve": ("Valve_Position_Command", "Hot_Water_Valve"),
  "occupied": ("Occupancy_Command", None),
  "web-outside-air-temp": ("Outside_Air_Temperature_Sensor", "Weather_Station"),
}  # unmapped role -> rule not applicable, reason "no Brick mapping for role"
ROLE_ASK = """ASK {
  ?point (brick:isPointOf|^brick:hasPoint) ?owner .
  ?owner (brick:isPartOf|^brick:hasPart)* ?equip .
  ?point a/(rdfs:subClassOf|owl:equivalentClass|^owl:equivalentClass)* ?cls .
  ?owner a/(rdfs:subClassOf|owl:equivalentClass|^owl:equivalentClass)* ?ownerCls }"""
# no owner constraint: bind ?ownerCls = brick:Entity or use a second prepared ASK without that line
# rules = [r for r in open_fdd.rules.RULES if kind in r.equipment_kinds]; kind from equip class (AHU -> "ahu")
# empty required_roles -> applicable, generic=True. Cache role results per request.
```

Expected for AHU_1:

- Applicable: FC1, FC2, FC3, FC4, FC8–FC13, AHU-SATDEV, AHU-DUCTHI, ECON-1/2/3/4/6/7, RESET-1, CMD-1, OA-1, DMP-1, VLV-1, SCHED-1, plus the generic rules.
- **Not** applicable: FC5 and FC7 (heating-valve), FC6, FC14, FC15, AHU-SIMUL, OAT-METEO, ECON-5, TRIM-1, and FCU-*.

**FC1 client (`scripts/analyst_client.py`):**

```python
def find_one(c, equip, **q):  # GET /api/equipment/{equip}/points?brick_class=..&parent_class=..|tags=..
    pts = c.get(f"/api/equipment/{equip}/points", params=q).raise_for_status().json()["points"]
    if len(pts) != 1: raise SystemExit(f"expected 1 point for {q}, got {len(pts)}")
    return pts[0]
roles = {"duct-static-pressure": find_one(c, eq, brick_class="Supply_Air_Static_Pressure_Sensor"),
         "duct-static-pressure-sp": find_one(c, eq, tags="Supply,Air,Static,Pressure,Setpoint"),
         "fan-cmd": find_one(c, eq, brick_class="Fan_Speed_Command", parent_class="Supply_Fan")}
series = {r: pd.Series(...from GET /api/points/{p['point_id']}/timeseries...) for r, p in roles.items()}
df = pd.DataFrame(series).sort_index(); df.attrs.update(equipment_id=eq, equipment_type="ahu")
res = open_fdd.rules.run_rule("FC1", df, poll_seconds=300)  # source: open_fdd/rules/cookbook_catalog.py::fc1
print(res.status, res.fault_hours, res.fault_pct, res.sample_count, res.fault_sample_count)
print(res.to_dict()["evidence"]["confirmed_fault"]["fault_intervals"][:5])
```

Keep the logic in functions that take an `httpx.Client`, so the test can pass a FastAPI `TestClient`. On the full data, expect the raw FC1 mask (`DSP < SP − 0.12` and fan ≥ 87%) to be true for about 1,873 samples, and status `FAULT`.

## API

| Method and path | Purpose |
|---|---|
| `GET /health` | Health check. |
| `POST /api/sparql {query}` and `GET /api/sparql?query=` | Read-only SPARQL. |
| `GET /api/sparql/examples` | Preset queries. |
| `GET /api/equipment` | List equipment. |
| `GET /api/equipment/{id}/points?brick_class=&tags=&parent_class=&include_subclasses=true&include_fed_zones=false` | Point lookup by class or tag. |
| `GET /api/points/{point_id}` | Point details. |
| `GET /api/points/{point_id}/timeseries?start=&end=&limit=` | Timeseries through the graph ref (404 when the timeseries id is not in the store; 409 when the ref is missing or there is more than one timeseries id). |
| `POST /api/timeseries/query` | Batch timeseries fetch. |
| `GET /api/equipment/{id}/faults?include_generic=true` | Applicable Open-FDD faults. |
| `GET /api/model/validate?shacl=false` | Validation checks. |
| `GET /api/model/ttl` | Download the model. |
| `POST /api/model/points`, `POST /api/model/flush` | Mutations (403 unless `allow_mutations`). |
| `GET /` → `/ui` | Browser UI. |

Validation rules:

- Ids are local names matching `^[A-Za-z0-9_\-]{1,128}$`. Unknown ids return 404.
- Classes match `^[A-Z][A-Za-z0-9_]{0,127}$` and must be a `brick:Point` subclass, otherwise 422.
- Tags are at most 20 items of `[A-Za-z0-9_]+`.

UI presets (`sparql/examples/*.rq`): list points; AHU points with refs and DB; points by class; points by tags; missing refs (expect 0 rows); refs with ≠1 timeseries id; refs without a Database; equipment tree; zones fed by the AHU; databases; class counts. The validation module reuses the three validation queries.

## Tests

- `test_store_sqlite.py`: WAL mode; PK on `(timeseries_id, ts)`; write/read round trip; start/end/limit; upsert idempotency; injection-looking id stored literally.
- `test_bootstrap.py`: row count equals non-null cells; second run skipped; `--force` gives the same counts; every CSV column is mapped (83) and every mapping column exists in the CSV.
- `test_model.py`: one Site, one AHU, 83 points; each point has exactly one ref with exactly one timeseries id, `storedAt` a Database node, and an id that exists in SQLite. Timeseries ids are unique. Classes are `brick:Point` subclasses. Units are QUDT. Mapping matches TTL. No CSV column name appears as a literal. SHACL conforms.
- `test_sparql_guard.py`: SELECT, ASK, CONSTRUCT, and DESCRIBE allowed. INSERT DATA, DELETE WHERE, LOAD, CLEAR, DROP, SERVICE (including nested), FROM, over-long queries, and garbage are rejected. Row cap sets `truncated`.
- `test_api.py`: health; SPARQL ok, 400 bad syntax, 400 update/SERVICE; every example runs; the 3 FC1 points by class and by tags; unknown equipment 404; bad or unknown class 422; timeseries ascending and filtered; missing ref 409 (inject triples); missing timeseries id 404; mutation 403 by default; with mutations enabled, a point is added, then queryable, then a snapshot is written with no `.tmp` left.
- `test_graph_service.py`: atomic write survives a serializer exception; the periodic flusher writes only when dirty; the lifespan shutdown flushes.
- `test_faults.py`: FC1, AHU-DUCTHI, and FC13 applicable; FC5 not applicable (heating-valve missing); FC14 not applicable.
- `test_client_fc1.py`: the client flow against TestClient matches an independent pandas FC1 raw mask on the test window; a synthetic FC1 semantics check.
- `test_ui.py`: `/ui` returns 200 HTML containing "SPARQL"; `/static/app.js` returns 200.
- Tests use a first-2000-row copy of the real CSV (all columns), tmp db and snapshot paths, and a session-cached ontology.

## Ordered steps (verify each before moving on)

- [ ] S0 data: `ls -la data/BUILDING_50/AHU_1 && git check-ignore var/x.sqlite`
- [ ] S1 scaffold: `uv sync && uv run brickts --help && uv run ruff check .`
- [ ] S2 store: `uv run pytest -q tests/test_store_sqlite.py`
- [ ] S3 model: `uv run brickts model build && uv run brickts validate --shacl && uv run pytest -q tests/test_model.py`
- [ ] S4 bootstrap: `uv run brickts bootstrap && uv run brickts bootstrap` (second run says skipped) `&& uv run pytest -q tests/test_bootstrap.py`
- [ ] S5–S8: `uv run pytest -q tests/test_graph_service.py tests/test_sparql_guard.py tests/test_api.py tests/test_faults.py`
- [ ] S9 UI: `uv run brickts serve` then open `http://127.0.0.1:8000/ui`, run each preset, click a point, and save the screenshot to `docs/ui.png`
- [ ] S10 client: with the server running, `uv run python scripts/analyst_client.py --base-url http://127.0.0.1:8000 --equipment AHU_1`
- [ ] S11: `uv run ruff check . && uv run ruff format --check . && uv run pytest -q` all green
- [ ] S12 docs/ops: README covers the pattern (cite the Brick URL), the AI modeling workflow, the TSDB stand-in framing, run steps, the UI, and production notes (auth, Timescale/Influx store, real triplestore with server timeouts, migrations, metrics). Optional: `docker build .`. Don't build locally if RAM is tight.
- [ ] S13 ship: `git add` (data, model, src, tests, docs, scripts, configs; no `var/`) then commit, push, and run `gh pr create --base develop`

## Acceptance criteria

- All invariants in AGENTS.md hold and are enforced by tests. pytest and ruff are green locally and in CI.
- Bootstrap is idempotent. SQLite is long/narrow with a `(timeseries_id, ts)` PK and WAL mode.
- Every one of the 83 points resolves to data only through `ref:hasExternalReference`. A `grep` for CSV column names in `src/brickts/{api,services,graph}` and the client finds nothing.
- The SPARQL endpoint rejects updates, SERVICE, and FROM, and enforces the row cap, timeout, and length limit. The UI uses the same endpoint.
- The faults endpoint matches the expected AHU_1 applicability. The client prints the fault list and the FC1 summary from `open_fdd.run_rule`.
- The TTL snapshot is written atomically on interval, after mutations, and on shutdown.

## Open questions (report them in the final summary)

- The zip has 2 AHUs plus plant and ~50 VAVs; scope is AHU_1 only (A17).
- `ref:Database` vs `brick:Database`: neither is defined in Brick 1.5, so the node is typed with both (A6).
- Ambiguous mappings:
  - `dat_reset_f` is taken as the active SAT setpoint (Open-FDD's choice).
  - `mad_c` is treated as the OA damper command.
  - The duplicate fan status columns are split across `Fan_Status`, `Fan_On_Off_Status`, and `Start_Stop_Status`.
  - The `hu_50_…` column is constant 1, with a garbled name, so it is typed as generic `Status`.
  - `ex_dmpr_pos_fan_enable_pct` meaning is unclear.
  - `tstat` is typed `Thermostat_Status`.
- Zone labels in `columns.csv` say `bld_100_BOILERS_PUMPS SpaceTemp`, which is a source mislabel. `VAVH_2D316` has values >150 °F (sentinel 888). Raw values are kept.
