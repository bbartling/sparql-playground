# Day 58 — Page history with a stable cursor

[Previous: Day 57](day57.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 59](day59.md)

**Week 9 · 45–75 minutes.** Prerequisites: Days 1–57, or equivalent SQL skills.

## Goal

Design keyset pagination that preserves ties, site scope and a fixed history window.

## Before you start

Retrieve point UUIDs through metadata. Keep a fixed half-open window in every page. Work in SQL or a request-contract document; no application UI is needed.

## Concept

For one point, `(site_id, point_id, ts)` makes timestamp unique. Across points, timestamp needs a UUID tie breaker. A cursor must carry the ordering tuple and bind to the original site, selected points, range and model revision. Treat it as opaque validated input at an API boundary. Keyset pagination avoids walking a growing offset, but concurrent inserts before the cursor can still change what a multi-request reader sees. Declare snapshot/export semantics or document that behavior.

## Tiny example

```sql
WITH events(ts, event_id) AS (
  VALUES ('2026-01-05 08:00Z'::timestamptz, 1),
         ('2026-01-05 08:00Z'::timestamptz, 2),
         ('2026-01-05 08:05Z'::timestamptz, 3)
)
SELECT * FROM events
WHERE (ts, event_id) > ('2026-01-05 08:00Z'::timestamptz, 1)
ORDER BY ts, event_id LIMIT 2;
```

Both remaining events appear. Filtering only `ts > cursor_time` would lose event 2.

## SQL challenge

Write a prepared query that pages north Supply A duct static history over January 5, 08:00–09:00 UTC, with page size four. Its resolved point has ten rows because two instants are absent. Return a next cursor only when another row exists; fetching at most page size plus one can establish this. Then describe the ordering needed for a two-point endpoint.

## Experiment

In a scratch copy, add an earlier row between pages and a later row inside the window. Record which each pagination contract sees. Compare offset and keyset behavior; do not label either a complete snapshot without evidence.

## Acceptance checks

- Concatenated pages contain ten distinct source rows in increasing order.
- Changing site, point set or window invalidates a cursor.
- Empty and final pages terminate without repeating the last row.
- A declared maximum page size and maximum time range constrain requests independently.

## Stretch and reflection

How would a data revision or immutable export identifier make a long download reproducible?

Save your SQL, actual output, and one explanation in `student-work/sql/day58/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-9).

[Previous: Day 57](day57.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 59](day59.md)
