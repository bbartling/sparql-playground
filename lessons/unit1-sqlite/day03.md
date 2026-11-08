# Day 3 — Time: ISO timestamps, date functions, ranges, local time

**Goal:** turn `timestamp_utc` into dates and date parts, select a day, and know where each tool's time handling bites.

## Read

`timestamp_utc` is **ISO 8601 text**: `2026-03-16 00:40:00+00:00` is year-month-day, a space, hour:minute:second, and a
UTC offset (`+00:00` means UTC). Historians store UTC because it has no daylight saving jumps and sorts the same way
as the clock.

Because every value has the same fixed-width format, **sorting the text is sorting by time**. That is why Day 2's
range query worked on raw text. But text is still text: to get *parts* of the date (the hour, the weekday, the month)
or to do arithmetic, you need real date handling:

- **pandas** parses once: `df["time"] = pd.to_datetime(df["timestamp_utc"], utc=True)` gives a datetime column
  (`datetime64[ns, UTC]`) with the whole `.dt` toolbox.
- **SQLite** has no date type at all. `datetime()`, `date()`, `strftime()` and `unixepoch()` read the text and compute
  on it **row by row**, every time you call them.

How the two line up for `2026-03-16 00:40:00+00:00`:

| SQL (on the text column) | pandas (`t = pd.to_datetime(..., utc=True)`) | Result |
|---|---|---|
| `datetime(timestamp_utc)` | `t.dt.strftime("%Y-%m-%d %H:%M:%S")` | `2026-03-16 00:40:00` (offset dropped) |
| `date(timestamp_utc)` | `t.dt.strftime("%Y-%m-%d")` | `2026-03-16` |
| `strftime('%H', timestamp_utc)` | `t.dt.hour` | `00` (text in SQL, int in pandas) |
| `strftime('%w', timestamp_utc)` | `(t.dt.dayofweek + 1) % 7` | `1` (a Monday) |
| `unixepoch(timestamp_utc)` | `(t - epoch).dt.total_seconds()` | `1773621600` |

`unixepoch` is **Unix epoch seconds**: seconds since 1970-01-01 00:00:00 UTC. Subtracting two of them gives seconds
between readings, which is how the scripts check there are no gaps: 5-minute steps from the first to the last
reading need `span_s / 300 + 1 = 35,536` rows, and there are exactly that many.

**Weekday gotcha.** SQLite's `%w` counts **Sunday = 0** and returns **text**; pandas' `dayofweek` counts **Monday = 0**
and returns an integer. 2026-03-16 was a Monday: 1 in SQL, 0 in pandas. The pandas script converts with
`(dayofweek + 1) % 7` before comparing, and the SQL script wraps `%w` in `CAST(... AS INTEGER)`.

**Date ranges: half-open.** To select a day, write `start <= time < end` with `end` = the next midnight. Consecutive
days then never share a reading, and "the day" needs no thought about 23:59:59.999. Closed ranges (`BETWEEN`, `<=`) are
where off-by-one days come from. They also bite on short text: `BETWEEN '2026-07-01' AND '2026-07-01'` returns **zero**
rows, because `'2026-07-01 00:00:00+00:00'` sorts *after* `'2026-07-01'` (a longer string with the same start is
greater). The scripts build bounds as full timestamps, `2026-07-01 00:00:00+00:00`, which in pandas is simply
`str(pd.Timestamp("2026-07-01", tz="UTC"))`.

**Don't filter with a function of the column.** `WHERE date(timestamp_utc) = '2026-07-01'` returns the same 288 rows
as the range, but SQLite has to compute a date for every row instead of seeking. The range form lets it use the
index: a B-tree seek, O(log n + k). The function form is a scan, O(n). The plans, printed by the SQL script:

```
SEARCH ahu_1 USING COVERING INDEX sqlite_autoindex_ahu_1_1 (timestamp_utc>? AND timestamp_utc<?)
SCAN ahu_1 USING COVERING INDEX sqlite_autoindex_ahu_1_1
```

(Both read the index, since it holds the whole key; `SEARCH` jumps to the range, `SCAN` walks all of it.) The pandas
twin of the mistake is formatting the whole column as strings just to compare dates, which is a Python-level pass
over every row; comparing the datetime column to two bounds is one vectorized comparison. With 35,000 rows both are
instant; with a month of 1-second data from a thousand points the difference is minutes.

**Time zones.** Store UTC, convert at the edges. pandas converts to a named zone, daylight saving included:
`t.dt.tz_convert("America/Chicago")`. SQLite has only `'localtime'`, the zone of **whatever machine runs the query**,
so the same query gives different answers on different computers. That is a reason to keep zone conversion in pandas
or application code. Building 50 is in the Central zone. Its data (March to July) is all daylight saving time, UTC−5;
the spring change was 8 March, before the data starts, and the autumn one is in November, after it ends.

## Run

```bash
uv run python lessons/course.py run 3
```

That runs [`day03_pandas.py`](day03_pandas.py), then [`day03_sql.py`](day03_sql.py). Both print:

```
first three readings, as dates and epoch seconds:
           time_utc    epoch_s  outside_air_temp_f
2026-03-16 00:40:00 1773621600             69.0327
...
first and last timestamp:
          first_utc            last_utc
2026-03-16 00:40:00 2026-07-17 09:55:00
rows if every 5-minute step is present: 35536
rows actually there:                    35536

readings on 2026-07-01 (half-open range): 288
readings on 2026-03-16 (data starts at 00:40): 280
same day via a computed date on every row: 288
BETWEEN '2026-07-01' AND '2026-07-01' on text: 0 (the day's rows all sort after it)

weekday of the first row (0 = Sunday, as SQL counts): 1
the hottest reading, UTC: 2026-07-14 21:40:00 98.86
```

288 = 24 hours × 12 readings an hour: a full day of 5-minute data. The first day, 2026-03-16, has 280, because the data
starts at 00:40, not midnight, so eight readings never logged.

After the shared results each script adds its own tail, because they differ:

- pandas converts to local time: `2026-07-14 16:40:00-05:00` for the hottest reading, and the fan's first start on
  2026-04-01 was `09:00 UTC` = **04:00 local**. It also shows pandas refusing to compare a timezone-naive column
  with an aware timestamp (`TypeError: Invalid comparison...`), the classic pandas time bug. That error is the friendly
  outcome: the unfriendly one is a library that silently compares and is off by five hours. Pass `utc=True` when you
  parse, and build bounds with `tz="UTC"`.
- SQL prints its query plans and `datetime(..., 'localtime')`, which gives the right answer on a machine set to Central
  time and a different one anywhere else.

## Try it

1. When was the hottest reading in `America/Chicago` time, and is that a plausible hour for a hot day?
2. How many readings does June 2026 have, as a half-open range? Why would `<= '2026-06-30'` be wrong?
3. When did the fan first start on 2026-06-04, in UTC and in local time? (Copy the fan-start step; change the dates.)

<details><summary>Answers</summary>

1. 16:40 (4:40 pm) local on 14 July, `21:40 UTC` minus five hours. Mid-afternoon is when the outdoor temperature peaks,
   so yes. (pandas only: `hot_time.tz_convert("America/Chicago")`.)
2. 8,640 (30 days × 288), with `timestamp_utc >= '2026-06-01 00:00:00+00:00' AND timestamp_utc < '2026-07-01
   00:00:00+00:00'`. `<= '2026-06-30'` compares the *text*, and every reading on the 30th (`2026-06-30 00:05:00+00:00`
   and so on) sorts after `'2026-06-30'`, so the whole last day would be missing.
3. 09:05 UTC, which is 04:05 local (UTC−5). On both mornings checked the fan starts around 4 am local: an early start
   (a warm-up or cool-down before occupancy?), the kind of thing you only see once you read the time in local terms.

</details>

## Why it matters

Building people think in local time ("the fan should start at 6 am"). Databases should store UTC. Converting at
the edges and noticing what a UTC timestamp is in local time is a daily skill: a schedule fault looks like a
five-hour mistake if you forget. The half-open range and the "never wrap the indexed column in a function" rules are the two habits from today
that you will use in every later week.
