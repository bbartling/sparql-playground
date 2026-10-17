# Part 2 — Model CRUD, tag-tree UI, browser SPARQL

**Series:** [If the analyst could create an API](../README.md)  
**Builds on:** [Part 1](../part-01-bare-sparql-api/)  
**Git freeze:** see `GIT_SHA.txt` (mainline when this checkpoint was taken)

## What this part adds

Still the same Brick → SPARQL → opaque timeseries path. Plus:

| Addition | Where |
|----------|--------|
| Site → equip → point tree + soft-delete (keeps timeseries refs) | `checkpoint/src/brickts/services/model_crud.py`, `/api/model/*` |
| Ops tags (Received / Not received / LATE / DAMAGED / …) | `POST /api/model/tags` |
| Vite React UI (Model / SPARQL / Dashboard) | [`checkpoint/web/`](checkpoint/web/) |
| Bundled `.rq` list for the browser editor | `GET /api/sparql/examples` |
| Beginner Turtle export at repo root | `building.ttl` via background serialize |

Mutations require `BRICKTS_ALLOW_MUTATIONS=true`.

## Checkpoint contents

Frozen sources live under [`checkpoint/`](checkpoint/):

- `checkpoint/src/brickts/` — FastAPI app including model CRUD / CORS / SPARQL examples
- `checkpoint/web/` — Vite Model / SPARQL / Dashboard UI
- `checkpoint/scripts/lesson_0*.py`, SPARQL helpers
- `checkpoint/tests/` — API / UI / FC1 tests at freeze time

Shared building data stays at the **repo root** (`model/`, `data/`). Do not duplicate CSVs here.

As mainline grows (Part 3+), keep running **this** tree via the commands below so the blog stays honest to the Part 2 shape.

## Run the Part 2 checkpoint

From the **repository root** (so `model/` and `data/` resolve). Forces Python to import the frozen package:

```bash
uv sync
uv run brickts model build
uv run brickts bootstrap

export PYTHONPATH="blog/if-the-analyst-could-create-an-api/part-02-model-crud-ui/checkpoint/src${PYTHONPATH:+:$PYTHONPATH}"
BRICKTS_ALLOW_MUTATIONS=true uv run brickts serve   # http://127.0.0.1:8000/docs
```

Optional UI (separate terminal, still from repo root):

```bash
cd blog/if-the-analyst-could-create-an-api/part-02-model-crud-ui/checkpoint/web
npm install
npm run dev    # http://127.0.0.1:5173 — API proxy expects :8000
```

Confirm the freeze is what is loaded:

```bash
PYTHONPATH=blog/if-the-analyst-could-create-an-api/part-02-model-crud-ui/checkpoint/src \
  uv run python -c "import brickts; print(brickts.__file__)"
# should print .../part-02-model-crud-ui/checkpoint/src/brickts/__init__.py
```

## Blog draft

Add your article draft here as `draft.md` when ready. Next: [Part 3](../part-03-sql-postgres-timescale/).
