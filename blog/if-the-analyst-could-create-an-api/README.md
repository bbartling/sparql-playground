# If the analyst could create an API

Blog series companion to the LinkedIn note
[If the analyst could create an API…](https://www.linkedin.com/posts/activity-7514716015222484993-LHRB).

Each **part** freezes an app base under `checkpoint/` (when shipped) so the next chapter
can grow without erasing the prior shape.

| Part | Folder | Story |
|------|--------|--------|
| **1** | [`part-01-bare-sparql-api/`](part-01-bare-sparql-api/) | Bare FastAPI: Brick graph + read-only SPARQL + SQLite timeseries (historical freeze) |
| **2** | [`part-02-model-crud-ui/`](part-02-model-crud-ui/) | **Live app base** — Haystack CRUD + Vite UI (`checkpoint/`; root `src/`/`web/` symlink here) |
| **3** | [`part-03-data-viz-timescale/`](part-03-data-viz-timescale/) | *(placeholder)* Data viz + SQLite → Postgres/Timescale cutover |
| **4** | [`part-04-fdd-openfdd-postgres/`](part-04-fdd-openfdd-postgres/) | *(placeholder)* Open-FDD on Postgres SQL |
| **5** | [`part-05-security/`](part-05-security/) | *(placeholder)* API / SPARQL / historian security |

Parts 3–5 are **empty scaffolds** (`README` + `checkpoint/.gitkeep`) until those chapters ship.

## Independent: the SQL course (not part of this series tree)

[`lessons/sql/INDEX.md`](../../lessons/sql/INDEX.md) stays its own track (own DB, own validators).
Blog parts may **link** into it; they do not relocate or own the course.

## How to use checkpoints

1. Draft the article in that part’s folder (`draft.md` when ready).
2. Freeze `checkpoint/` + pin `GIT_SHA.txt` when the chapter ships.
3. Run a frozen part with `PYTHONPATH=blog/…/checkpoint/src` from the repo root (see each README).
