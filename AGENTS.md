# AGENTS.md — sparql-playground (brickts)

This repo is a **tutorial + near-production pattern**: Brick RDF describes the building;
timeseries are reached **only through the model** ([Brick timeseries storage](https://docs.brickschema.org/metadata/timeseries-storage.html)).
Here: FastAPI + read-only SPARQL + SQLite stand-in TSDB + Swagger at `/docs`. Lessons: `scripts/lesson_0*.py`.

- **Locked decisions:** [`agent_spec/ARCHITECTURE.md`](agent_spec/ARCHITECTURE.md)
- **Build plan (if rebuilding from scratch):** [`.cursor/plans/sparql_playground_build.plan.md`](.cursor/plans/sparql_playground_build.plan.md)

```
CSV ──bootstrap──▶ TimeseriesStore (samples: timeseries_id, ts, value)
site.ttl + points CSV ──model build──▶ building_50.ttl ──▶ Graph (+ Brick ontology)
HTTP ──▶ SPARQL / points / timeseries
         point → ref:TimeseriesReference → timeseries_id + storedAt → Database → store.read()
```

## Commands

```bash
uv sync
uv run brickts model build
uv run brickts bootstrap
uv run brickts validate [--shacl]
uv run brickts serve                      # http://127.0.0.1:8000/docs
uv run python scripts/lesson_01_mech_summary.py
uv run pytest -q && uv run ruff check .
```

## Invariants (do not break)

1. Every `brick:Point` has exactly one `ref:hasExternalReference` → `ref:TimeseriesReference` with exactly one `ref:hasTimeseriesId` and a `ref:storedAt` Database.
2. Every timeseries id in the model exists in the store; every mapped column is in the model.
3. No hardcoded CSV column names in API/services/graph/client code.
4. No hardcoded equipment ids in product code — select by Brick class, tags, or roles.
5. SPARQL is read-only (no UPDATE/LOAD/SERVICE/FROM); row cap + timeout + length limit.
6. Parameterized SQL only; graph mutations via locked copy-on-write; atomic TTL writes.
7. No secrets in the graph, repo, or logs — Database nodes hold env-var *names*, not credentials.

## Guardrails

- Read-only reference: `/home/ben/Desktop/open-fdd` — never edit it.
- Don’t commit `var/`, `*.sqlite`, `.venv`, secrets. No Git LFS. Data files under 50 MB each.
- No auth, no CDN, no Node UI — Swagger only for interactive API.

---

## Prompt A — build an API like this (any language)

Copy this into another agent / project. Stack can be Go, Node, Java, .NET, etc. — not tied to FastAPI.

```text
Build a read-only “Brick + timeseries” API with these rules:

GOAL
- Clients discover building equipment and points with SPARQL (or an equivalent graph query).
- Clients never query the historian by raw column/tag names from the BMS export.
- The Brick (or Brick-compatible RDF) model is the only path from a logical point to samples.

DATA MODEL (Brick ref-schema)
- Site graph: Building, Equipment (AHU, Fan, …), Points, parts (isPartOf/hasPart), feeds/zones.
- Every Point has exactly one ref:hasExternalReference → ref:TimeseriesReference.
- That reference has exactly one opaque ref:hasTimeseriesId (UUID string, frozen at model time).
- That reference has ref:storedAt → a Database node (label + backend kind + env var NAME for connection — never credentials in the graph).

TIMESERIES STORE
- Abstract interface: read(timeseries_id, start?, end?, limit?) → [{ts, value}, …].
- Storage is long/narrow: (timeseries_id, timestamp_utc, value). Wide CSV/BMS tables are ingest-only.
- Swap SQLite / Timescale / Influx / lakehouse SQL behind the same interface; API unchanged.

HTTP SURFACE (minimum — this repo’s bare tutorial API)
- GET /hello — wake/ping (ready flag for cold starts)
- GET /health
- POST /api/sparql — read-only SELECT/ASK; reject UPDATE, LOAD, SERVICE, FROM; timeout + row cap
- POST /api/sparql/upload — run a .rq file (human-friendly in Swagger)
- GET /api/sparql/files — list/download lesson .rq files
- GET /api/points/{id}/timeseries?start=&end=&limit=
- Interactive OpenAPI/Swagger docs; no custom HTML app required

SECURITY / OPS
- Parameterized SQL only. No secrets in RDF or logs.
- Mutations off by default. Auth optional for LAN tutorials; required for production.

DELIVERABLES
1) Short architecture note matching the above.
2) Working read path: SPARQL → point → timeseries_id → store.read → JSON.
3) One inventory SPARQL example (count AHUs / zones) prefilled in OpenAPI.
4) Contract tests: every point has a ref; every timeseries_id resolves; bad SPARQL rejected.
```

---

## Prompt B — add Brick on top of an existing SQL / lake TSDB

Copy this when the customer already has a huge historian or data lake and only needs a Brick layer.

```text
We already have a production timeseries store (SQL warehouse, Timescale, Snowflake, Databricks,
Influx, PI/historian, etc.). Do NOT migrate the samples. Add a Brick metadata layer so apps
resolve points through RDF, then follow an opaque timeseries id into the existing store.

CONSTRAINTS
- Timeseries stay where they are. No bulk copy into a new DB for the tutorial/pattern.
- Wide BMS tables may remain for ETL; query path for apps is long/narrow or native TS API keyed by id.
- Opaque timeseries ids: either reuse stable historian point ids, or mint UUIDv5 once and store a mapping table (source_tag → timeseries_id). Never recompute ids at request time from column names in app code.

STEPS
1) Inventory: list equipment and points you care about (AHUs first). For each point note:
   human label, Brick class (e.g. Supply_Air_Static_Pressure_Sensor), owning equipment/part,
   unit (QUDT if possible), and the existing store key (tag, uuid, measurement+tags, …).

2) Author Brick RDF (Turtle or generate from CSV):
   - Site / Building / Floors / Equipment / parts / zones (isPartOf, hasPart, feeds).
   - Points with brick:isPointOf (and hasPoint inverse).
   - For each point: ref:hasExternalReference → ref:TimeseriesReference ;
       ref:hasTimeseriesId "…" ; ref:storedAt <Database> .
   - Database node: rdfs:label, backend type (e.g. "timescale"), connectionEnv "MY_TSDB_DSN"
     (env var name only).

3) Implement a thin adapter:
   read(timeseries_id, start, end, limit) → samples
   using the existing SQL/API (parameterized). Register it under the Database node’s backend.

4) Expose read-only SPARQL over the Brick graph (+ Brick ontology for subclass/tag inference).
   Point and timeseries HTTP helpers may wrap SPARQL for convenience.

5) Validate:
   - Every Point has exactly one TimeseriesReference + timeseries id + storedAt.
   - Spot-check: SPARQL finds duct static / setpoint / fan speed on an AHU; adapter returns a month of samples.
   - No application code hardcodes BMS column names — only the mapping/ETL layer may.

NON-GOALS
- Replacing the lakehouse. Rewriting historians. Building a full digital-twin UI.
- Putting connection strings or credentials into the RDF graph.

SUCCESS
Apps ask the graph “what is the supply-fan speed command on AHU_1?” and receive samples from
the existing production store via the opaque id — same pattern as Brick timeseries storage docs.
```

---

## How to add data in *this* repo

1. `data/<BUILDING>/<EQUIP>/history_wide.csv` with `timestamp_utc` + value columns.
2. `model/points/<BUILDING>__<EQUIP>.csv` — freeze `timeseries_id` (UUIDv5 rule in ARCHITECTURE A3).
3. New equipment/parts/zones → `model/site.ttl`.
4. Register in `data/datasets.json`.
5. `uv run brickts model build && uv run brickts validate --shacl && uv run brickts bootstrap && uv run pytest -q`.
