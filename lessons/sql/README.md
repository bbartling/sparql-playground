# SQL and building-data engineering: beginner to confident practitioner

**12 weeks · 84 days · six daily lessons plus one independent weekly challenge.** Start with no database background. Finish able to design, query, test and review a model-driven HVAC time-series/FDD application. This is mostly SQL/database engineering; RDF/SPARQL is the small semantic lookup layer that connects a logical point to its database identity.

[Start: Day 01](day01.md) · [All 84 lessons](INDEX.md) · [Local lab](LAB_GUIDE.md) · [Remote Timescale setup](REMOTE_SETUP.md) · [Primary references](SOURCES.md) · [Production bridge](OPENFDD_BRIDGE.md)

## Your route

| Weeks | Learn by building |
| --- | --- |
| 1–2 | Read SQL confidently; design tables, keys, types and relationships |
| 3–4 | Handle time, windows, joins, transactions, migrations and safe application queries |
| 5–7 | Calculate runtime, energy, comfort and fault confirmation with explicit coverage/units |
| 8 | Query a Brick model and follow external references into exact SQL samples |
| 9–11 | Engineer bounded APIs, query plans, Timescale storage, integrity and honest stress tests |
| 12 | Read actual Open-FDD schemas, 77 rule entries and 18 analytics queries; deliver a reviewed capstone |

Weekday lessons take approximately 45–75 minutes. Challenges take 2–4 hours and can span multiple evenings. These are practice estimates, not deadlines. Keep your own SQL, diagrams, predictions and test evidence in ignored `student-work/sql/`. You are learning how to explain and verify a database, not memorize every keyword.

## First session

From the repository root:

```bash
uv sync --frozen
uv run python lessons/sql/lab.py up
uv run python lessons/sql/lab.py doctor
uv run python lessons/sql/lab.py load
uv run python lessons/sql/lab.py psql
```

At the `brickts_course` prompt:

```sql
SELECT 'I can ask the database a question' AS first_result;
SELECT site_id,label FROM course.site ORDER BY site_id;
```

Exit psql with `\q`, then open Day 01. [LAB_GUIDE](LAB_GUIDE.md) explains what each command does, ordinary errors, the alternate bench-server route, passwords and how to stop your own lab.

The standalone course database is `brickts_course`. Its fixtures are synthetic: 2 sites, 3 AHUs, 42 points and 24,190 samples. Repeated equipment labels, missing readings and a real fault interval make bad joins and false conclusions visible. PostgreSQL does the calculations. Python only launches tools, validates fixtures and demonstrates independent testing.

This new track does not change the existing brickts SQLite tutorial or its API. The original four SPARQL/Python lessons remain available. Production Open-FDD is a read-only study reference; a simplified course fault is explicitly not a full production FC1 implementation. Future students can use their own PostgreSQL server without sharing an application's database.

For installation only, the SQL launcher uses the Python standard library: `python3 lessons/sql/lab.py up` works without installing the application dependencies. The offline graph exercises later use `uv sync --frozen`. See [validation evidence and limits](VALIDATION.md).
