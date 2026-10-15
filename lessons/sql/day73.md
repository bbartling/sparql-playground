# Day 73 — Observe transactions, locks and bounded deadlock recovery

[Previous: Day 72](day72.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 74](day74.md)

**Week 11 · 45–75 minutes.** Prerequisites: Days 1–72, or equivalent SQL skills.

## Goal

Read evidence of a blocked transaction and specify a retry that replays a whole logical operation.

## Before you start

Use exactly two lab sessions and a two-row scratch table. Set five-second statement deadlines and one-second lock deadlines initially. Record session PIDs and keep rollback commands ready. In psql, `\set VERBOSITY verbose` exposes SQLSTATE in error output. Touch only rows you create.

## Concept

Locks protect concurrent changes, but inconsistent acquisition order can form a cycle. PostgreSQL detects a deadlock and aborts one participant with SQLSTATE `40P01`. A lock timeout produces a different failure and can prevent a cycle from lasting until detection. Canceled or failed transactions require rollback. Retrying one final statement can violate the original operation; a bounded retry must replay the whole transaction with idempotency and a consistent ordering policy.

## Tiny example

```sql
CREATE TABLE student.lock_demo (
  id integer PRIMARY KEY, value integer NOT NULL
);
INSERT INTO student.lock_demo VALUES (1, 0), (2, 0);
-- Session A:
BEGIN;
SET LOCAL lock_timeout = '1s';
SET LOCAL statement_timeout = '5s';
UPDATE student.lock_demo SET value = value + 1 WHERE id = 1;
```

While A holds that row, B attempts the same update with its own local deadlines. B should time out. Roll back both sessions before continuing.

## SQL challenge

Capture your sessions’ `pg_stat_activity`, `pg_locks` and `pg_blocking_pids` evidence for a blocked update. Identify holder, waiter, transaction state and wait duration. Then design a two-row operation that always locks IDs in ascending order. Document whole-transaction retry limits and the final expected row values after one successful operation.

## Experiment

Optionally create an opposite-order cycle with the same two rows. Use a five-second statement timeout and a lock timeout long enough to permit deadlock detection. If privileges/settings prevent observing `40P01`, record the timeout actually seen. Never claim deadlock detection from an ordinary lock timeout. Roll back both sessions afterward.

## Acceptance checks

- PIDs and blocking relationships belong to your lab sessions.
- SQLSTATE distinguishes lock timeout, deadlock and cancellation.
- No transaction remains idle while holding a lock.
- A retry policy caps attempts and preserves the declared logical operation.

## Stretch and reflection

How would a transaction identifier or batch ledger help avoid double application after an uncertain commit?

Save your SQL, actual output, and one explanation in `student-work/sql/day73/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-11).

[Previous: Day 72](day72.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 74](day74.md)
