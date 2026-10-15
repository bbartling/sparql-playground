# Day 13 — Make repeated ingest safe in a transaction

[Previous: Day 12](day12.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 14](day14.md)

**Week 2 · 45–75 minutes.** Prerequisites: days 1–12, or equivalent skills.

## Goal

Use a unique key and `ON CONFLICT` to handle a repeated ingest attempt, then roll back a scratch change. Decide whether a repeat should be ignored or treated as a correction.

## Before you start

All writes remain in `student`. Read `\d course.sample` to confirm its logical key, and keep the fixture unchanged. Today's scratch table is deliberately small; it demonstrates ingest behavior without copying all 24,190 observations.

## Concept

An ingest process can retry after a timeout even when the first write succeeded. A key ensures that retrying cannot create a second logical observation. `ON CONFLICT DO NOTHING` keeps the existing row. `DO UPDATE` can replace stored fields, but a correction policy must say which incoming record wins and why.

A transaction groups statements between `BEGIN` and `COMMIT`. `ROLLBACK` discards the transaction's uncommitted changes. A successful statement is not durable until its transaction commits. With ordinary `psql` autocommit enabled, an individual statement runs in its own transaction unless you explicitly start one.

## Tiny example

```sql
CREATE TABLE student.day13_sample (
    site_id text NOT NULL,
    point_id uuid NOT NULL,
    ts timestamptz NOT NULL,
    value double precision,
    quality text NOT NULL CHECK (quality IN ('good','bad','missing')),
    PRIMARY KEY (site_id, point_id, ts)
);

INSERT INTO student.day13_sample (site_id, point_id, ts, value, quality)
SELECT site_id, point_id, ts, value, quality
FROM course.sample
ORDER BY ts, site_id, point_id
LIMIT 1
ON CONFLICT (site_id, point_id, ts) DO NOTHING;
```

Run the insert twice. The scratch table still contains one row. That row's key came from stored fixture identity; it was not invented from an equipment label.

## SQL challenge

Create your own scratch ingest table with the logical observation key and documented null/quality policy. Insert a bounded ten-row fixture excerpt, repeat the same batch, and prove there are still ten rows. State whether your baseline accepts corrections or keeps the first stored value.

Test a correction inside a transaction, using the copied row's key and a visibly synthetic value. Observe it inside the transaction, then roll back and verify the original scratch value returns. Record the before, during, and after results.

## Experiment

In `student.day13_sample`, run `BEGIN;`, change `quality` to `bad`, inspect it, and run `ROLLBACK;`. The table returns to its original quality. What would `COMMIT` have meant? If a statement fails inside a transaction, use `ROLLBACK` before continuing; the failed transaction cannot silently resume normal work.

## Acceptance checks

- A repeated batch creates no duplicate logical rows.
- Your correction experiment changes scratch data temporarily and restores it with rollback.
- You explicitly distinguish retry handling from correction precedence.

## Stretch and reflection

Could a late arriving bad record overwrite a newer good correction under a naive upsert? Describe the extra source/version metadata a real policy needs. Consult [week 2 references](SOURCES.md#week-2) for `INSERT`, conflict handling, and transactions.

[Previous: Day 12](day12.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 14](day14.md)
