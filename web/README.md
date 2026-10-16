# Brick model + SPARQL UI

Tutorial React UI for the brickts API:

- **Model** — site → building → equipment → point tree; tag points; add / soft-delete
- **SPARQL** — browser editor with tutorial presets (`.rq` from `scripts/sparql/`), results table, point→timeseries drill, TTL download
- **Dashboard** — ops tag counts

Turtle serializes to repo-root **`building.ttl`** (background thread).

## Run

Terminal 1 — API (mutations optional for Model edits):

```bash
cd ..
BRICKTS_ALLOW_MUTATIONS=true uv run brickts serve
```

Terminal 2 — UI:

```bash
npm install
npm run dev
```

Open http://127.0.0.1:5173 · Swagger http://127.0.0.1:8000/docs
