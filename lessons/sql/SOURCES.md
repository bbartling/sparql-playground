# Primary reading, by week

Use the lesson first, then the linked reference for precise behavior. Sources are official project documentation and the pinned Open-FDD source; explanations and synthetic exercises here are original. Accessed 2026-10-15. PostgreSQL examples target 16; Timescale examples record 2.30.2 rather than assume all versions share one API. Documentation URLs can redirect as projects evolve.

## Week 1

- [PostgreSQL tutorial](https://www.postgresql.org/docs/16/tutorial.html)
- [psql](https://www.postgresql.org/docs/16/app-psql.html)
- [SELECT](https://www.postgresql.org/docs/16/sql-select.html)
- [Comparison and NULL](https://www.postgresql.org/docs/16/functions-comparison.html)
- [Aggregate functions](https://www.postgresql.org/docs/16/functions-aggregate.html)

## Week 2

- [Data definition](https://www.postgresql.org/docs/16/ddl.html)
- [Constraints](https://www.postgresql.org/docs/16/ddl-constraints.html)
- [Table expressions and joins](https://www.postgresql.org/docs/16/queries-table-expressions.html)
- [INSERT and conflict handling](https://www.postgresql.org/docs/16/sql-insert.html)

## Week 3

- [Date/time types](https://www.postgresql.org/docs/16/datatype-datetime.html)
- [Date/time functions](https://www.postgresql.org/docs/16/functions-datetime.html)
- [Window functions tutorial](https://www.postgresql.org/docs/16/tutorial-window.html)
- [Window function details](https://www.postgresql.org/docs/16/functions-window.html)
- [WITH](https://www.postgresql.org/docs/16/queries-with.html)

## Week 4

- [Transactions](https://www.postgresql.org/docs/16/tutorial-transactions.html)
- [Isolation](https://www.postgresql.org/docs/16/transaction-iso.html)
- [PREPARE](https://www.postgresql.org/docs/16/sql-prepare.html)
- [Roles](https://www.postgresql.org/docs/16/user-manag.html)
- [Row security](https://www.postgresql.org/docs/16/ddl-rowsecurity.html)
- [ALTER TABLE](https://www.postgresql.org/docs/16/sql-altertable.html)

## Week 5

- [Date/time functions](https://www.postgresql.org/docs/16/functions-datetime.html)
- [Aggregate functions](https://www.postgresql.org/docs/16/functions-aggregate.html)
- [Window function frames](https://www.postgresql.org/docs/16/sql-expressions.html#SYNTAX-WINDOW-FUNCTIONS)
- [Open-FDD source navigation](OPENFDD_BRIDGE.md)

## Week 6

- [Conditional expressions](https://www.postgresql.org/docs/16/functions-conditional.html)
- [Statistical aggregates](https://www.postgresql.org/docs/16/functions-aggregate.html)
- [Materialized views](https://www.postgresql.org/docs/16/rules-materializedviews.html)
- [Versioned analytics source](OPENFDD_BRIDGE.md#analytics-reading-map)

## Week 7

- [Window functions](https://www.postgresql.org/docs/16/functions-window.html)
- [SQL Boolean logic](https://www.postgresql.org/docs/16/functions-logical.html)
- [Open-FDD FC1 and runtime sources](OPENFDD_BRIDGE.md#rule-reading-map)
- [SQL expression syntax](https://www.postgresql.org/docs/16/sql-expressions.html)

## Week 8

- [Brick core concepts](https://docs.brickschema.org/brick/relationships.html)
- [Brick external timeseries references](https://docs.brickschema.org/metadata/timeseries-storage.html)
- [W3C SPARQL query language](https://www.w3.org/TR/sparql11-query/)
- [Typed SPARQL JSON results](https://www.w3.org/TR/sparql11-results-json/)
- [Haystack RDF mapping](https://project-haystack.org/doc/docHaystack/Rdf)

## Week 9

- [Using EXPLAIN](https://www.postgresql.org/docs/16/using-explain.html)
- [Multicolumn indexes](https://www.postgresql.org/docs/16/indexes-multicolumn.html)
- [LIMIT/OFFSET](https://www.postgresql.org/docs/16/queries-limit.html)
- [Resource settings](https://www.postgresql.org/docs/16/runtime-config-resource.html)
- [Statement and lock timeouts](https://www.postgresql.org/docs/16/runtime-config-client.html)

## Week 10

- [Timescale hypertables](https://www.tigerdata.com/docs/reference/timescaledb/hypertables/create_table)
- [Timescale generalized create_hypertable](https://www.tigerdata.com/docs/reference/timescaledb/hypertables/create_hypertable)
- [Continuous aggregate refresh](https://www.tigerdata.com/docs/build/continuous-aggregates/refresh-policies)
- [Columnstore policy](https://www.tigerdata.com/docs/reference/timescaledb/hypercore/add_columnstore_policy)
- [Pinned 2.30.2 policy SQL definitions](https://github.com/timescale/timescaledb/blob/2.30.2/sql/policy_api.sql)
- [PostgreSQL resource configuration](https://www.postgresql.org/docs/16/runtime-config-resource.html)

## Week 11

- [PL/pgSQL assertions/errors](https://www.postgresql.org/docs/16/plpgsql-errors-and-messages.html)
- [Database locks](https://www.postgresql.org/docs/16/explicit-locking.html)
- [Monitoring statistics](https://www.postgresql.org/docs/16/monitoring-stats.html)
- [pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html)
- [COPY](https://www.postgresql.org/docs/16/sql-copy.html)

## Week 12

- [Pinned Open-FDD production source map](OPENFDD_BRIDGE.md)
- [Generated 77 rule/18 analytics inventory](openfdd_inventory.json)
- [PostgreSQL CREATE FUNCTION](https://www.postgresql.org/docs/16/sql-createfunction.html)
- [PostgreSQL testing concepts](https://www.postgresql.org/docs/16/regress.html)

References explain mechanisms, not engineering acceptance of an actual building. Do not copy copyrighted standards text or claim a synthetic pass proves calibrated savings, real device compatibility or production security.
