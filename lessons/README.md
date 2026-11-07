# Building data, from SQL to RDF to BACnet — daily mini lessons

A 16-week course of short daily lessons (about 20–30 minutes each, five a week). It's written for someone with an
undergraduate CS degree or the equivalent: you know a programming language, basic data structures and big-O. You
don't need to know buildings, SQL, RDF or BACnet yet.

It uses the same data and code as this repo's API:

- **Building 50**: two air handlers (AHU_1, AHU_2) at a real building, 118 points logged every 5 minutes from
  2026-03-16 to 2026-07-17. That's about 4.2 million readings.
- The API's own **SQLite database** (`var/timeseries.sqlite`) is the database you query in Unit 1.
- The API's **RDF model** (`model/building_50.ttl`) and **SPARQL endpoint** are what you build up to in Units 3–4.
- **BACnet** and the **bacpypes3** RDF scanner come last: how the data gets out of a live building in the first place.

The thread through the whole course: every point has a **UUID**. In SQLite it's the `timeseries_id` of the readings.
In RDF the model says "this sensor's history is stored under that UUID" (`ref:hasTimeseriesId`). Unit 1 makes you
comfortable with the numbers. Units 2–4 teach the graph that tells you which UUID is which sensor.

## Setup (once)

1. Install [uv](https://docs.astral.sh/uv/). [DB Browser for SQLite](https://sqlitebrowser.org/dl/) (free) is
   optional: handy for looking at tables, but every lesson runs from Python.
2. In this repo:

   ```bash
   uv sync
   uv run bldgts model build
   uv run bldgts bootstrap
   uv run python lessons/course.py doctor
   ```

   `bootstrap` loads the Building 50 CSVs into `var/timeseries.sqlite` (about 240 MB, a minute or two). `doctor`
   should print `4,193,248 samples, 118 series`.

## How the lessons run: SQL and pandas, side by side

Every lesson is driven from Python. Each computation is done **twice**:

- as **SQL**, a SQLite string run through the standard library's `sqlite3` (the database does the work), and
- as **pandas**, the same answer computed on a DataFrame (Python does the work),

and then `lab.assert_parity(pandas_result, sql_result)` checks the two agree row for row. That's how
[Open-FDD](https://github.com/bbartling/open-fdd) keeps its fault rules honest: every SQL rule has a pandas twin,
and its parity tests fail if they disagree on a single row. Along the way the lessons compare the two (and plain
Python loops) the way a CS course would: big-O, what an index buys, memory, and timings on growing data.

```bash
uv run python lessons/course.py run 14      # run Day 14's code (on a temporary copy of the database)
uv run python lessons/course.py extract 14  # print Day 14's code as one script, to paste into a notebook
uv run python lessons/course.py check       # run every lesson; all parity checks must pass (CI runs this)
```

A lesson's code is its ```` ```python ```` blocks, top to bottom. Paste them into a Python REPL or a Jupyter
notebook, or let `course.py run` do it. `run` and `check` work on a throwaway copy of the database, so lessons never
change `var/timeseries.sqlite`. Shared helpers (connecting, the parity check, the SI `history` table, synthetic data,
timing) live in [`lab.py`](lab.py).

Fault math is **SI**, like Open-FDD: °C, Pa, and fractions 0–1 for commands. Weeks 1–2 explore the raw database in
the units the historian logged (°F, inH2O, percent); from Day 11 on, rules read an SI `history` table.

## Syllabus

Printable packs of the written weeks (PDF): [`pdf/`](pdf/README.md).

Written lessons are linked. The rest of the outline is the plan; those lessons get written as the course goes.

### Unit 1 — SQL and pandas on real building data (SQLite, weeks 1–3)

Just enough SQL to explore a historian, summarize it and write a fault rule, with the same computation in pandas next
to every query. No server, no Postgres, no Timescale: one SQLite file and Python.

**Week 1: find your way around (read-only)**

| Day | Lesson |
|---|---|
| 1 | [Open the database; what one row is](unit1-sqlite/day01.md) |
| 2 | [SELECT, WHERE, ORDER BY, LIMIT on one sensor; what the UUIDs are](unit1-sqlite/day02.md) |
| 3 | [Time: epoch seconds, `datetime()`, date ranges](unit1-sqlite/day03.md) |
| 4 | [Summary stats: COUNT, MIN, MAX, AVG, SUM](unit1-sqlite/day04.md) |
| 5 | [GROUP BY and HAVING: per day, per month, per series (+ week 1 challenge)](unit1-sqlite/day05.md) |

**Week 2: lookups, joins and conditions**

| Day | Lesson |
|---|---|
| 6 | [A point list table (`lab_point`) and why it's a stand-in for the RDF model](unit1-sqlite/day06.md) |
| 7 | [JOIN: readings by role and equipment instead of UUID](unit1-sqlite/day07.md) |
| 8 | [Self-joins: static pressure *while the fan is running*](unit1-sqlite/day08.md) |
| 9 | [CASE and conditional aggregation: run hours, percent occupied](unit1-sqlite/day09.md) |
| 10 | [Time buckets and views: hourly averages (what Timescale's `time_bucket` does) (+ week 2 challenge)](unit1-sqlite/day10.md) |

**Week 3: fault detection in SQL and pandas**

| Day | Lesson |
|---|---|
| 11 | [Long to wide: the `history` table every Open-FDD rule reads](unit1-sqlite/day11.md) |
| 12 | [Indexes and `EXPLAIN QUERY PLAN`](unit1-sqlite/day12.md) |
| 13 | [Window functions: LAG, rolling averages, streaks](unit1-sqlite/day13.md) |
| 14 | [Write a fault rule (FC1, duct static too low) and check it against Open-FDD](unit1-sqlite/day14.md) |
| 15 | [What production does differently (Timescale), and the UUID bridge to RDF (+ unit challenge)](unit1-sqlite/day15.md) |

### Unit 2 — Python data structures and algorithms for graphs (weeks 4–6)

A triple store is "just" hash maps, sets and joins. You build a tiny one yourself before using a library, so rdflib
and SPARQL engines stop being magic.

**Week 4: pandas vs SQL vs plain Python: FDD at scale**

The same fault calculations three ways (a Python loop, vectorized pandas, SQLite), on synthetic data that grows 10×
per step: timings, memory, big-O, and when each one wins. Every result is checked three ways for parity.

| Day | Lesson |
|---|---|
| 16 | [One answer three ways: loop, pandas, SQL; timings and the hidden cost of moving data](unit2-python/day16.md) |
| 17 | [Memory: `fetchall()` vs streaming vs DataFrames, `tracemalloc`, dtypes, chunked reads](unit2-python/day17.md) |
| 18 | [Gaps and coverage: sample-and-hold with `MAX_GAP_HOURS`, elapsed-time confirmation](unit2-python/day18.md) |
| 19 | [Weather join: as-of joins (`merge_asof` vs an indexed subquery) and a sensor-vs-weather rule](unit2-python/day19.md) |
| 20 | [Scaling showdown: the FC1 streak as a loop, pandas and window SQL (+ week 4 challenge)](unit2-python/day20.md) |

- **Week 5: build a triple store.**
  - Triples as tuples, and interning strings to integers.
  - Three indexes (SPO, POS, OSP) and why you need all three.
  - Pattern matching with wildcards, and the cost of each access path.
  - Loading `building_50.ttl` into it.
- **Week 6: graph algorithms on the building.**
  - BFS/DFS over `isPartOf` / `feeds`: equipment trees, "everything downstream of AHU_1".
  - Cycles, and transitive closure with memoization.
  - Joining two patterns: nested-loop vs hash join, and choosing join order by selectivity.
  - Heaps for top-k, and sorting.

### Unit 3 — RDF with rdflib (weeks 7–9)

- **Week 7: the data model.**
  - IRIs, literals and datatypes, blank nodes, namespaces.
  - Turtle syntax, and reading `building_50.ttl` line by line.
  - `rdflib.Graph`: add, remove, `triples()`, `value()`, serialization formats.
- **Week 8: vocabularies.**
  - RDFS (`subClassOf`, domain/range), a little OWL.
  - Brick classes and relationships, Haystack tags, and how this repo maps one to the other.
  - The ref schema: `ref:TimeseriesReference`, `ref:hasTimeseriesId`, `ref:storedAt` (the UUID bridge from Unit 1).
- **Week 9: correctness.**
  - Inference: what it adds and what it costs.
  - SHACL shapes and `bldgts validate --shacl`.
  - Building a model from a point list: `bldgts model build` read end to end.

### Unit 4 — SPARQL and the API (weeks 10–12)

- **Week 10: SPARQL basics.**
  - SELECT, basic graph patterns, FILTER, OPTIONAL, UNION, ORDER/LIMIT.
  - Aggregates, GROUP BY, property paths (`brick:isPartOf+`).
  - Each one compared with the SQL you wrote in Unit 1.
- **Week 11: SPARQL in depth.**
  - Subqueries, VALUES, BIND, CONSTRUCT, ASK.
  - How an engine evaluates a query, using your Unit 2 triple store as the mental model.
  - Read-only guards (`sparql_guard.py`): why the API refuses UPDATE / SERVICE.
- **Week 12: the FastAPI app.**
  - Tour of the app: `/api/sparql`, `/api/points`, timeseries reads through the model.
  - A Python client that finds FC1 points by role with SPARQL and pulls their history by UUID.
  - Running the Unit 1 fault rule model-driven, with no hard-coded UUIDs.

### Unit 5 — BACnet and modeling live buildings (weeks 13–16)

What goes on under the hood of BACnet, enough to scan a real building safely and model what you find. You don't need
to be a network programmer.

- **Week 13: the BACnet object model.**
  - Devices, objects and properties; present-value, units, status-flags, reliability.
  - Commandable objects and the 16-slot priority array; relinquish-default.
  - Reading Building 50's points as if they were BACnet objects.
- **Week 14: how BACnet moves.**
  - UDP 47808, broadcast Who-Is / I-Am, ReadProperty vs ReadPropertyMultiple, segmentation and max-APDU.
  - BACnet/IP vs MS/TP, routers and network numbers, BBMDs and foreign devices.
  - The bacpypes3 shell (`whois`, `read`) against a bench controller.
- **Week 15: BACnet to RDF.**
  - `bacpypes3.rdf`: devices and objects as IRIs, properties as predicates, priority arrays as RDF lists.
  - The site scanner (`bacnet_site_scan.py`): device facts, command ownership, topology, provenance.
  - SPARQL over a scan: who is commanding what, which overrides are left in.
- **Week 16: modeling the supervisory layer.**
  - Schedules, trend logs, loops and the references between them.
  - Observed vs inferred facts; value-sharing (e.g. one outside-air sensor shared to every AHU).
  - Scanning a live building responsibly: read-only, rate limits, MS/TP, permission.
  - Capstone: scan → RDF → SPARQL → findings a retrofit or RCx engineer could use.

Background for Unit 5:
- [JoelBender/BACpypes3#181](https://github.com/JoelBender/BACpypes3/pull/181) and [#183](https://github.com/JoelBender/BACpypes3/pull/183)
- The [scanner gist](https://gist.github.com/bbartling/5514cbb102cb40ce397d794fd4e094ab)
- This repo's to-do issues: [#2 bacpypes3 RDF](https://github.com/bbartling/sparql-playground/issues/2) and [#3 scanner + modeling](https://github.com/bbartling/sparql-playground/issues/3)

## How each lesson is laid out

- **Goal:** one sentence.
- **Read:** a short explanation, including how pandas and SQL each do the calculation.
- **Run:** Python blocks: the SQL string, the pandas version, and `lab.assert_parity`. `assert` lines state the
  answers you should see; `course.py check` runs them all.
- **Try it:** one or two exercises, with runnable answers folded underneath.
- **Why it matters:** where this shows up later in the course.
