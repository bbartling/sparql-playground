# Day 61 — Make ingest retries idempotent

[Previous: Day 60](day60.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 62](day62.md)

**Week 9 · 45–75 minutes.** Prerequisites: Days 1–60, or equivalent SQL skills.

## Goal

Define a retry policy that survives duplicate batches and partial failure without hiding contradictory measurements.

## Before you start

Use a new scratch table in `student`. Do not modify the fixture or stop a database container. Simulate errors with transactions and a disconnected lab client.

## Concept

The logical sample key is `(site_id, point_id, ts)`. A unique constraint makes duplicates detectable. `ON CONFLICT DO NOTHING` can make identical retries harmless, but also silently retain an old value when a later batch disagrees. A correction policy must declare whether updates are permitted, which source wins and how changes are audited. Batch identity and sample identity answer different questions. A transaction commits an entire declared batch or none of it; losing the connection after commit leaves the client uncertain and requires safe replay.

## Tiny example

```sql
CREATE TABLE student.retry_demo (
  site_id text NOT NULL, point_id uuid NOT NULL,
  ts timestamptz NOT NULL, value double precision,
  PRIMARY KEY (site_id, point_id, ts)
);
INSERT INTO student.retry_demo
SELECT site_id, point_id, ts, value FROM course.sample
ORDER BY site_id, point_id, ts LIMIT 3
ON CONFLICT DO NOTHING;
```

Run the insert again. The count remains three. This only proves duplicate-key behavior for this chosen policy.

## SQL challenge

Design a scratch ingest ledger and a transaction for a twelve-row, single-point batch. A repeated identical batch must create no new logical samples; a changed value for an existing key must be rejected or recorded as an explicit revision. Include source quality and finite-value validation. Demonstrate rollback when the last row violates a constraint, then replay the valid batch.

## Experiment

Disconnect a client after a small commit, reconnect and replay the same batch. Separately attempt a connection to an unused local port with a short connection timeout to represent unavailability. Record bounded retries and backoff in a design note. Do not claim to have reproduced every network failure mode.

## Acceptance checks

- Two identical submissions produce twelve logical rows.
- One invalid row prevents partial batch visibility.
- A conflicting value has an observable, declared outcome.
- The outage path stops after a bounded retry budget and preserves the batch for later replay.

## Stretch and reflection

Which evidence distinguishes “not committed” from “commit acknowledgment lost”?

Save your SQL, actual output, and one explanation in `student-work/sql/day61/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-9).

[Previous: Day 60](day60.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 62](day62.md)
