# Day 60 — Bound database concurrency and prove cancellation

[Previous: Day 59](day59.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 61](day61.md)

**Week 9 · 45–75 minutes.** Prerequisites: Days 1–59, or equivalent SQL skills.

## Goal

Show that a request deadline actually cancels database work and leaves its connection reusable.

## Before you start

Use only your dedicated lab database and at most two sessions. Choose a five-second maximum experiment and identify each session’s PID yourself. Never cancel a PID copied from somebody else’s activity listing.

## Concept

A connection pool limits concurrent sessions; a request queue also needs a bound and a wait deadline. Otherwise overload merely moves into the queue. A client giving up does not by itself prove that its SQL stopped. PostgreSQL `statement_timeout` cancels server work. A canceled statement in an explicit transaction leaves the transaction aborted until rollback. Pools must clean up failed transactions before handing a connection to another request. A useful record separates queue wait, query time and serialization time.

## Tiny example

Run interactively so you can recover after the intentional error. In psql, set `\set VERBOSITY verbose` first to display SQLSTATE:

```sql
BEGIN;
SET LOCAL statement_timeout = '200ms';
SELECT pg_catalog.pg_sleep(2);
-- Expected SQLSTATE 57014; issue the following after the error:
ROLLBACK;
SELECT 1 AS connection_reusable;
```

The delay is bounded even if the timeout setting fails. `SET LOCAL` lasts only for its transaction.

## SQL challenge

Specify a two-connection pool, a bounded waiting queue and distinct acquisition/query deadlines for the day59 contract. Demonstrate a timeout, rollback and successful next query. In a second session, observe your first session with `pg_stat_activity`; capture PID, state, wait event and query age without logging credentials or private query text. Explain how the driver propagates cancellation when a caller disconnects.

## Experiment

Compare the server timeout above with interrupting a two-second delay from the client. Observe whether the backend stops work and whether the transaction requires rollback. If you cannot inspect activity, mark that evidence unavailable rather than declaring cancellation verified.

## Acceptance checks

- SQLSTATE and elapsed time document actual server cancellation.
- The same session successfully executes a query after cleanup.
- Pool capacity, queue capacity and both deadlines are explicit.
- Your activity observation distinguishes waiting from executing.

## Stretch and reflection

When would `lock_timeout` expose a blocked query sooner than the statement deadline? Keep all settings local to this lab.

Save your SQL, actual output, and one explanation in `student-work/sql/day60/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-9).

[Previous: Day 59](day59.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 61](day61.md)
