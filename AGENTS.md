# AGENTS.md — sparql-playground (brickts)

A tutorial that is also near-production. It hosts a **Brick RDF model** and queries
**timeseries through the model** (Brick ref-schema, <https://docs.brickschema.org/metadata/timeseries-storage.html>).
FastAPI serves a read-only SPARQL endpoint, point lookups by class or tag, timeseries
JSON, and Open-FDD fault applicability APIs. Interactive surface is FastAPI Swagger (`/docs`); tutorial scripts live under `scripts/lesson_0*.py`. **Async SQLite (aiosqlite)** stands in for a real TSDB on the HTTP path; SPARQL/rdflib runs in a thread pool.

- **Build plan (start here if the app is not built yet):** [`.cursor/plans/sparql_playground_build.plan.md`](.cursor/plans/sparql_playground_build.plan.md)
- **Locked decisions:** [`agent_spec/ARCHITECTURE.md`](agent_spec/ARCHITECTURE.md)

## Architecture in one picture

```
data/<BUILDING>/<EQUIP>/history_wide.csv ──(brickts bootstrap, uses model/points/*.csv)──▶ TimeseriesStore (SQLite: samples(timeseries_id, ts, value))
model/site.ttl + model/points/*.csv ──(brickts model build)──▶ model/building_50.ttl ──▶ GraphService (model + Brick ontology)
HTTP ─▶ routers ─▶ services ─▶ GraphService (SPARQL)  ─▶ point ─ref:hasExternalReference─▶ TimeseriesReference
                                                      ─ref:hasTimeseriesId + ref:storedAt─▶ Database node ─▶ store registry ─▶ await TimeseriesStore.read()
```

## Commands

```bash
uv sync                                   # install (project-local .venv)
uv run brickts model build                # render model/building_50.ttl from site.ttl + mappings
uv run brickts bootstrap                  # CSV -> SQLite (idempotent; --force to reload)
uv run brickts validate [--shacl]         # SPARQL invariant checks (+ Brick SHACL)
uv run brickts serve                      # http://127.0.0.1:8000/docs
uv run python scripts/lesson_01_mech_summary.py   # beginner series (edit lesson_config.py)
uv run python scripts/analyst_client.py   # multi-rule Open-FDD against a running server
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
```

## Invariants (tests enforce these; never break them)

1. Every `brick:Point` has **exactly one** `ref:hasExternalReference` to a `ref:TimeseriesReference`.
   That reference has **exactly one** `ref:hasTimeseriesId` and a `ref:storedAt` to a node typed
   `ref:Database` or `brick:Database`.
2. Every timeseries id in the model exists in the store, and every mapped CSV column is in the model.
3. **No hardcoded CSV column names** in `src/brickts/api`, `src/brickts/services`, `src/brickts/graph`,
   or `scripts/analyst_client.py`. Column names live only in `data/`, `model/points/*.csv`, and `src/brickts/ingest.py`.
4. **No equipment ids hardcoded** in product code. Ids are request parameters, and selection is by Brick class, tags, or roles.
5. The SPARQL endpoint stays read-only: no UPDATE, LOAD, SERVICE, or FROM. Row cap, timeout, and length limit apply.
6. SQL is parameterized only. Graph mutations go through `GraphService` (lock + copy-on-write). TTL writes are atomic.
7. No secrets in the graph, the repo, or the logs. Database nodes carry labels and env-var *names*, never connection strings with credentials.

## How to add data (new CSV, same or new equipment)

1. Put the CSV at `data/<BUILDING>/<EQUIP>/history_wide.csv`. It needs a `timestamp_utc` column plus value columns. Tutorial site ships `AHU_1` and `AHU_2`.
2. Author `model/points/<BUILDING>__<EQUIP>.csv` with columns
   `source_column,point_id,label,brick_class,unit,owner_id,openfdd_role,timeseries_id,notes`.
   Generate ids with the UUIDv5 rule in ARCHITECTURE A3 and freeze them in the file.
3. For new equipment, zones, or parts, add their triples to `model/site.ttl` (`brick:isPartOf` / `brick:hasPart`, `brick:feeds`).
4. Register the dataset in `data/datasets.json`.
5. Run `uv run brickts model build && uv run brickts validate --shacl && uv run brickts bootstrap && uv run pytest -q`.
6. Runtime alternative (mutations enabled): `uv run brickts ingest --csv … --mapping …`, or `POST /api/model/points`.

## How to extend the model

- Pick classes from Brick 1.5 (`brickschema` bundled ontology) and check that each exists:
  `uv run python -c "import brickschema;from rdflib import RDF,OWL,Namespace;B=Namespace('https://brickschema.org/schema/Brick#');g=brickschema.Graph(load_brick=True);print((B['Fan_Speed_Command'],RDF.type,OWL.Class) in g)"`.
- Points attach with `brick:isPointOf` to the equipment or its part (Supply_Fan, Outside_Damper, …), and include the inverse `brick:hasPoint`.
- Units use QUDT (`unit:DEG_F`, `unit:IN_H2O`, `unit:PERCENT`). Leave the unit out for binary or enumerated points.
- When a new Open-FDD role is needed, add it to `ROLE_REQUIREMENTS` in `src/brickts/services/faults.py`.

## How to add a TSDB backend (Timescale, Influx, a historian)

1. Implement `TimeseriesStore` in `src/brickts/store/<backend>.py`. Keep it parameterized, return `Sample` objects, and make `read` honor `start`, `end`, and `limit`.
2. Register it in `src/brickts/store/registry.py` under a `bts:backend` value (for example `"timescale"`), and read its connection from env settings.
3. In `model/site.ttl`, point the Database node (`a ref:Database, brick:Database ; bts:backend "timescale"`) at it, or add a second Database node and set `ref:storedAt` per reference.
4. Graph, routers, client, and tests do not change. Add one contract test that runs the shared store test suite against the new backend.

## Guardrails

- Read-only reference repo: `/home/ben/Desktop/open-fdd`. **Never edit it.**
- Don't commit `var/`, `*.sqlite`, `.venv`, or any secrets. Don't use Git LFS. Data files must stay under 50 MB each; if one is larger, stop and ask.
- Keep the code small and typed. Use pydantic for every request/response schema. Write a comment only for a constraint the code cannot show.
- No auth system, no extra services, no CDN, no Node build.
