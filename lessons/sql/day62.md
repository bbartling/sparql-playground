# Day 62 — Budget a bounded history workload

[Previous: Day 61](day61.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 63](day63.md)

**Week 9 · 45–75 minutes.** Prerequisites: Days 1–61, or equivalent SQL skills.

## Goal

Turn query limits into a measurable workload budget across raw history, aggregates and response serialization.

## Before you start

Keep the test at two clients, forty requests total and the two-day fixture. Set a stop condition of ten seconds per request and a small total deadline. Use SQL transcripts or an optional local driver; no HTTP server is required.

## Concept

A history request has several costs: identity resolution, connection wait, SQL execution, result transfer and encoding. Selecting fewer columns reduces transfer, while aggregation must still scan eligible input rows unless a suitable summary exists. Limits on points, window, page size and concurrency describe different bounds. For a one-point day at five-minute cadence, the expected maximum is 288 source rows. Unknown coverage and a valid empty result need distinct reporting.

## Tiny example

```sql
SELECT pg_catalog.pg_column_size(ROW(ts, value, quality)) AS tuple_bytes
FROM course.sample
WHERE site_id = 'SYN-NORTH'
  AND ts >= '2026-01-05 00:00Z'::timestamptz
  AND ts < '2026-01-06 00:00Z'::timestamptz
ORDER BY point_id, ts LIMIT 3;
```

This measures PostgreSQL’s representation of a sample row, not JSON bytes, protocol overhead or total process memory. Use actual encoded payload size when you make a claim about the wire.

## SQL challenge

Prepare three bounded query shapes: a one-point raw hour, a one-point day, and one equipment’s hourly kW summary. Include time predicates before aggregation, explicit quality policy and deterministic ordering. Record request parameters, rows returned, eligible source count, execution time and encoded response bytes where measured. Compare one client with two; state pool and queue settings from day60.

## Experiment

Repeat a warm query and then change its point/window. Explain why the second request does not necessarily share the same cache conditions. Compare a three-column payload with a redundant joined history payload for the same rows. Do not fetch the entire database merely to discard rows in a client.

## Acceptance checks

- Every query is scoped by site and a finite time range.
- Raw one-point day responses never exceed 288 fixture rows.
- No missing sample is converted into measured zero.
- A compact table contains actual counts and timings, plus unavailable measurements labeled as such.
- The run stops at the declared bounds even after errors.

## Stretch and reflection

Which budget would need to change before adding twenty points to one plot? Justify each change with data.

Save your SQL, actual output, and one explanation in `student-work/sql/day62/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-9).

[Previous: Day 61](day61.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 63](day63.md)
