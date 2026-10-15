# Course fixture and authoring contract

This is a standalone educational SQL lab. It does not replace brickts' SQLite adapter or change its public API. PostgreSQL16 with TimescaleDB 2.30.2 is the validated baseline; exact server/extension versions are recorded by the lab checks. Use only the dedicated database `brickts_course`. Never load course DDL into an application database.

## Stable schema used by every lesson

- `course.site(site_id text PRIMARY KEY, label text, tz text)` — two synthetic sites, `SYN-NORTH` and `SYN-SOUTH`.
- `course.equipment(equipment_id uuid PRIMARY KEY, site_id text, label text, kind text)` — three AHUs, two at north and one at south. Label is not identity. Composite FK/unique keys enforce site ownership.
- `course.point(point_id uuid PRIMARY KEY, site_id text, equipment_id uuid, role text, unit text)` — frozen opaque UUIDs; one point per equipment/role in the starter fixture. Duplicate same-role sensors in later exercises require an explicit selection policy, not first-row selection.
- `course.sample(site_id text, point_id uuid, ts timestamptz, value double precision NULL, quality text)` — long table, key `(site_id,point_id,ts)`, quality `good|bad|missing`; finite values only. Only good, non-null values are eligible for calculations unless a lesson explicitly analyzes quality.
- `course.lab_meta(singleton boolean PRIMARY KEY, schema_version integer, purpose text)` — ownership sentinel, not an application table.
- `student` — scratch schema in this same disposable course database. Learners create their own tables/views here; main fixtures remain available.
- `course.history` — view joining sample -> point -> equipment and carrying site_id. Columns: `site_id, equipment_id, equipment_label, equipment_kind, point_id, role, unit, ts, value, quality`.
- `course.ahu_5m` — teaching pivot grouped by site/equipment/instant; columns `site_id,equipment_id,equipment_label,ts` plus all 14 numeric role columns below. Bad/null source samples stay null. This pivot does not resample or fill gaps.

Roles/units: `duct_static` Pa, `duct_static_sp` Pa, `fan_status` bool encoded 0/1, `fan_speed_pct` %, `kw` kW, `sat`/`sat_sp`/`rat`/`oat`/`mat`/`zone_temp`/`zone_temp_sp` degC, `damper_pct` %, `cooling_pct` %.

These are teaching role names, not an assertion they are the current Open-FDD canonical catalog. The final bridge teaches the explicit role/unit/SQL-input adapter.

## Deterministic fixture

Start inclusive `2026-01-05T00:00:00Z`, end exclusive `2026-01-07T00:00:00Z`, five-minute cadence, 3 AHUs, 14 points each. North equipment labels `Supply A` and `Supply B`; south also uses `Supply A`. Retrieve UUIDs from metadata, never derive runtime identity from labels.

Supply A north: fan on 06:00–18:00 UTC each day, 12 kW on / 0 off; low-pressure fault 100 Pa vs 250 Pa setpoint on Jan5 08:00–09:00UTC. Otherwise static 260 Pa while on. Supply B north fan on 10:00–16:00 UTC, 6 kW; south fan on 22:00–04:00 UTC, 9 kW. SAT 13 degC except Supply B north Jan5 12:00–13:00UTC is 20 degC. Zone 22 degC except Supply A north Jan5 14:00–15:00UTC is 28 degC, setpoint 22 degC. Comfort teaching band 20–24 degC, inclusive.

Two duct_static samples are absent for Supply A north Jan5 08:25 and 08:30 UTC. Its kw at Jan5 15:10UTC is null/bad. A duplicate ingest attempt must not create a second logical row. Fixed equipment/point UUIDs are generated once in fixture generation and stored in SQL/Turtle, never inferred by query clients. Expected counts: 2 sites, 3 equipment, 42 points, 24,190 samples (3*14*576 minus 2); 1 bad/null value.

For cadence examples, a good sample can represent at most 300 seconds, clipped to the requested half-open window. Never bridge an arbitrarily long gap. Distinguish scheduled run hours, observed status-based hours, valid coverage and unknown intervals. Any alternative duration/confirmation convention must be declared and tested.

## Lesson format and ownership

12 weeks,84daily Markdown files `day01.md`…`day84.md`. Days divisible by 7 are independent weekly challenges: brief, acceptance criteria, deliverables, review questions; no worked solution or step-by-step implementation. Ordinary days use Goal, Before you start, Concept, Tiny example, SQL challenge, Experiment, Acceptance checks, Stretch and reflection, navigation. Aim 45–75 minutes weekdays, 2–4 hours for weekly challenges; learner may split sessions.

Use concrete self-contained examples, deterministic expected observations and exercises that differ from the tiny demonstration. SQL examples use qualified tables. Never assume a quoted string is an SQL identifier. Explain the relational grain and units before formulas. Plain PostgreSQL examples must not depend on Timescale until week 10. No giant histories, unbounded stress, changes to shared servers, real credentials, private project names or real OT controls.

Commands (from repository root): `uv run python lessons/sql/lab.py up`, `... load`, `... psql`, `... run lessons/sql/sql/02_explore.sql`, `... check`; the helper uses a dedicated local course Compose project by default. For an existing bench server use the documented native psql/SSH-tunnel route after a DBA creates an empty brickts_course database. `up` never attaches to the existing application container. Week 8 graph queries run with `uv run python lessons/sql/graph_lab.py <file.rq>`; this resolves metadata, not samples. `graph_lab.py --check` verifies each model point's external reference against SQL fixture identity without needing live application data.

Sources and lab setup live in `SOURCES.md` and `LAB_GUIDE.md`. Public Open-FDD is a read-only production-study reference, pinned in `OPENFDD_BRIDGE.md`; no local path is required to follow web links. Distinguish this repo's Brick profile from Open-FDD Haystack and its extensions. Do not silently claim they are one ontology or present a simplified lesson predicate as the complete production FC1 algorithm.
