# Haystack-native UI + blog Parts 3–5 placeholders

> **For agentic workers:** implement task-by-task; one green test cycle per task where noted.

**Goal:** Replace ship/receive with Haystack markers + suggest/rename UI; keep opaque timeseries; scaffold blog Parts 3–5 as empty named placeholders (data viz/Timescale, Open-FDD SQL, security).

**Spec:** `docs/superpowers/specs/2026-10-17-haystack-native-ui-design.md`

## Task 1: Blog Parts 3–5 directory rename

- Replace `part-03-sql-postgres-timescale` → `part-03-data-viz-timescale`
- Replace `part-04-coming-soon` → `part-04-fdd-openfdd-postgres`
- Add `part-05-security`
- Each: `README.md`, `GIT_SHA.txt` (empty/`TBD`), `checkpoint/.gitkeep`
- Update series `README.md` + `AGENTS.md`

## Task 2: Vendor Haystack defs + suggest module

- Pin defs under `data/haystack/` (VERSION + defs JSON or curated markers index)
- `src/bldgts/haystack/defs.py` + `suggest.py` using `difflib.get_close_matches`
- Tests for suggest ranking

## Task 3: CRUD — markers replace ops tags

- `BTS.hasHaystackMarker`, rename API, retarget `/api/model/tags`
- Remove meta-tags / ops dashboard semantics
- Update `tests/test_model_crud.py`

## Task 4: UI Haystack mode

- Rewrite `web/src/main.tsx` + styles: markers, hold=rename all levels, right-click=suggest
- Dashboard = coverage

## Task 5: ARCHITECTURE lock note + smoke

- Update A2/A15 notes for Haystack UI path (timeseries refs retained)
- `pytest` + manual smoke
