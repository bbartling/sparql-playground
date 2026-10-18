# Part 3 — Haystack model CRUD + Vite UI

**Series:** [If the analyst could create an API](../README.md)  
**Builds on:** [Part 2](../part-02-nf-edge-sensors/) (NF edge sensors) · [Part 1](../part-01-bare-sparql-api/)  
**Status:** **live app base** — Python package **`bldgts`** (generic building/timeseries name; not Brick-specific)

## Layout

```
checkpoint/
  src/bldgts/      # FastAPI package
  web/             # Vite UI (Edit tree + SPARQL + Agent plan/apply + RDF)
  scripts/
  tests/
```

Shared data: repo-root `model/`, `data/` (incl. `data/haystack/defs.json`).

## Run

```bash
# from repository root
uv sync
uv run bldgts model build
uv run bldgts bootstrap
BLDGTS_ALLOW_MUTATIONS=true uv run bldgts serve   # http://127.0.0.1:8000/docs

cd blog/if-the-analyst-could-create-an-api/part-03-model-crud-ui/checkpoint/web
npm install && npm run dev                        # http://127.0.0.1:5173
```

**Edit** locks the tree. Left-click any row to rename or edit Haystack markers and typed values/references. Review fuzzy suggestions before adding them. Edit stays focused on authoring; inspect saved checks through the validation summary. Red means required/invalid metadata, yellow means recommendations only, and green means no issues found in the supported Haystack profile. The separate SPARQL integrity view checks graph hygiene. **Agent** builds a scoped `INSERT DATA`/`DELETE DATA` plan (`POST /api/agent/plan`) and applies the exact stored plan (`POST /api/agent/apply`) — `/api/sparql` stays read-only. **RDF** shows live Turtle.

See [Haystack modeling contract](HAYSTACK_MODELING.md) and architecture **A19** for the typed metadata API, agent plan/apply rules, and remaining limitations (not full Haystack protocol/ontology conformance; SPARQL worker threads are not hard-cancelled).

## Verify

From the repository root:

```bash
uv run pytest -q
uv run ruff check .
cd blog/if-the-analyst-could-create-an-api/part-03-model-crud-ui/checkpoint/web
npm ci
npm run build
```

The checkpoint uses shared repository `data/`, `model/`, and the root Python environment; copy those with it when packaging a separate project. Root `tests/` is the authoritative live regression suite.

## Next

[Part 4 — Data viz + Timescale](../part-04-data-viz-timescale/)
