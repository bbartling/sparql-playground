# brickts

A small tutorial API for **building data**:

1. A **Brick** model describes the site (AHUs, fans, sensors, zones…).
2. You ask questions with **SPARQL** (“which AHUs exist?”, “where is duct static pressure?”).
3. The model points at **timeseries ids** in a database — you never query by raw CSV column name.

This repo uses SQLite as a stand-in historian. A real site would use Timescale, Influx, or a data lake; the API shape stays the same.

**Demo site:** `BUILDING_50` with `AHU_1` and `AHU_2`.  
**Live API docs:** <https://sparql-playground.onrender.com/docs>  
**Queries to paste into Swagger:** [`docs/sparql_queries.md`](docs/sparql_queries.md)

```
CSV history  ──bootstrap──▶  SQLite (long/narrow samples)
site.ttl + point maps  ──build──▶  Brick Turtle  ──▶  SPARQL API
Browser → /docs (Swagger)     Laptop → scripts/lesson_0*.py
```

Details for agents: [`AGENTS.md`](AGENTS.md). Locked choices: [`agent_spec/ARCHITECTURE.md`](agent_spec/ARCHITECTURE.md).

## Run locally

```bash
uv sync
uv run brickts model build
uv run brickts bootstrap
uv run brickts serve          # http://127.0.0.1:8000/docs
```

## Tutorial scripts (no CLI args)

Edit `BASE_URL` (and friends) at the top of each `scripts/lesson_0*.py`, then:

```bash
uv run python scripts/lesson_01_mech_summary.py   # inventory via SPARQL
uv run python scripts/lesson_02_fc1_points.py      # find FC1 points
uv run python scripts/lesson_03_fc1_dataframe.py   # month → pandas DF
uv run python scripts/lesson_04_run_fc1.py           # run Open-FDD FC1 locally
```

## Docker

```bash
docker compose up --build
# Swagger: http://127.0.0.1:8000/docs
```

## License

See [LICENSE](LICENSE).
