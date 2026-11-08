# Day 9 — Time buckets: hourly and daily averages, and views vs summary tables

**Goal:** collapse 5-minute rows into hourly and daily summaries in SQL and pandas (what Timescale calls
`time_bucket`), and understand when to store a query (a view) and when to store its result (a summary table).

## Read

A year of 5-minute data is 105,000 rows per point. A dashboard, a report or a daily-energy number wants hours or
days. **Bucketing** means: give every row a key for "which hour (or day) am I in", then `GROUP BY` that key. Only
the key changes; everything else is Day 8's conditional aggregation.

| Bucket | `day09_sql.py` | `day09_pandas.py` |
|---|---|---|
| hour, as text | `strftime('%Y-%m-%d %H', timestamp_utc)` | `ts.dt.strftime("%Y-%m-%d %H")` |
| hour, as an integer | `unixepoch(timestamp_utc) / 3600` | `(ts - epoch).dt.total_seconds() // 3600` |
| hour, as a timestamp | integer bucket `* 3600`, back through `strftime(..., 'unixepoch')` | `ts.dt.floor("h")` |
| day | `strftime('%Y-%m-%d', timestamp_utc)` or `date(timestamp_utc)` | `ts.dt.strftime("%Y-%m-%d")` or `.dt.floor("D")` |
| group + average | `GROUP BY equipment_id, bucket` + `avg(...)` | `groupby(["equipment_id", bucket]).agg(...)` |
| the same, as one call | | `df.set_index("ts").groupby(eq)[col].resample("h").mean()` |

Two things to know:

- **The integer bucket is the portable, fast one.** `unixepoch(ts) / 3600` is integer division (SQLite divides
  integer by integer exactly like this), so the key is a number: cheap to compare, easy to index. `strftime` gives
  readable text. Both find the same buckets, which the scripts' "bucket check" table confirms (2,962 per AHU).
- **`resample` fills empty buckets; `groupby` doesn't.** With `resample("h")` an hour with no data appears as a row
  of `NaN`; with `groupby`/`GROUP BY` it simply isn't there. Building 50 has no gaps, so both agree (5,924 hourly
  rows), but a real building will have some, and you have to choose which behavior you want.

The columns summarize like Day 8: `avg(outside_air_temp_c)` over all rows, `avg(static_running_pa)` over the
rows where
the fan was running (the column is `NULL` while the fan is off, and `avg()` skips `NULL`, like pandas' `mean()` skips
`NaN`), and `avg(supply_fan_status)`, the fraction of the hour the fan was on. A bucket with no running rows has no
mean: `NaN` in pandas, `NULL` in SQL, which the parity test treats as equal.

**View vs summary table.** Once you have an hourly query, there are two ways to keep it:

- `CREATE VIEW hourly_v AS SELECT ...` stores the **query**. Every read re-runs the aggregation over all 71,072 rows.
  It can't go stale, and costs no storage.
- `CREATE TABLE hourly_t AS SELECT ...` stores the **result**: 5,924 rows, computed once. Reads are instant (and can
  be indexed), but the table is a snapshot: new rows in `ahu_1` don't show up until you rebuild it.

This is the same trade-off as caching anywhere: compute-on-read versus compute-once. It's also what Timescale calls a
*continuous aggregate*: a summary table the database keeps fresh for you. The scripts read the summary ten times each
way: about a second for the view, a few milliseconds for the table (pandas shows the same shape: re-running
`groupby` every time vs reusing the DataFrame). The right choice depends on how often the data changes versus how
often it is read; dashboards that read all day over history that rarely changes want a table.

## Run

```bash
uv run python lessons/course.py run 9
```

That runs [`day09_pandas.py`](day09_pandas.py), then [`day09_sql.py`](day09_sql.py). Both print the first rows of the
hourly and daily tables, and one day of hourly outside-air temperature. An excerpt:

```
Hourly averages, first rows (AHU_1):
equipment_id                hour_start  rows  mean_oa_c  mean_static_running_pa  fan_on_fraction
       AHU_1 2026-03-16 00:00:00+00:00     4      20.57                     NaN              0.0
       AHU_1 2026-03-16 01:00:00+00:00    12      19.98                     NaN              0.0
...
hourly rows: 5,924, daily rows: 248
```

(SQL shows a `NULL` as `NaN` too, since pandas prints it.) The first bucket has only **4 rows** because the record
starts
at 00:40: a partial hour. A rule that needs "12 samples per hour" has to know about partial buckets at the edges.

## Try it

1. Which day has the highest mean outside-air temperature on AHU_1, and which the lowest? Change `daily` to find out
   (hint: sort, or `idxmax` / `ORDER BY ... DESC LIMIT 1`).
2. Change the hourly buckets to 15-minute buckets in both scripts. What are the new key expressions, and how many rows
   does AHU_1 get?

<details><summary>Answers</summary>

1. Hottest: 2026-07-01 at 31.3 °C. Coldest: 2026-03-17 at −5.9 °C (the record opens with a flat, stuck-looking reading
   of 20.6 °C, a reminder to look at the data before trusting a mean). SQL: `ORDER BY mean_oa_c DESC LIMIT 1`;
   pandas: `daily.loc[daily.mean_oa_c.idxmax()]`.
2. SQL: `unixepoch(timestamp_utc) / 900` (900 s), turned back with `* 900`. pandas: `ts.dt.floor("15min")`. The
   data is
   5-minute steps, so each bucket has three rows and AHU_1 gets 35,536 / 3 ≈ 11,850 buckets (about 11,846).

</details>

## Why it matters

Hourly and daily summaries are what people read, and what slower rules (daily energy, hours outside setpoint) run on.
Bucketing is also where timezones bite: these buckets are UTC, so a "day" starts in the evening in US time zones.
A report
for building staff has to bucket in local time. And the view/table choice is the first taste of a decision you'll
make repeatedly: derive on read, or materialize once. Day 10 does a different kind of time join: matching each row to
the fault episode it falls in.
