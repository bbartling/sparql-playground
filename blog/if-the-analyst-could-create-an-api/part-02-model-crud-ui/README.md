# Part 2 — Haystack model CRUD + Vite UI

**Series:** [If the analyst could create an API](../README.md)  
**Builds on:** [Part 1](../part-01-bare-sparql-api/)  
**Status:** **live app base** (uv `module-root` points here; there is no repo-root `src/` or `web/`)

## Layout

```
checkpoint/
  src/brickts/     # FastAPI package (Haystack markers + timeseries refs)
  web/             # Vite UI
  scripts/
  tests/
```

Shared building data stays at the **repository root** (`model/`, `data/`, including `data/haystack/defs.json`).

## Run

From the **repository root**:

```bash
uv sync
uv run brickts model build
uv run brickts bootstrap
BRICKTS_ALLOW_MUTATIONS=true uv run brickts serve   # http://127.0.0.1:8000/docs
```

UI (separate terminal):

```bash
cd blog/if-the-analyst-could-create-an-api/part-02-model-crud-ui/checkpoint/web
npm install
npm run dev    # http://127.0.0.1:5173
```

## Next

[Part 3 — Data viz + Timescale](../part-03-data-viz-timescale/) (placeholder until frozen).
