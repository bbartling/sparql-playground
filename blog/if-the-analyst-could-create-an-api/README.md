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

Each published API part freezes a **`checkpoint/`** of that app base (`src/`, tests, scripts;
Part 2 also freezes `web/`). Shared `model/` + `data/` stay at the repo root. The **live**
tree at the root keeps moving; reopen an older part by `PYTHONPATH=…/checkpoint/src` as
documented in that part’s README.

## Independent: the SQL course (not part of this series tree)

The **84-day PostgreSQL / Timescale / SPARQL course** lives on its own and stays that way:

- [`lessons/sql/INDEX.md`](../../lessons/sql/INDEX.md)
- Lab: [`LAB_GUIDE.md`](../../lessons/sql/LAB_GUIDE.md) · remote: [`REMOTE_SETUP.md`](../../lessons/sql/REMOTE_SETUP.md)
- Own DB (`brickts_course`), own validators — **not** nested under `blog/`

Blog Parts 3–4 may **link** into those lessons for readers; they do not relocate, fork, or
own the course. Treat `lessons/sql/` as a parallel track you can study anytime.

## How to use these checkpoints

1. Write / edit the blog draft for that part in its folder (add or extend `draft.md`).
2. Freeze the app base into that part’s `checkpoint/` when the chapter ships (pin `GIT_SHA.txt`).
3. Run a frozen part with `PYTHONPATH=blog/…/checkpoint/src` from the repo root (see each README).
4. Parts 3–4: article notes here; hands-on SQL stays in independent `lessons/sql/` (link, don’t relocate).

## Shared building data (API parts)

Do **not** duplicate large CSVs under `blog/`. Parts 1–2 use the repo’s:

- `model/site.ttl`, `model/building_50.ttl`, `model/points/`
- `data/BUILDING_50/`
- Brick invariants in [`agent_spec/ARCHITECTURE.md`](../../agent_spec/ARCHITECTURE.md)
