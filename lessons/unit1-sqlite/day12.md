# Day 12 — Indexes and `EXPLAIN QUERY PLAN`

**Goal:** see how SQLite finds rows, and add an index where it has to read everything.

## Read

A table without a useful index is a list: to find rows, SQLite **scans** all of them, O(n). An **index** is a B-tree
sorted by some columns. Finding a key or a key range is O(log n), then it walks the matching rows in order.

`samples` is `WITHOUT ROWID` with primary key `(timeseries_id, ts)`, so the table **is** a B-tree sorted by series,
then time. That makes some questions cheap and others not:

| Query filters on | Can use the key? |
|---|---|
| `timeseries_id = ?` | yes, it's the first key column |
| `timeseries_id = ? AND ts BETWEEN ...` | yes, both columns, range on the second |
| `ts BETWEEN ...` alone | **no**: time is only sorted *within* each series, so it must scan |
| `date(ts, 'unixepoch') = ...` | the function hides `ts` from the index |

Prefix `EXPLAIN QUERY PLAN` to any query and SQLite tells you its plan instead of running it. Look for
`SEARCH ... USING PRIMARY KEY` / `USING INDEX` (good) vs `SCAN table` (reads everything).

The tradeoff: every index speeds up some reads, but costs disk space and slows every insert. Historians index exactly
what they're queried by (series + time) and little else.

## Run

```sql
EXPLAIN QUERY PLAN
SELECT * FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
  AND ts >= unixepoch('2026-07-01') AND ts < unixepoch('2026-07-02');
```

`SEARCH samples USING PRIMARY KEY (timeseries_id=? AND ts>? AND ts<?)` jumps straight to 288 rows.

```sql
EXPLAIN QUERY PLAN
SELECT * FROM samples
WHERE ts >= unixepoch('2026-07-01') AND ts < unixepoch('2026-07-02');
```

`SCAN samples`: all 4.2 million rows, to return 33,984. Run both queries without `EXPLAIN` and compare the time DB
Browser reports under the results.

```sql
-- lab_history has no index yet, so even one AHU-day scans
EXPLAIN QUERY PLAN
SELECT * FROM lab_history
WHERE equipment_id = 'AHU_1'
  AND ts >= unixepoch('2026-07-01') AND ts < unixepoch('2026-07-02');
```

```sql
CREATE INDEX IF NOT EXISTS lab_history_equipment_ts ON lab_history (equipment_id, ts);

SELECT count(*) FROM lab_history
WHERE equipment_id = 'AHU_1'
  AND ts >= unixepoch('2026-07-01') AND ts < unixepoch('2026-07-02');
-- expect: 288
```

Run the `EXPLAIN QUERY PLAN` again: `SEARCH lab_history USING INDEX lab_history_equipment_ts`.

## Try it

1. Check the plan for Day 3's "bad" filter, `date(ts, 'unixepoch') = '2026-07-01'`, with a `timeseries_id`. Which
   part of the key does it still use?
2. If dashboards often ask "all points at one moment" (`ts = ?` across every series), what index would help, and what
   would it cost?

<details><summary>Answers</summary>

```sql
EXPLAIN QUERY PLAN
SELECT * FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
  AND date(ts, 'unixepoch') = '2026-07-01';
```

`SEARCH samples USING PRIMARY KEY (timeseries_id=?)`. It finds the series fast, then checks the date on all 35,536
of its rows instead of 288.

2. An index on `samples(ts)` (or `(ts, timeseries_id)`). It would roughly duplicate the key data, around another
   100+ MB here, and slow down every insert. Timescale solves the "by time" access differently: it splits the table
   into time **chunks** (Day 15).

</details>

## Why it matters

The same thinking applies to triple stores (week 5). A graph of `(subject, predicate, object)` triples needs several
sorted indexes (SPO, POS, OSP) because SPARQL queries fix different positions. Which index a query can use is the
whole performance story.
