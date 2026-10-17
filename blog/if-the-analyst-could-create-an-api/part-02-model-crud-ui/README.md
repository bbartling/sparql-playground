# Part 2 — Haystack model CRUD + Vite UI

**Series:** [If the analyst could create an API](../README.md)  
**Builds on:** [Part 1](../part-01-bare-sparql-api/)  
**Status:** **live app base** — Python package **`bldgts`** (generic building/timeseries name; not Brick-specific)

## Layout

```
checkpoint/
  src/bldgts/      # FastAPI package
  web/             # Vite UI (Edit → click point → tag menu + raw RDF tab)
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

cd blog/if-the-analyst-could-create-an-api/part-02-model-crud-ui/checkpoint/web
npm install && npm run dev                        # http://127.0.0.1:5173
```

**Edit** locks the tree · click a point · small tag menu (fuzzy Haystack chips from BAS names) · **Tag** writes RDF. Model tab shows green/yellow/red tagging coverage; SPARQL tab shows RDF integrity (orphans/duplicates). **RDF** tab shows live Turtle from `/api/model/ttl`.

## Next

[Part 3 — Data viz + Timescale](../part-03-data-viz-timescale/)
