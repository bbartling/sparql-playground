# Day 23 — Bind query values with SQL PREPARE

[Previous: Day 22](day22.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 24](day24.md)

**Week 4 · 45–75 minutes.** Prerequisites: days 1–22, or equivalent skills.

## Goal

Separate query structure from supplied values using PostgreSQL's SQL-level prepared statements. No Python client or application framework is required today.

## Before you start

Connect to the course database in a fresh `psql` session. Recall that single quotes mark text values and that point identity is a stored UUID. The prepared statements in this lesson exist only in your current session.

## Concept

A parameter is a value supplied to a query whose structure is already specified. `PREPARE` declares parameter types and uses placeholders such as `$1`. `EXECUTE` supplies values for those positions. This keeps input text in the value position, rather than asking a program to concatenate it into SQL syntax.

Parameters stand for values, not table names, column names, or arbitrary ordering clauses. An application that genuinely needs dynamic identifiers must select from an explicit allowlist and use the database driver's identifier mechanisms. Driver parameter APIs have their own placeholder syntax; today's SQL syntax teaches the boundary without assuming a particular language.

## Tiny example

```sql
PREPARE day23_equipment (text) AS
SELECT equipment_id, site_id, label, kind
FROM course.equipment
WHERE site_id = $1
ORDER BY equipment_id;

EXECUTE day23_equipment ('SYN-NORTH');
EXECUTE day23_equipment ('SYN-SOUTH');
```

The executions return two and one equipment rows respectively. The query structure stays the same while the site value changes. Use `DEALLOCATE day23_equipment;` when you finish or simply close the session.

## SQL challenge

Prepare a bounded sample-read statement accepting a site ID, point UUID, start instant, and end instant. Use an explicit half-open window, show timestamp/value/quality, and order by time. Include a fixed small result limit for inspection. Retrieve the chosen point UUID from metadata and record its site, role, and unit separately; never derive a UUID from a label.

Execute the statement for two adjacent windows of that same point. Compare each result to the equivalent literal query. State what should happen for a correctly typed but nonexistent point UUID and for a malformed UUID value.

## Experiment

Before deallocating the example, run:

```sql
EXECUTE day23_equipment ('SYN-NORTH'' OR true --');
```

It returns zero rows because the entire argument is one unmatched site value. The embedded apostrophe is escaped in the SQL literal. Explain why the characters are data here. Do not test by building an unsafe string-concatenation client.

## Acceptance checks

- Prepared inventory results contain 2 northern and 1 southern rows.
- The sample query binds four typed values and retains the quality and time-window policy.
- Suspicious input remains a value, and your explanation distinguishes value parameters from identifiers.

## Stretch and reflection

Inspect `pg_prepared_statements` in the current session. What disappears when the session ends? Read [week 4 references](SOURCES.md#week-4) for prepared statements and your eventual driver's parameter interface.

[Previous: Day 22](day22.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 24](day24.md)
