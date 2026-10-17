# If the analyst could create an API

Blog series companion to the LinkedIn note
[If the analyst could create an API…](https://www.linkedin.com/posts/activity-7514716015222484993-LHRB).

Each **part** is a frozen checkpoint of the sparql-playground / brickts *API story* so you can
write the post, come back later, and build the next part without losing the prior shape.

| Part | Folder | Story |
|------|--------|--------|
| **1** | [`part-01-bare-sparql-api/`](part-01-bare-sparql-api/) | Bare FastAPI: Brick graph + read-only SPARQL + SQLite timeseries refs + laptop lessons (FC1) |
| **2** | [`part-02-model-crud-ui/`](part-02-model-crud-ui/) | Same core + model CRUD, ops tags, Vite UI, in-browser SPARQL, root `building.ttl` export |
| **3** | [`part-03-sql-postgres-timescale/`](part-03-sql-postgres-timescale/) | *(scaffold)* Blog chapter that *points at* deeper SQL / Timescale themes |
| **4** | [`part-04-coming-soon/`](part-04-coming-soon/) | *(scaffold)* Next API/blog chapter — fill when you draft it |

The **live app** at the repo root tracks Part 2 (and beyond). Part 1 keeps a **source snapshot**
under `checkpoint/` taken from git so the bare API does not get overwritten as the mainline grows.

## Independent: the SQL course (not part of this series tree)

The **84-day PostgreSQL / Timescale / SPARQL course** lives on its own and stays that way:

- [`lessons/sql/INDEX.md`](../../lessons/sql/INDEX.md)
- Lab: [`LAB_GUIDE.md`](../../lessons/sql/LAB_GUIDE.md) · remote: [`REMOTE_SETUP.md`](../../lessons/sql/REMOTE_SETUP.md)
- Own DB (`brickts_course`), own validators — **not** nested under `blog/`

Blog Parts 3–4 may **link** into those lessons for readers; they do not relocate, fork, or
own the course. Treat `lessons/sql/` as a parallel track you can study anytime.

## How to use these checkpoints

1. Write / edit the blog draft for that part in its folder (add or extend `draft.md`).
2. For Part 1, open `checkpoint/` — frozen bare API surface (no `web/`, no model CRUD).
3. For Part 2, the runnable app is the **repo root** (`uv run brickts serve`, optional `web/`).
4. For Parts 3–4, keep article notes here; send hands-on SQL work to `lessons/sql/`.

## Shared building data (API parts)

Do **not** duplicate large CSVs under `blog/`. Parts 1–2 use the repo’s:

- `model/site.ttl`, `model/building_50.ttl`, `model/points/`
- `data/BUILDING_50/`
- Brick invariants in [`agent_spec/ARCHITECTURE.md`](../../agent_spec/ARCHITECTURE.md)
