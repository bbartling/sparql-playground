# Part 2 — Model CRUD, tag-tree UI, browser SPARQL

**Series:** [If the analyst could create an API](../README.md)  
**Builds on:** [Part 1](../part-01-bare-sparql-api/)  
**Git (current Part 2 line):** see `GIT_SHA.txt` (`bd064b1` feature + `62648f4` format fix)

## What this part adds

Still the same Brick → SPARQL → opaque timeseries path. Plus:

| Addition | Where |
|----------|--------|
| Site → equip → point tree + soft-delete (keeps timeseries refs) | `src/brickts/services/model_crud.py`, `/api/model/*` |
| Ops tags (Received / Not received / LATE / DAMAGED / …) | `POST /api/model/tags` |
| Vite React UI (Model / SPARQL / Dashboard) | [`web/`](../../../web/) |
| Bundled `.rq` list for the browser editor | `GET /api/sparql/examples` |
| Beginner Turtle export at repo root | `building.ttl` via background serialize |

Mutations require `BRICKTS_ALLOW_MUTATIONS=true`.

## Run (live Part 2 = repo root)

```bash
# from repo root
uv sync
uv run brickts model build
uv run brickts bootstrap
BRICKTS_ALLOW_MUTATIONS=true uv run brickts serve   # :8000/docs

# optional UI
cd web && npm install && npm run dev                 # :5173
```

## Why there is no `checkpoint/` copy here

Part 2 **is** the mainline application. Duplicating `src/` + `web/` would rot. Use this folder for:

- `draft.md` — Part 2 blog write-up
- notes / screenshots / outline as you publish

Key commits:

- `bd064b1` — CRUD API + web UI + SPARQL examples + `building.ttl`
- `62648f4` — ruff format (CI green)

## Next

[Part 3](../part-03-sql-postgres-timescale/) — PostgreSQL / Timescale via the SQL course.
