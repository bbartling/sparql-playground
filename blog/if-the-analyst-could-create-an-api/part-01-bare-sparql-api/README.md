# Part 1 — Bare SPARQL + timeseries API

**Series:** [If the analyst could create an API](../README.md)  
**LinkedIn seed:** [post](https://www.linkedin.com/posts/activity-7514716015222484993-LHRB)  
**Git freeze:** `2d3c72e` (last mainline commit before model CRUD / Vite UI) — see `GIT_SHA.txt`

## What this part is

A **read-only** tutorial API an analyst can stand up:

1. Brick RDF describes AHUs / points / zones.
2. `POST /api/sparql` (and `/upload`) answers inventory questions.
3. Points resolve **opaque** timeseries ids → SQLite samples (never raw CSV column names in the API).
4. Laptop scripts (`lesson_01`…`04`) do SPARQL → pandas → Open-FDD FC1.

HTTP surface at freeze time:

- `GET /health`
- `POST /api/sparql`, `POST /api/sparql/upload`
- `GET /api/points/{id}/timeseries`
- `GET /api/model/ttl` (`scope=model|site`)
- Swagger at `/docs` — no custom UI

## Checkpoint contents

Frozen sources live under [`checkpoint/`](checkpoint/):

- `checkpoint/src/brickts/` — FastAPI app (no `model_crud`, no CORS UI package)
- `checkpoint/scripts/lesson_0*.py`, `checkpoint/scripts/sparql/`
- `checkpoint/tests/` — API / UI / FC1 client tests from that era

Shared data stays at the **repo root** (`model/`, `data/`).

## Restore tip (optional)

To inspect the full tree at this SHA without the snapshot folder:

```bash
git show 2d3c72e:src/brickts/api/app.py | less
# or a throwaway worktree:
# git worktree add /tmp/brickts-part1 2d3c72e
```

## Blog draft

Add your article draft here as `draft.md` when ready. Next: [Part 2](../part-02-model-crud-ui/).
