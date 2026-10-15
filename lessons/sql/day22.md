# Day 22 — Observe commits, rollbacks, and a competing writer

[Previous: Day 21](day21.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 23](day23.md)

**Week 4 · 45–75 minutes.** Prerequisites: days 1–21, or equivalent skills.

## Goal

Observe transaction visibility from two clients and explain why concurrent writes need coordination. Keep every experiment confined to one scratch row with a short lock timeout.

## Before you start

Open two terminals, each connected to the same `brickts_course` database through the lab helper. Label them A and B in your notes. Confirm both connections with `\conninfo`. Do not run this exercise on an application database or shared operational table.

## Concept

A transaction's uncommitted changes are visible to that transaction but ordinarily not to another session. PostgreSQL's usual default isolation level, Read Committed, gives each statement a view of committed data as it begins. A competing update can wait for another writer's row lock.

An atomic expression such as `value = value + 1` lets the database perform an increment against the row it updates. Reading a value into a client and later assigning a computed constant can overwrite another writer's work unless the design adds a suitable concurrency strategy. Rollback removes uncommitted changes and releases locks; disconnecting an unfinished session also aborts its open transaction.

## Tiny example

In A, create a one-row scratch table outside an explicit transaction:

```sql
CREATE TABLE student.day22_counter (
    counter_id integer PRIMARY KEY CHECK (counter_id = 1),
    value integer NOT NULL
);
INSERT INTO student.day22_counter (counter_id, value) VALUES (1, 0);
BEGIN;
UPDATE student.day22_counter SET value = value + 1 WHERE counter_id = 1;
SELECT value FROM student.day22_counter WHERE counter_id = 1;
```

A sees `1`. Before A commits, B's plain `SELECT` sees `0`. In A, run `ROLLBACK;`; both sessions then see `0`.

## SQL challenge

Repeat the increment and commit it instead. Verify both sessions see `1` after commit. Record a small timeline containing the statement, session, transaction state, and observed value.

Test contention: while A holds an uncommitted update, start a transaction in B, run `SET LOCAL lock_timeout = '2s';`, then attempt an update of the same row. Record the timeout, run `ROLLBACK;` in B, and finish A with rollback. Every open transaction must be closed before you leave.

## Experiment

Run `SHOW transaction_isolation;`. Explain your observed visibility using that result rather than assuming all isolation levels behave alike. Compare the atomic increment with two clients independently reading `1` and later assigning `2`; predict the lost-update risk without implementing a larger race.

## Acceptance checks

- Uncommitted and committed visibility have distinct recorded evidence.
- The competing write stops within the declared timeout, and both clients recover.
- The scratch counter ends at a known committed value with no transaction left open.

## Stretch and reflection

Read [week 4 references](SOURCES.md#week-4) about isolation and explicit locking. When might `SELECT ... FOR UPDATE` be useful, and what extra waiting behavior would it introduce? Keep your answer conceptual until a bounded test is designed.

[Previous: Day 21](day21.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 23](day23.md)
