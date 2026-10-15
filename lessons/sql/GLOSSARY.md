# Plain-language database glossary

[Course index](INDEX.md) · [Schema picture](SCHEMA.md)

| Word | Meaning in this course |
| --- | --- |
| Server | The running PostgreSQL process that manages data and executes queries. |
| Client | A program such as psql that sends requests to a server. |
| Database | A named collection of schemas and objects managed by the server. Use `brickts_course` here. |
| Schema | A namespace such as `course` or `student` inside a database. |
| Table / row / column | A relation, one record at its declared grain, and one named attribute. |
| Grain | Exactly what one row represents: for example, one point at one timestamp. |
| Type | A value's declared kind: text, integer, UUID, timestamp, numeric, and so on. |
| Primary key | Columns that uniquely and non-nullably identify a row. |
| Foreign key | A constraint requiring a referenced identity to exist. |
| Composite key | A key containing more than one column; all components matter. |
| Constraint | A rule PostgreSQL checks before accepting a change. |
| NULL | Missing or unknown information, not automatically zero, false, or an empty string. |
| JOIN | Combining related rows using an explicit matching condition. |
| Aggregate | Collapsing a population to a summary such as count, sum or average. |
| GROUP BY | Defining the groups over which an aggregate is calculated. |
| CTE / WITH | A named intermediate query expression, useful for organizing a calculation. |
| Window function | A calculation across related rows that preserves the individual rows. |
| Transaction | A group of changes that succeeds together or rolls back. |
| Parameter | A bound data value kept separate from the SQL program. |
| Migration | A versioned, reviewable change to database structure or data conventions. |
| Index | An additional data structure that can accelerate selected access patterns, at a write/storage cost. |
| Query plan | The server's chosen operations for executing a query. |
| EXPLAIN ANALYZE | Executes the statement and reports measured plan behavior; it is not read-only for a write statement. |
| MVCC | PostgreSQL's versioned-row approach to concurrent readers and writers. |
| Isolation | Rules governing what concurrent transactions can observe. |
| Role | A database identity or permission group; unlike a measurement role such as `kw`. |
| RLS | Row-level security policies; understand owner and superuser bypass before claiming isolation. |
| Replay / idempotence | Repeating the same operation without accidentally duplicating logical observations. |
| Half-open window | An interval including its start and excluding its end: `[start,end)`. |
| Coverage | How much of the requested time or population has usable evidence. |
| Runtime | Observed operating duration under a declared status and gap policy. |
| kW / kWh | Power / energy. Integrate power over hours to calculate energy. |
| Hypertable | A Timescale table whose rows are partitioned into time chunks behind one SQL interface. |
| Continuous aggregate | A Timescale-managed summary with explicit refresh and freshness behavior. |
| Pool | A limited set of reusable database connections, not unlimited parallel capacity. |
| Backpressure | Slowing or refusing new work when a bounded queue or resource budget is full. |
| RDF triple | A subject, predicate and object describing a statement about the model. |
| IRI | A globally named graph resource; a URI-looking string literal is still a literal. |
| Brick | The building vocabulary used in this playground's semantic model. |
| SPARQL | A query language for RDF graphs; SQL remains the sample-calculation language here. |
| External reference | The graph link from a logical point to its time-series id and database. |
| AFDD | Automated fault detection and diagnostics: calculations plus scope, applicability, evidence and operating policy. |
| Oracle | An independent expected answer used in testing, not the same implementation called twice. |

The daily lessons explain these words in context. You do not need to memorize this table before starting.
