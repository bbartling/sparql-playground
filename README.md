# brickts — Brick timeseries SPARQL tutorial

Near-production tutorial for the [Brick timeseries storage pattern](https://docs.brickschema.org/metadata/timeseries-storage.html): an RDF model is the **only** path from a logical point to historian data. This repo uses **async SQLite** ([aiosqlite](https://github.com/OMnilight/aiosqlite), long/narrow `samples(timeseries_id, ts, value)`) as a TSDB stand-in behind an async `TimeseriesStore` protocol, so you can later swap in TimescaleDB, InfluxDB, or a site historian without changing the HTTP API or SPARQL surface. SPARQL evaluation stays on **rdflib** in a thread pool — only timeseries I/O is async.

**Scope:** `BUILDING_50` with `AHU_1` and `AHU_2` (points + parts modeled; 5-minute historian CSVs under 50 MB each).

## Architecture

```
history_wide.csv ── bootstrap ──▶ SqliteTimeseriesStore
site.ttl + points CSV ── model build ──▶ building_50.ttl ──▶ GraphService (+ Brick 1.5 ontology)
HTTP ──▶ read-only SPARQL / point lookup / timeseries JSON
Browser ──▶ /docs (Swagger) · laptop ──▶ scripts/lesson_0*.py (+ Open-FDD)
```

Locked decisions: [`agent_spec/ARCHITECTURE.md`](agent_spec/ARCHITECTURE.md). Agent guide: [`AGENTS.md`](AGENTS.md).

## Quick start

```bash
uv sync
uv run brickts model build
uv run brickts validate --shacl
uv run brickts bootstrap          # idempotent; --force to reload
uv run brickts serve              # http://127.0.0.1:8000/docs
uv run pytest -q && uv run ruff check .
```

**Server = model + SPARQL + timeseries.** Explore the API in Swagger (`/docs`). Progressive Python lessons (no CLI args — edit `scripts/lesson_config.py`):

```bash
# Point BASE_URL at Render or localhost in scripts/lesson_config.py
uv run python scripts/lesson_01_mech_summary.py   # health + mech roll-up + tags
uv run python scripts/lesson_02_fc1_points.py      # SPARQL → FC1 point ids
uv run python scripts/lesson_03_fc1_dataframe.py   # month of samples → pandas DF
uv run python scripts/lesson_04_run_fc1.py           # local open_fdd.run_rule("FC1")
```

Power tool for many rules / AHUs:

```bash
uv run python scripts/analyst_client.py --equipment AHU_1 --list-only
uv run python scripts/analyst_client.py --equipment AHU_1 --rule FC2
uv run python scripts/analyst_client.py --all-equipment --all-applicable --quiet
```

Environment variables use the `BRICKTS_` prefix (see `src/brickts/settings.py`). Docker/Render must bind `0.0.0.0` and honor `$PORT` (the image does).

## AI / human modeling workflow

1. Author equipment and locations in `model/site.ttl` (Site, Building, Floors, AHUs, parts, zones, Database node).
2. Author `model/points/BUILDING_50__AHU_*.csv` (`source_column`, `point_id`, Brick class, QUDT unit, owner, optional role, frozen UUIDv5 `timeseries_id`).
3. `uv run brickts model build` merges every `model/points/*.csv` into committed `model/building_50.ttl` with `ref:TimeseriesReference` on every point.
4. `uv run brickts bootstrap` loads wide CSVs into SQLite using the mappings (never query by CSV column name in app code).

## Interactive surface

There is **no custom HTML UI** — bare FastAPI + **Swagger** at `/docs` (`/` redirects there). **POST** `/api/sparql` ships with prefilled example bodies (mech summary, list AHUs) so Try it out / curl is ready. More presets: **GET** `/api/sparql/examples`. Tutorial depth is in `scripts/lesson_0*.py`.

## Production notes

- **Auth:** not included; keep on LAN/VPN. Set `BRICKTS_ALLOW_MUTATIONS=true` only for controlled model edits.
- **TSDB:** implement `TimeseriesStore` for your backend; register `bts:backend` in `store/registry.py`; point Database nodes at env-driven connection settings (never secrets in the graph).
- **Triplestore:** replace in-process rdflib with a hosted store; keep the same read-only guard (no UPDATE/SERVICE/FROM, row cap, timeout).
- **Migrations:** mapping CSV + `ingest_log` sha256; use `--force` or versioned dataset keys for reloads.
- **Metrics:** JSON request logs via stdlib logging (`BRICKTS_LOG_JSON=true`).

## Docker

```bash
docker compose up --build
# Swagger: http://127.0.0.1:8000/docs
```

## License

See [LICENSE](LICENSE).
