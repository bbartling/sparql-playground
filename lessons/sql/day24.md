# Day 24 — Change a schema with a reviewable migration

[Previous: Day 23](day23.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 25](day25.md)

**Week 4 · 45–75 minutes.** Prerequisites: days 1–23, or equivalent skills.

## Goal

Write a small scratch migration with preconditions, a bounded backfill, and postconditions. Separate the meaning of existing data from defaults for future writes.

## Before you start

Create only `student` objects. A migration is a saved, ordered change to a schema, often accompanied by data changes. Today's exercise uses a few scratch rows; it does not migrate the course fixture or an application database.

## Concept

Adding a required column to existing data needs a policy for those existing rows. A default describes what happens when a future insert omits a value. It does not prove a historical fact. A backfill assigns values to existing rows under a declared rule. Fabricating observation timestamps or measured values to satisfy a constraint would misrepresent evidence.

A migration should name its starting assumption and desired final state. PostgreSQL can transact many DDL changes, so a small migration can be tested and rolled back as a unit. Schema changes acquire locks and may affect other clients; a successful tiny lab is not evidence of safe timing on a large shared table. A rollout also needs to consider old and new writers.

## Tiny example

```sql
CREATE TABLE student.day24_batch (
    batch_id text PRIMARY KEY,
    source_label text NOT NULL
);
INSERT INTO student.day24_batch (batch_id, source_label)
VALUES ('practice-batch-1', 'synthetic excerpt');

BEGIN;
ALTER TABLE student.day24_batch ADD COLUMN review_state text;
UPDATE student.day24_batch
SET review_state = 'pending'
WHERE review_state IS NULL;
ALTER TABLE student.day24_batch
    ALTER COLUMN review_state SET DEFAULT 'pending',
    ALTER COLUMN review_state SET NOT NULL;
ALTER TABLE student.day24_batch
    ADD CONSTRAINT day24_review_state_check
    CHECK (review_state IN ('pending', 'reviewed'));
COMMIT;
```

One row remains, now pending review. That value is a declared workflow policy, not an inferred historical measurement.

## SQL challenge

Design your own two-row scratch metadata table and a migration adding a required review flag or state. Document why the chosen backfill is truthful. Save the original DDL, migration, precondition queries, and postcondition queries separately so another learner can review them.

Verify unchanged row count and identities, complete backfill, accepted future default behavior, and rejection of an invalid state. Include a short note about how an old writer that omits the new column behaves.

## Experiment

On a fresh scratch table, rehearse a similar migration inside `BEGIN` and inspect the changed definition before running `ROLLBACK`. Confirm both schema and data return to the starting state. Explain why rollback testing is easiest before other code begins relying on the new shape.

## Acceptance checks

- Your migration has explicit starting and ending contracts.
- Existing identities and row count survive, and no measurement facts are invented.
- Backfill behavior, future defaults, invalid input, and rollback have separate evidence.

## Stretch and reflection

What makes re-running a migration different from retrying one ingest batch? Describe how a migration ledger could prevent accidental repeat execution. Read [week 4 references](SOURCES.md#week-4) for `ALTER TABLE`, defaults, transactions, and locks.

[Previous: Day 23](day23.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 25](day25.md)
