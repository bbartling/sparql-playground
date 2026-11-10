# Building data, from CSV to RDF to BACnet — daily mini lessons

A 17-week course of short daily lessons (about 20–30 minutes each, five a week). It's written for someone with an
undergraduate CS degree or the equivalent: you know a programming language, basic data structures and big-O. You
don't need to know buildings, SQL, RDF or BACnet yet.

It uses the same data and code as this repo's API:

- **Building 50**: two air handlers (AHU_1, AHU_2) at a real building, logged every 5 minutes from 2026-03-16 to
  2026-07-17. The historian's exports are in `data/BUILDING_50/AHU_*/history_wide.csv`: one row per timestamp, one
  column per point.
- **Weeks 1–4** work straight from those CSVs: pandas reads them, and SQLite holds the same rows as tables. Fault
  rules name their columns directly (`supply_fan_status`, `da_p_inwc`), the way a first FDD script does.
- **Week 5** is where that stops scaling. A **Haystack**-tagged RDF model (`model/building_50.ttl`) says which point
  is which, every point gets a stable **UUID**, and an **external timeseries reference** says where its history is
  stored (the API's SQLite database `var/timeseries.sqlite`, or a CSV column). The same rule then runs on any
  building, with no column names in the code.
- Later units build up the graph side (triple stores, rdflib, SPARQL, the FastAPI app) and end with **BACnet**: how
  the data gets out of a live building in the first place.

## Setup (once)

1. Install [uv](https://docs.astral.sh/uv/). [DB Browser for SQLite](https://sqlitebrowser.org/dl/) (free) is
   optional: handy for looking at tables, but every lesson runs from Python.
2. In this repo:

   ```bash
   uv sync
   uv run python lessons/course.py setup
   uv run python lessons/course.py doctor
   ```

   `setup` loads the two CSV exports (and Open-FDD's fault events) into `var/lessons.sqlite`, a few seconds. Nothing
   is transformed: same tables as the CSVs, same column names.
3. Before Week 5, build the API's model and database:

   ```bash
   uv run bldgts model build
   uv run bldgts bootstrap
   ```

   `bootstrap` loads the same CSVs into `var/timeseries.sqlite` in the API's long format (one row per point per
   timestamp, keyed by UUID), about 240 MB.

## How the lessons run: two scripts per day

Each day is a lesson (`dayNN.md`) and **two scripts that compute the same thing**:

| Script | Reads | Does the work with |
|---|---|---|
| `dayNN_pandas.py` | the CSV export, into a DataFrame | pandas (and plain Python where the lesson compares loops) |
| `dayNN_sql.py` | the same rows, as SQLite tables | SQL strings run through the standard library's `sqlite3` |

```bash
uv run python lessons/course.py run 14     # Day 14: the pandas script, then the SQL script
```

The scripts are short and plain on purpose: read a CSV or connect to the database, a few numbered steps, print. No
helper modules, nothing hidden. Each script ends by **printing** its answers. Put the two printouts side by side and
compare them: same numbers, computed two different ways. The numbered comments in one script match the other, so you
can read them together.

That's how [Open-FDD](https://github.com/bbartling/open-fdd) keeps its fault rules honest: every SQL rule has a pandas
twin, and its parity tests fail if they disagree on a single row. This course does the same.
`tests/test_lesson_scripts.py` runs both scripts of every day and checks their answers agree
(`uv run pytest -q -m lessons`, or `uv run python lessons/course.py check`; CI runs it).

Fault math is **SI**, like Open-FDD: °C, Pa, and fractions 0–1 for commands. The CSVs are in the units the historian
logged (°F, inH2O, percent); Day 6 shows the conversions and later days use them.

## Syllabus

Printable packs of the written weeks (PDF): [`pdf/`](pdf/README.md). The scripts live next to each lesson in the repo.

Written lessons are linked. The rest of the outline is the plan; those lessons get written as the course goes.

### Unit 1 — FDD on a CSV export, in pandas and SQL (weeks 1–3)

Just enough pandas and SQL to explore a historian export, summarize it and write a fault rule. No server, no
Postgres, no Timescale: CSV files, one SQLite file and Python.

**Week 1: find your way around (read-only)**

| Day | Lesson |
|---|---|
| 1 | [Open the data: a CSV in pandas, the same rows in SQLite; what one row is](unit1-sqlite/day01.md) |
| 2 | [Pick columns and rows: SELECT, WHERE, ORDER BY, LIMIT vs DataFrame indexing](unit1-sqlite/day02.md) |
| 3 | [Time: timestamps, date ranges and time zones](unit1-sqlite/day03.md) |
| 4 | [Summary stats: COUNT, MIN, MAX, AVG, SUM, and run hours](unit1-sqlite/day04.md) |
| 5 | [GROUP BY and HAVING: per day, per month (+ week 1 challenge)](unit1-sqlite/day05.md) |

**Week 2: units, joins and conditions**

| Day | Lesson |
|---|---|
| 6 | [Units: converting to SI (°C, Pa, fractions) for fault math](unit1-sqlite/day06.md) |
| 7 | [Two AHUs: stacking (UNION ALL / concat) and joining on time](unit1-sqlite/day07.md) |
| 8 | [CASE and conditional aggregation: run hours, unoccupied runtime, percent occupied](unit1-sqlite/day08.md) |
| 9 | [Time buckets: hourly and daily averages; views vs summary tables](unit1-sqlite/day09.md) |
| 10 | [Joining Open-FDD's fault events: interval joins (+ week 2 challenge)](unit1-sqlite/day10.md) |

**Week 3: fault detection in SQL and pandas**

| Day | Lesson |
|---|---|
| 11 | [Indexes and `EXPLAIN QUERY PLAN` vs a sorted DataFrame index](unit1-sqlite/day11.md) |
| 12 | [Window functions: LAG, rolling averages, fan starts](unit1-sqlite/day12.md) |
| 13 | [Streaks (gaps and islands): "true for N rows in a row"](unit1-sqlite/day13.md) |
| 14 | [Write a fault rule (FC1, duct static too low) twice, and check it against Open-FDD](unit1-sqlite/day14.md) |
| 15 | [Data quality before you trust a rule: dropouts, stuck sensors, coverage (+ unit challenge)](unit1-sqlite/day15.md) |

### Unit 2 — pandas vs SQL vs plain Python at scale (week 4)

**Week 4: FDD at scale**

The same fault calculations three ways (a Python loop, vectorized pandas, SQLite), on synthetic data that grows 10×
per step: timings, memory, big-O, and when each one wins.

| Day | Lesson |
|---|---|
| 16 | [One answer three ways: loop, pandas, SQL; timings and the hidden cost of moving data](unit2-python/day16.md) |
| 17 | [Memory: `fetchall()` vs streaming vs DataFrames, `tracemalloc`, dtypes, chunked reads](unit2-python/day17.md) |
| 18 | [Gaps and coverage: sample-and-hold with `MAX_GAP_HOURS`, elapsed-time confirmation](unit2-python/day18.md) |
| 19 | [Weather join: as-of joins (`merge_asof` vs an indexed subquery) and a sensor-vs-weather rule](unit2-python/day19.md) |
| 20 | [Scaling showdown: the FC1 streak as a loop, pandas and window SQL (+ week 4 challenge)](unit2-python/day20.md) |

### Unit 3 — From hard-coded columns to a data model (week 5)

**Week 5: Haystack RDF and external timeseries references**

Hard-coded column names work for one building and break on the next. A model says which point is which (Haystack
tags, in RDF), every point gets a stable UUID, and an external reference says where its history lives. Then the rule
finds its own inputs.

| Day | Lesson |
|---|---|
| 21 | [Why hard-coded names break: one AHU's `mad_c` is the other's `mad_c_pct`; a role map as a first model](unit3-modeling/day21.md) |
| 22 | [Haystack tags as RDF: find a rule's inputs by tags with SPARQL, and the flat table that shadows the graph](unit3-modeling/day22.md) |
| 23 | [UUIDs and the long table: stable ids, `samples`, and pivoting long to wide](unit3-modeling/day23.md) |
| 24 | [External timeseries references: one model, history in SQLite or in a CSV](unit3-modeling/day24.md) |
| 25 | [Model-driven FC1 through the app's API, with no ids in the code (+ week 5 challenge)](unit3-modeling/day25.md) |

### Unit 4 — Python data structures and algorithms for graphs (weeks 6–7)

A triple store is "just" hash maps, sets and joins. You build a tiny one yourself before using a library, so rdflib
and SPARQL engines stop being magic.

- **Week 6: build a triple store.**
  - Triples as tuples, and interning strings to integers.
  - Three indexes (SPO, POS, OSP) and why you need all three.
  - Pattern matching with wildcards, and the cost of each access path.
  - Loading `building_50.ttl` into it.
- **Week 7: graph algorithms on the building.**
  - BFS/DFS over `isPartOf` / `feeds`: equipment trees, "everything downstream of AHU_1".
  - Cycles, and transitive closure with memoization.
  - Joining two patterns: nested-loop vs hash join, and choosing join order by selectivity.
  - Heaps for top-k, and sorting.

### Unit 5 — RDF with rdflib (weeks 8–10)

- **Week 8: the data model.**
  - IRIs, literals and datatypes, blank nodes, namespaces.
  - Turtle syntax, and reading `building_50.ttl` line by line.
  - `rdflib.Graph`: add, remove, `triples()`, `value()`, serialization formats.
- **Week 9: vocabularies.**
  - RDFS (`subClassOf`, domain/range), a little OWL.
  - Haystack defs and tags, Brick classes and relationships, and how this repo maps one to the other.
  - The ref schema in depth: `ref:TimeseriesReference`, `ref:hasTimeseriesId`, `ref:storedAt` (Week 5's bridge).
- **Week 10: correctness.**
  - Inference: what it adds and what it costs.
  - SHACL shapes and `bldgts validate --shacl`.
  - Building a model from a point list: `bldgts model build` read end to end.

### Unit 6 — SPARQL and the API (weeks 11–13)

- **Week 11: SPARQL basics.**
  - SELECT, basic graph patterns, FILTER, OPTIONAL, UNION, ORDER/LIMIT.
  - Aggregates, GROUP BY, property paths (`brick:isPartOf+`).
  - Each one compared with the SQL you wrote in Unit 1.
- **Week 12: SPARQL in depth.**
  - Subqueries, VALUES, BIND, CONSTRUCT, ASK.
  - How an engine evaluates a query, using your Unit 4 triple store as the mental model.
  - Read-only guards (`sparql_guard.py`): why the API refuses UPDATE / SERVICE.
- **Week 13: the FastAPI app.**
  - Tour of the app: `/api/sparql`, `/api/points`, timeseries reads through the model.
  - A Python client that finds FC1 points by role with SPARQL and pulls their history by UUID (Day 25, grown up).
  - Running every Unit 1 rule model-driven, on any building.

### Unit 7 — BACnet and modeling live buildings (weeks 14–17)

What goes on under the hood of BACnet, enough to scan a real building safely and model what you find. You don't need
to be a network programmer.

- **Week 14: the BACnet object model.**
  - Devices, objects and properties; present-value, units, status-flags, reliability.
  - Commandable objects and the 16-slot priority array; relinquish-default.
  - Reading Building 50's points as if they were BACnet objects.
- **Week 15: how BACnet moves.**
  - UDP 47808, broadcast Who-Is / I-Am, ReadProperty vs ReadPropertyMultiple, segmentation and max-APDU.
  - BACnet/IP vs MS/TP, routers and network numbers, BBMDs and foreign devices.
  - The bacpypes3 shell (`whois`, `read`) against a bench controller.
- **Week 16: BACnet to RDF.**
  - `bacpypes3.rdf`: devices and objects as IRIs, properties as predicates, priority arrays as RDF lists.
  - The site scanner (`bacnet_site_scan.py`): device facts, command ownership, topology, provenance.
  - SPARQL over a scan: who is commanding what, which overrides are left in.
- **Week 17: modeling the supervisory layer.**
  - Schedules, trend logs, loops and the references between them.
  - Observed vs inferred facts; value-sharing (e.g. one outside-air sensor shared to every AHU).
  - Scanning a live building responsibly: read-only, rate limits, MS/TP, permission.
  - Capstone: scan → RDF → SPARQL → findings a retrofit or RCx engineer could use.

Background for Unit 7:
- [JoelBender/BACpypes3#181](https://github.com/JoelBender/BACpypes3/pull/181) and [#183](https://github.com/JoelBender/BACpypes3/pull/183)
- The [scanner gist](https://gist.github.com/bbartling/5514cbb102cb40ce397d794fd4e094ab)
- This repo's to-do issues: [#2 bacpypes3 RDF](https://github.com/bbartling/sparql-playground/issues/2) and [#3 scanner + modeling](https://github.com/bbartling/sparql-playground/issues/3)

## How each lesson is laid out

- **Goal:** one sentence.
- **Read:** a short explanation, including how pandas and SQL each do the calculation.
- **Run:** `course.py run N`, what each script does step by step, and what the printout should show.
- **Try it:** one or two exercises, with answers folded underneath.
- **Why it matters:** where this shows up later in the course.
