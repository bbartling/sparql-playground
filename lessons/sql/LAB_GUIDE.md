# Lab guide

[Course index](INDEX.md) · [Start Day 01](day01.md)

## What runs where

A database server stores rows, checks constraints and executes SQL. `psql` is a client that sends SQL and displays results. Python's `lab.py` is a short launcher so you need not install a separate psql client for the default route. Open the file to see the expanded Docker/psql commands; no scientific calculation is hidden there.

The existing brickts API continues to use its locked SQLite stand-in. This course adds an independent PostgreSQL/Timescale service, **not** a new application adapter. Its database and Compose project are separate from any application on your machine or bench. `course` holds reproducible fixtures; `student` is your scratch schema. A schema is a namespace inside a database, not a different server.

## Route A — isolated lab on this computer

Install Docker with Compose and uv if absent using their official instructions. From repository root:

```bash
uv sync --frozen
uv run python lessons/sql/lab.py up
uv run python lessons/sql/lab.py doctor
uv run python lessons/sql/lab.py load
uv run python lessons/sql/lab.py psql
```

The helper starts only Compose project `brickts-sql-course`, on loopback port 15432, with a 768 MiB memory cap and 1 CPU. It generates a course-only password at `var/sql-course/password`, permissions 0600, already ignored by Git. Do not commit it or share resolved Compose configuration. Existing application containers, data volumes and ports are not stopped or repurposed.

The image digest in compose.yaml was registry-verified and used with PostgreSQL 16.15 / TimescaleDB 2.30.2 on Linux amd64. `COURSE_IMAGE` and `COURSE_PORT` can explicitly override the lab image/host port. Record actual versions, and check architecture support before choosing another image. A small course cap is an exercise envelope, not a production server sizing recommendation.

To understand the shortcut, the psql part expands to:

```bash
docker compose -p brickts-sql-course -f lessons/sql/compose.yaml exec db \
  psql -X -U learner -d brickts_course -v ON_ERROR_STOP=1
```

The Docker-only `learner` account administers this disposable lab. A real application uses separate restricted ingestion, query and migration roles. Week 4 explains that distinction.

Useful commands:

```bash
uv run python lessons/sql/lab.py run lessons/sql/sql/02_explore.sql
uv run python lessons/sql/lab.py check
uv run python lessons/sql/lab.py run student-work/sql/my_query.sql
uv run python lessons/sql/lab.py down
```

`down` stops only the course project and retains its volume. `load` creates missing fixture tables and inserts missing fixture identities; it does not drop schemas or overwrite existing learner edits. If you changed seeded rows, the assertion check may fail: inspect your transaction and restore your own known edits deliberately. Keep work in student tables/views or use rollback for experiments. There is no automatic destructive reset command.

## Route B — existing PostgreSQL/Timescale server on the bench

For a full installation walkthrough on a **separate remote lab instance**, including SSH tunneling and a backup exercise, use [REMOTE_SETUP](REMOTE_SETUP.md). That is the preferred remote beginner route; the DBA route below is optional.

Your bench can host a **new, dedicated** `brickts_course` database. The helper does not create databases on an existing server, edit its authentication, read its environment or attach to an application database. Ask the server owner/DBA to create the course database and role. In an authorized administrator psql session, an example is:

```sql
CREATE ROLE course_learner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
\password course_learner
CREATE DATABASE brickts_course OWNER course_learner;
\connect brickts_course
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

`\password` prompts instead of putting a password into SQL history. If names already exist, stop and inspect ownership; never drop or overwrite another database to fit the example. Only the DBA installs extensions. Nothing in the ordinary course requires changing the shared server's global configuration.

The current bench at 192.168.204.16 is reachable with SSH alias `mintbench`. Keep this as a local connection choice, not a dependency embedded in queries. For example, keep this tunnel running in its own terminal:

```bash
ssh -N -L 15433:127.0.0.1:5432 mintbench
```

Confirm the remote server actually listens on remote loopback port 5432 before using this optional DBA route; use its authorized port otherwise. The separate remote Docker route uses 15432 instead.

In another terminal, install a PostgreSQL client if needed and set:

```bash
export COURSE_MODE=native
export PGHOST=127.0.0.1 PGPORT=15433 PGUSER=course_learner PGDATABASE=brickts_course
# Configure a private ~/.pgpass / PGPASSFILE entry with chmod600, or use psql's prompt.
uv run python lessons/sql/lab.py doctor
uv run python lessons/sql/lab.py load
```

Never paste credentials or DSNs into Git, Turtle, screenshots or shared transcripts. Native mode uses libpq connection settings and checks the database name before running course files. `up/down` are refused in native mode. The helper's standard 15-second statement and 3-second lock timeouts are a starting teaching envelope; observe and explain any deliberate session override. Tutorial guards cannot stop a privileged person intentionally running unrelated SQL manually.

## First psql skills

| Command | Meaning |
| --- | --- |
| `\conninfo` | Show which server/database this client reached |
| `\dt course.*` | List course tables |
| `\d course.sample` | Inspect columns, keys and constraints |
| `\timing on` | Time statements |
| `\x auto` | Choose expanded display for wide rows |
| `\i path.sql` | Execute a file visible to the psql client; in Docker that means inside the container |
| `\q` | Exit psql |

Use `lab.py run student-work/sql/example.sql` for SQL files saved on the host. The helper streams the file to the container; a container psql session cannot see arbitrary host paths.

`SELECT` is SQL sent to the server. Backslash commands belong to the psql client. A semicolon ends a SQL statement; `\r` clears an unfinished input buffer. If a transaction errors, `ROLLBACK;` ends its failed state. Read the error before retrying.

## Data and engineering conventions

See [CONTRACT](CONTRACT.md) for every table, role, unit and exact fixture count. All timestamps are timestamptz with explicit UTC boundaries. Queries use half-open windows `[start,end)`. Temperature is degC, pressure Pa, power kW, energy kWh; fan_status is 0/1. Good/non-null coverage is different from healthy operation. A missing fault mask is unknown, never fabricated zero.

A valid fixture sample represents at most 300 seconds. Do not bridge arbitrary gaps or multiply an irregular row count by a guessed cadence. Units and the denominator belong beside every result. Duplicate labels are intentional; resolve a point's frozen UUID from metadata. Fixture names may appear in teaching examples, never as a general application's classification logic.

## Daily evidence and weekly rubric

Before running a query, write what you expect and its row grain. Save source SQL, relevant output, parameters/window, observed tool versions, and one failure you can explain. Label work `observed`, `fixture-only` or `not run`. Keep files in `student-work/sql/dayNN/`.

For each weekly challenge score 0–2 on correctness, scope/identity, units/time/coverage, bounded work and reproducibility: 0 missing, 1 partial, 2 demonstrated. Aim for at least 8/10 with no false success or cross-site result. Revisit a missing criterion instead of redefining completion. Weekly pages deliberately have no worked implementation.

## Common errors

- Connection refused: check the course container/tunnel and port, not random application settings.
- Database guard rejects the connection: inspect PGDATABASE; never remove the guard to target another DB.
- Relation does not exist: run load in the course database, then inspect schema qualification.
- Column must appear in GROUP BY: decide the intended output grain.
- Empty aggregate/null: inspect input eligibility and window; do not replace unknown with 0 casually.
- Permission denied: distinguish database/schema/table rights and ask the owner; don't grant yourself global admin.
- Query canceled: inspect its plan, window and workload before raising a timeout or RAM limit.

## Optional Timescale and graph labs

Week 10 can create a scratch hypertable as its lessons describe. The explicit companion `sql/10_timescale.sql` instead converts only course.sample inside the guarded lab; `sql/11_continuous_aggregate.sql` creates student.hourly_point without automatic retention/refresh policies. Run `sql/12_timescale_assertions.sql` afterward to verify actual hourly counts and quality handling. Read the SQL first, then run it deliberately. Normal load/check remain plain PostgreSQL-compatible.

```bash
uv run python lessons/sql/graph_lab.py --check
uv run python lessons/sql/graph_lab.py lessons/sql/sparql/day50_triples.rq
```

The graph CLI is offline SELECT/ASK over synthetic metadata. It validates external references against fixture identities, not a live DB. It does not install a graph server, fetch a remote ontology or expose new application endpoints. Week 8 connects its opaque result ids to parameterized SQL. Existing Swagger examples remain in the original tutorial.

The offline graph CLI caps query length and returned rows. Those limits do not establish a hard CPU or memory budget for arbitrary SPARQL expressions; use the supplied small graph and trusted exercises.
