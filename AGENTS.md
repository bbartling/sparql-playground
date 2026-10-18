# AGENTS.md — sparql-playground (bldgts)

This repo is a **tutorial + near-production pattern**: a **Haystack** application RDF model describes the building;
timeseries are reached **only through the model** via opaque `ref:TimeseriesReference` links.
Here: FastAPI + read-only SPARQL + SQLite stand-in TSDB + Swagger at `/docs`. Lessons: `scripts/lesson_0*.py`.

- **Locked decisions:** [`agent_spec/ARCHITECTURE.md`](agent_spec/ARCHITECTURE.md)
- **Normal Framework (edge OT / BACnet / portal):** [`agent_spec/NORMAL_FRAMEWORK.md`](agent_spec/NORMAL_FRAMEWORK.md) — **bosspi** Pi live edge + OptiPlex standby, BACnet 5007, portal switch notes, CF tunnel + API keys; blog Part 2; no secrets
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
uv run bldgts model build
uv run bldgts bootstrap
uv run bldgts validate [--shacl]
uv run bldgts serve                      # http://127.0.0.1:8000/docs
uv run python scripts/lesson_01_mech_summary.py
uv run pytest -q && uv run ruff check .
```

## Invariants (do not break)

1. Every historized point has exactly one `ref:hasExternalReference` → `ref:TimeseriesReference` with exactly one `ref:hasTimeseriesId` and a `ref:storedAt` Database.
2. Every timeseries id in the model exists in the store; every mapped column is in the model.
3. No hardcoded CSV column names in API/services/graph/client code.
4. No hardcoded equipment ids in product code — select by Haystack markers, refs, or Open-FDD roles.
5. SPARQL **query** is read-only (no UPDATE/LOAD/SERVICE/FROM); row cap + timeout + length limit. Agent writes use scoped `/api/agent/plan` + `/api/agent/apply` (A19), never `/api/sparql`.
6. Parameterized SQL only; graph mutations via locked copy-on-write; atomic TTL writes.
7. No secrets in the graph, repo, or logs — Database nodes hold env-var *names*, not credentials.

## Guardrails

- Read-only reference: `/home/ben/Desktop/open-fdd` — never edit it.
- Don’t commit `var/`, `*.sqlite`, `.venv`, secrets. No Git LFS. Data files under 50 MB each.
- No auth, no CDN for the core API — Swagger at `/docs`. Optional Vite UI under the live part’s `checkpoint/web/` (Part 3). Live Turtle export: repo-root `building.ttl`.

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
- GET /health — wake/ping (ready flag for cold starts)
- POST /api/sparql — read-only SELECT/ASK; reject UPDATE, LOAD, SERVICE, FROM; timeout + row cap
- POST /api/sparql/upload — run a local .rq the human copied from the tutorial
- GET /api/points/{id}/timeseries?start=&end=&limit=
- GET /api/model/ttl?scope=model|site — download Turtle (full building graph, or site.ttl only)
- Interactive OpenAPI/Swagger docs; no custom HTML app required
- Lesson `.rq` files live in the repo only (not downloaded from the API)

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
5. `uv run bldgts model build && uv run bldgts validate --shacl && uv run bldgts bootstrap && uv run pytest -q`.

## Blog series checkpoints

[`blog/if-the-analyst-could-create-an-api/`](blog/if-the-analyst-could-create-an-api/) — **no repo-root `src/`/`web/`**. Each part freezes an app base under `checkpoint/`. Live package = Part 3 Haystack CRUD (`pyproject.toml` `module-root`). Part 2 = NF edge sensor client. Parts 4–6 are empty placeholders (data-viz/Timescale, Open-FDD Postgres, security). SQL course stays **independent**.

## Daily SQL course (operator requested, 2026-10-15)

`lessons/sql/INDEX.md` contains 84 daily lessons and 12 independent weekly challenges.
Read its `CONTRACT.md`, `LAB_GUIDE.md` and `REMOTE_SETUP.md` before modifying fixtures or helpers.
This independent PostgreSQL/Timescale learning lab is not an application-store replacement.
Use only the dedicated `brickts_course` database; preserve existing lab/application services.
Keep student work, passwords, dumps and observations under ignored `student-work/` or `var/`.

```bash
uv run python lessons/sql/validate_course.py
uv run python lessons/sql/graph_lab.py --check
uv run python lessons/sql/lab.py up
uv run python lessons/sql/lab.py load
uv run python lessons/sql/lab.py check
```

`validate_course.py` checks course structure and local links. It does not execute SQL.
The separate Timescale CI job performs real SQL known-answer and integrity checks.
Do not label those as proof of every learner solution, production security or all 77 rules.
