# Day 3 — Time: epoch seconds, `datetime()`, date ranges

**Goal:** turn `ts` into readable dates, and select a day or a month.

## Read

`ts` is **Unix epoch seconds**: seconds since 1970-01-01 00:00:00 UTC. `1773621600` is 2026-03-16 00:40 UTC.
Historians store time like this because integers sort fast, compare exactly and have no time zone ambiguity.
Everything in this database is **UTC**.

SQLite's date functions read epoch seconds when you add the `'unixepoch'` modifier:

| Function | Result for `1773621600` |
|---|---|
| `datetime(ts, 'unixepoch')` | `2026-03-16 00:40:00` |
| `date(ts, 'unixepoch')` | `2026-03-16` |
| `strftime('%H', ts, 'unixepoch')` | `00` (hour) |
| `strftime('%w', ts, 'unixepoch')` | `1` (day of week, 0 = Sunday) |
| `unixepoch('2026-07-01')` | `1782864000` (text → epoch seconds) |

To select a time range, compare `ts` to epoch numbers. Write the range **half-open**, `start <= ts < end`, so
consecutive days never share a reading.

Don't filter with `date(ts, 'unixepoch') = '2026-07-01'`. It gives the same rows, but SQLite has to compute a date
for every row instead of jumping to the range. Day 12 shows the difference.

## Run

```sql
SELECT datetime(ts, 'unixepoch') AS time_utc, value
FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
ORDER BY ts
LIMIT 3;
-- expect: 2026-03-16 00:40:00 | 69.0327
```

```sql
-- First and last timestamp in the whole database
SELECT datetime(min(ts), 'unixepoch'), datetime(max(ts), 'unixepoch') FROM samples;
-- expect: 2026-03-16 00:40:00 | 2026-07-17 09:55:00
```

```sql
-- All outside air readings on 1 July 2026 (UTC)
SELECT count(*)
FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
  AND ts >= unixepoch('2026-07-01')
  AND ts <  unixepoch('2026-07-02');
-- expect: 288
```

288 = 24 hours × 12 readings an hour: a full day of 5-minute data.

## Try it

1. When was the hottest outside air reading, as a date and time?
2. How many readings does the first day, 2026-03-16, have, and why isn't it 288?

<details><summary>Answers</summary>

```sql
SELECT datetime(ts, 'unixepoch'), value FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
ORDER BY value DESC LIMIT 1;
-- expect: 2026-07-14 21:40:00 | 98.8608
```

```sql
SELECT count(*) FROM samples
WHERE timeseries_id = 'bf422925-1e2d-598d-9069-3b0f17d49c48'
  AND ts >= unixepoch('2026-03-16') AND ts < unixepoch('2026-03-17');
-- expect: 280
```

The data starts at 00:40, not midnight, so the first eight readings of that day were never logged.

</details>

## Why it matters

Building people think in local time ("the fan should start at 6 am"). Databases should store UTC. Converting at the
edges, and noticing when a "6 am start" shows up at 11:00 UTC, is a daily skill. The RDF model will record the site's
time zone so code doesn't have to guess.
