# Course validation — 2026-10-15

[Course index](INDEX.md) · [Lab setup](LAB_GUIDE.md) · [Remote setup](REMOTE_SETUP.md)

## Observed local environment

- Linux amd64, PostgreSQL **16.15**, TimescaleDB **2.30.2**.
- Dedicated Compose project `brickts-sql-course`, database `brickts_course`, loopback port 15432.
- Container capped at 768 MiB and 1 CPU. This is a small exercise envelope, not a production sizing result.
- Image digest in the Compose file was available from the registry and used for these checks.

## Executed checks

| Check | Observed result |
| --- | --- |
| Course navigation and page contracts | 84 contiguous daily pages, 12 independent weekly challenges, local links valid |
| Fixture setup run twice | No duplicated identities; counts remain 2 sites / 3 AHUs / 42 points / 24,190 samples |
| Known-answer SQL and negative constraints | 467 observed kWh; fan runtimes 24 / 12 / 12 hours; wrong-site foreign key and nonfinite value rejected |
| Gap-aware teaching pressure condition | North Supply A: 3,000 raw / 1,800 confirmed / 600 unknown seconds; other equipment zero |
| Wrong-database protection, real psql | DDL rejected against `postgres` before creating a course schema |
| Tiny SQL examples, Days 01–56 | All 46 SQL blocks in Tiny example sections executed; isolated changes rolled back |
| Explicit Timescale conversion and aggregate | Fixture remains complete; 2,016 hourly rows; bad power sample yields 11 valid readings and mean 12 kW for its hour |
| Week 10 scratch operations | Four 12-hour chunks; historical correction stale until refresh, then expected corrected mean; columnstore preserves rows; absolute retention boundary leaves 12,096 rows |
| Offline RDF binding checks | All 42 external references match frozen point ids, database, owner, site, role and units |
| Five supplied SPARQL examples | Expected row counts 6 / 3 / 42 / 3 / 14 |
| Graph safety and serialization tests | Remote/update queries rejected; length/row guards and RDF literal/IRI datatypes exercised |
| Repository regressions | Full local suite passed 34 tests before the last two course cases were added; final course module passed all 11 tests |
| Style | Ruff lint and formatting checks passed |

The SQL example harness modeled explicit lesson commits with savepoints to preserve an outer rollback. That check establishes statement behavior, not durability or a two-session concurrency result. Scratch test objects were removed. Main fixture counts remained correct.

The immutable production source target is Open-FDD 3.6.15 at `a45832188ca35ef50987ea73e48c034706a45c86`. Its authored FC1 SQL was also exercised with an explicit synthetic history adapter and declared tuning, including one- and three-row confirmation; this is supplementary source evidence, not production parity qualification. The simplified teaching rule remains a distinct contract.

## Reproduce the committed automated checks

From the full repository root:

```bash
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python lessons/sql/validate_course.py
uv run python lessons/sql/graph_lab.py --check
uv run python lessons/sql/lab.py up
uv run python lessons/sql/lab.py load
uv run python lessons/sql/lab.py load
uv run python lessons/sql/lab.py check
uv run python lessons/sql/lab.py run lessons/sql/sql/10_timescale.sql
uv run python lessons/sql/lab.py run lessons/sql/sql/11_continuous_aggregate.sql
uv run python lessons/sql/lab.py run lessons/sql/sql/12_timescale_assertions.sql
uv run python lessons/sql/lab.py check
```

The `ci` workflow runs the repository checks and a separate real SQL/Timescale job. A page-structure check cannot substitute for executing SQL; a fixture pass cannot establish that every homework implementation is correct. The fixed known answers deliberately fail when the expected data or result contract is absent.

## Not claimed

Remote `mintbench` prerequisites were inspected read-only: Python 3.12.3 and Compose 2.40.3. This course installation and its data were not deployed there during authoring. Remote instructions, password-file generation and backup examples were checked statically; a real remote backup/restore was not tested.

No ARM run, large-server capacity test, full security assessment, real OT scan, all-77-rule qualification or production API/browser validation was performed. Challenges and scale/concurrency assignments remain learner exercises. The original application API/store was preserved; course checks never used application records.
