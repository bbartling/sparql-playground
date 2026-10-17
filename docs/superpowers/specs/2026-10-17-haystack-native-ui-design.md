# Design: Haystack-native smart-building UI (replace Brick + ship/receive)

**Date:** 2026-10-17  
**Status:** draft — awaiting operator approval before implementation  
**Repo:** sparql-playground / bldgts  

## Intent

Go **full Project Haystack** for the live smart-building IoT tutorial app:

1. **Remove shipping/receiving ops tags** (`RECEIVED`, `LATE`, meta dashboard) from UI and CRUD.
2. **Remove Brick as the live modeling vocabulary** for the tree UI, SPARQL examples aimed at the UI, and model CRUD.
3. Use **Haystack entity kinds + marker tags** (site, floor, equip, point, sensor, sp, …) with rename + closest-name suggest + Save.
4. Keep the **opaque timeseries read path** (point → timeseries id → store). That pattern is ontology-agnostic; only the graph vocabulary around the point changes.

This **explicitly changes locked architecture A2/A8/A9/A15** (Brick-only model path / Brick ontology / Brick UI). Operator requested 2026-10-17: “full blown haystack… get rid of the BRICK”.

## Non-goals (this milestone)

- Rewriting the 84-day SQL course or its Brick/SPARQL week 8 lessons.
- Deleting Part 1 / Part 2 **blog checkpoints** (they remain historical Brick app bases).
- Replacing SQLite with a Haystack server (SkySpark, etc.).
- Implementing the full Haystack HTTP API (ops, watches, hisRead protocol).
- Perfect PH/AHU proto coverage for every possible point — starter AHU set only.

## Product picture

```
Haystack defs (pinned JSON) ──suggest──▶ UI (tree + markers)
        │
site + points mapping ──model build──▶ building graph (Haystack RDF)
        │
HTTP ──▶ SPARQL / model CRUD / points/{id}/timeseries
 point ──▶ opaque timeseries_id ──▶ TimeseriesStore.read()
```

Users think in **Haystack tags**. The graph stores Haystack-shaped RDF. Timeseries stay behind opaque ids.

## Approaches considered

| | Approach | Pros | Cons |
|---|----------|------|------|
| A | Brick graph + Haystack tags overlay | Smaller change | User rejected — still Brick |
| **B (chosen)** | **Haystack-native live graph + UI; Brick frozen in blog checkpoints** | Matches “go nuts”; checkpoints preserve history | Large; ARCHITECTURE update |
| C | Dual Brick+Haystack twin always | Interop demos | Double maintenance; confuses UI |

**Recommendation: B.**

## Architecture

### Graph vocabulary (live app)

- **Drop** runtime dependency on Brick 1.5 ontology for the model UI and default SPARQL examples.
- **Load** a pinned Haystack defs pack (JSON from Project Haystack downloads / haystack-defs release) under `data/haystack/` (version file + `defs.json`). No network fetch at request time.
- Represent entities as RDF resources with:
  - `rdf:type` / marker membership aligned to Haystack defs (e.g. markers `site`, `floor`, `equip`, `ahu`, `point`, `sensor`, `sp`, …) using a stable namespace such as `https://project-haystack.org/def/ph#` (or documented `ph:` / `hs:` prefix chosen in implementation and locked in ARCHITECTURE).
  - `rdfs:label` for display names (rename target).
  - Haystack markers as repeated triples (predicate TBD, e.g. `hs:hasMarker` → literal or def URI).
  - **Timeseries:** keep Brick-ref-compatible **or** map to Haystack-ish `his` + opaque id + `storedAt` Database node — same store registry. Prefer keeping `ref:hasExternalReference` / `ref:hasTimeseriesId` for minimal store churn unless a clean `hs:` equivalent is cheap; document the choice in ARCHITECTURE when implementing.

### Model sources

Replace Brick-centric `model/site.ttl` + Brick class rendering with:

- Hand-authored **Haystack site structure** (TTL or Trio→RDF at build time): site, floors, AHU equips, points.
- Points CSV still freezes `timeseries_id` (A3 stays).
- `bldgts model build` becomes “render Haystack building graph” (CLI name can stay `bldgts` this milestone; rename package later if desired).

### SPARQL

- Still read-only SPARQL over the live graph + loaded defs (as RDF where practical, or model-only if defs stay JSON for suggest).
- Ship new example `.rq` files for Haystack inventory (list AHUs, points with `sensor`, missing markers).
- Old Brick `.rq` examples move under blog Part 1/2 checkpoints only (or `sparql/examples/archive/brick/`).

### CRUD + suggest API

| Endpoint | Role |
|----------|------|
| `GET /api/model/tree` | Site → floor → equip → point; each node has `haystack_markers[]`, `name`, `node_type` |
| `GET /api/model/haystack/defs` | Level-filtered marker catalog |
| `GET /api/model/haystack/suggest?q=&level=` | `difflib.get_close_matches` over defs symbols (+ optional synonyms from def docs) |
| `POST /api/model/rename` | Click-hold rename → `rdfs:label` |
| `POST /api/model/tags` | **Repurposed:** batch set Haystack markers (replace ops status/meta) |
| `POST /api/model/equip\|point\|hide` | Keep shape; create entities with required markers for level |
| `GET /api/model/dashboard` | Tag coverage (by marker / untagged), not received counts |

Remove: `meta-tags`, ops status pills, LATE/DAMAGED catalog.

### UI (`web/`)

- Rebrand copy: Haystack model tagger (smart building IoT), not dock/shipping.
- **Edit mode**
  - **Left click-hold:** rename any node (site/floor/equip/point).
  - **Right-click:** suggest panel — closest Haystack markers for that level; click to stage.
  - **Add tag:** pick from level-filtered catalog.
  - **Save:** batch markers + renames via CRUD (revision gate unchanged).
- Dashboard tab: coverage charts for markers / untagged points.
- SPARQL tab: Haystack example presets.

### Blog / course boundaries

- **Part 1 & Part 2 checkpoints:** unchanged Brick+ops (or Part 2 checkpoint may lag until re-frozen after this ships).
- **New Part (3 or 4):** “Haystack-native API + UI” freeze when green.
- **`lessons/sql`:** untouched; still may mention Brick in week 8 — out of scope.

### Testing

- Unit: `difflib` suggest ranks (`duct static` → expect `duct`/`sensor`/`pressure`-family markers among top N).
- API: rename + marker apply + tree shows markers; reject unknown markers; mutations off → 403.
- UI smoke: edit gestures documented in README.
- Contract: every point still has exactly one timeseries ref + id + storedAt.

### Migration / rollback

- Live `building.ttl` / `model/building_50.ttl` regenerated Haystack-shaped; old Brick TTL kept only under blog checkpoints / git history.
- `BLDGTS_*` env names may remain this milestone (document); optional later rename to `HS_*` / `HAYSTACK_*`.

## Phased delivery (implementation order)

1. **Vendor defs + suggest service** (`difflib`, level filters) + API.
2. **Strip ops tags** from CRUD/UI/dashboard; wire markers + rename.
3. **Haystack model seed + build** replacing Brick classes in live graph; update SPARQL examples.
4. **UI copy/gestures** for full-tree Haystack tagging.
5. **ARCHITECTURE.md** lock updates (A2/A8/A9/A15) + blog Part freeze.
6. Re-freeze Part 2 checkpoint **or** add Part 3 Haystack checkpoint.

## Risks

- Open-FDD FC1 lessons still speak Brick roles — client lessons may need Haystack→role mapping or stay on checkpoint Part 1.
- Large defs file: pin one release; do not scrape HTML tag lists.
- “Delete Brick” must not delete timeseries invariants (opaque id, parameterized SQL, read-only SPARQL).

## Approval

Operator: approve this spec to proceed to an implementation plan and coding.  
Reply **approve** / note deltas (especially: keep `ref:` timeseries triples vs pure Haystack `his` tags).
