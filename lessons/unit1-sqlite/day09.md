# Day 9 — Time buckets: hourly and daily averages

**Goal:** collapse 5-minute rows into hourly and daily averages in pandas and SQL: give every row a bucket (the hour
or day it belongs to), then `GROUP BY` the bucket.

## Read

A year of 5-minute data is 105,000 rows per point. A dashboard, a report or a daily-energy number wants hours or
days. **Bucketing** means: give every row a key for "which hour (or day) am I in", then group by that key and
average. Only the key changes; the rest is the grouping you already know.

The key is the timestamp written out as text with only the parts you want: `2026-03-16 00` for the hour,
`2026-03-16` for the day.

| Step | `day09_sql.py` | `day09_pandas.py` |
|---|---|---|
| hour key | `strftime('%Y-%m-%d %H', timestamp_utc)` | `df["time"].dt.strftime("%Y-%m-%d %H")` |
| day key | `strftime('%Y-%m-%d', timestamp_utc)` | `df["time"].dt.strftime("%Y-%m-%d")` |
| average per bucket | `GROUP BY hour` + `AVG(...)` | `df.groupby("hour").agg(...)` |

In pandas the CSV timestamp is text, so `pd.to_datetime` first turns it into a real timestamp (the `.dt` tools need
that). SQLite's `strftime` reads the text directly.

A bucket with few rows is a partial bucket: the record starts at 00:40, so the first hour has only **4 rows**
instead of 12. A rule that needs "12 samples per hour" has to know about partial buckets at the edges. That is why
the scripts keep a `rows` count next to each average.

AHU_1 has 2,962 hourly rows and 124 daily rows. Both scripts group on text, so an hour with no data simply
doesn't appear; Building 50 has no gaps, but a real building will have some.

Other ways to say the same thing (not in the scripts):

- pandas: `df["time"].dt.floor("h")` rounds a timestamp down to its hour and keeps it a real timestamp; and
  `df.set_index("time")["col"].resample("h").mean()` does the bucketing and the average in one call, adding a `NaN`
  row for an hour with no data.
- SQL: `unixepoch(timestamp_utc) / 3600` is the number of hours since 1970. Integer division makes a number that is
  cheap to compare and easy to index; `strftime` makes text that is easy to read.

## Run

```bash
uv run python lessons/course.py run 9
```

That runs [`day09_pandas.py`](day09_pandas.py), then [`day09_sql.py`](day09_sql.py). Both print:

```
Hourly rows: 2962
Daily rows:  124
First hour: 2026-03-16 00 has only 4 rows (a partial hour)
Hottest day: 2026-07-01 at 31.3 C
```

## Try it

1. Which day has the *lowest* mean outside-air temperature? (Sort the other way: `.iloc[0]` in pandas, `ORDER BY
   mean_oa_c LIMIT 1` in SQL.)
2. Change the hourly buckets to half-days in both scripts: before 12:00 and after. What do you change in the key?
3. **View vs summary table (SQL).** Once you have an hourly query there are two ways to keep it: `CREATE VIEW
   hourly_v AS SELECT ...` stores the **query**, so every read re-runs the aggregation (it can't go stale, and costs
   no storage), while `CREATE TABLE hourly_t AS SELECT ...` stores the **result**: computed once, reads are instant,
   but it is a snapshot that must be rebuilt when new rows arrive. Try both and time ten reads of each with
   `time.perf_counter()`: the table is hundreds of times faster. It is the same trade-off as caching anywhere, and
   what Timescale calls a *continuous aggregate*.

<details><summary>Answers</summary>

1. 2026-03-17 at −5.9 °C. The record opens with a flat, stuck-looking reading of 20.6 °C: a reminder to look at the
   data before trusting a mean.
2. Use the first 10 characters plus the AM/PM: in pandas `df["time"].dt.strftime("%Y-%m-%d %p")`, in SQL
   `strftime('%Y-%m-%d %p', ...)` is not available, so use
   `substr(timestamp_utc, 1, 10) || CASE WHEN CAST(strftime('%H', timestamp_utc) AS INTEGER) < 12 THEN ' AM' ELSE ' PM' END`.

</details>

## Why it matters

Hourly and daily summaries are what people read, and what slower rules (daily energy, hours outside setpoint) run on.
Bucketing is also where timezones bite: these buckets are UTC, so a "day" starts in the evening in US time zones.
A report for building staff has to bucket in local time. And the view/table choice is the first taste of a decision
you'll make repeatedly: derive on read, or store once. Day 10 does a different kind of time matching: finding which
fault episode each row falls in.
