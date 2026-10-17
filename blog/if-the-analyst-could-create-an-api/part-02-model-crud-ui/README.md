# Part 2 — Haystack model CRUD + Vite UI

**Series:** [If the analyst could create an API](../README.md)  
**Builds on:** [Part 1](../part-01-bare-sparql-api/)  
**Status:** **live app base** (repo-root `src/` and `web/` are symlinks into this `checkpoint/`)

## What this part is

Smart-building IoT tagging UI on the brickts API:

- Haystack markers (vendored `data/haystack/defs.json` + `difflib` suggest)
- Hold-to-rename, right-click closest match, Save via CRUD
- Opaque timeseries refs preserved
- SPARQL browser + coverage dashboard

## Layout

```
checkpoint/
  src/brickts/   ← also repo-root src/  (symlink)
  web/           ← also repo-root web/  (symlink)
  scripts/
  tests/
```

Do **not** maintain a second copy of the package under a real root `src/` tree. Edit here (or via the symlinks). Shared `model/` + `data/` stay at the repository root.

## Run

From the **repository root**:

```bash
uv sync
uv run brickts model build
uv run brickts bootstrap
BRICKTS_ALLOW_MUTATIONS=true uv run brickts serve   # :8000/docs

cd web && npm install && npm run dev                 # :5173
```

## Next

[Part 3 — Data viz + Timescale](../part-03-data-viz-timescale/) (placeholder until frozen).
