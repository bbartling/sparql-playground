# If the analyst could create an API

Blog series companion to the LinkedIn note
[If the analyst could create an API…](https://www.linkedin.com/posts/activity-7514716015222484993-LHRB).

**App bases live only under each part’s `checkpoint/`.** There is no repo-root `src/` or `web/`.
The live install (`uv run brickts`) is wired in `pyproject.toml` to **Part 2** until a later part becomes current.

| Part | Folder | Story |
|------|--------|--------|
| **1** | [`part-01-bare-sparql-api/`](part-01-bare-sparql-api/) | Frozen bare Brick + SPARQL + SQLite API |
| **2** | [`part-02-model-crud-ui/`](part-02-model-crud-ui/) | **Live** — Haystack CRUD + Vite UI |
| **3** | [`part-03-data-viz-timescale/`](part-03-data-viz-timescale/) | *(empty)* Data viz + Timescale cutover |
| **4** | [`part-04-fdd-openfdd-postgres/`](part-04-fdd-openfdd-postgres/) | *(empty)* Open-FDD on Postgres |
| **5** | [`part-05-security/`](part-05-security/) | *(empty)* Security |

## Independent SQL course

[`lessons/sql/INDEX.md`](../../lessons/sql/INDEX.md) — parallel track; not owned by this series.

## Checkpoints

1. Freeze code into that part’s `checkpoint/` when the chapter ships; pin `GIT_SHA.txt`.
2. To run an older freeze: point `PYTHONPATH` at that `checkpoint/src`, or temporarily change `tool.uv.build-backend.module-root`.
3. Parts 3–5 stay empty (`README` + `checkpoint/.gitkeep`) until built.
