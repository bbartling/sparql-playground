# Day 11 — Indexes and EXPLAIN QUERY PLAN: why some lookups are instant and others scan everything

**Goal:** read a database's query plan, see the difference between a seek and a scan, build an index and measure
what it buys, then do the same three ways in pandas (mask, `.loc` on a sorted index, binary search).

## Read

Every query has two parts: *what* you want and *how* the engine finds it. SQL only states the *what*. The *how* is
the **query plan**, and SQLite shows it if you put `EXPLAIN QUERY PLAN` in front of the statement. Two words matter:

- **SEARCH**: the engine used an index (a B-tree) to jump to the matching rows. About O(log n) to find the first
  match, plus O(k) to read the k rows that match.
- **SCAN**: the engine read every row and tested each one. O(n), every time you ask.

FDD means asking the same kinds of questions over and over: "everything in March", "everything where static is
high". Whether those are seeks or scans decides if a rule over a few years of data takes milliseconds or minutes.

Today's two questions, both on AHU_1's 35,536 rows:

1. **A time range:** one week of rows (1 to 8 May). `timestamp_utc` is the real table's `PRIMARY KEY`, so SQLite
   already keeps a B-tree sorted on it. To see the difference an index makes, the SQL script works on a `TEMP` copy
   of the table (so the lessons database is not changed). A copy has no primary key and no index, so the plan says
   `SCAN copy`: test every row. Then the script runs `CREATE INDEX` on the copy's `timestamp_utc`, and the plan flips
   to `SEARCH copy USING INDEX copy_time (timestamp_utc>? AND timestamp_utc<?)`. (The timestamps are text in one
   fixed format, so text order *is* time order and a range works on text.)
2. **A rare value:** rows where duct static is above 1.7 inH2O (32 rows). Nobody indexed `da_p_inwc`, so this is a
   scan: all 35,536 rows read to return 32. Try it 2 builds an index for it.

pandas has no query planner. *You* choose the access path, and there are three:

| Question | SQL (`day11_sql.py`) | pandas (`day11_pandas.py`) |
|---|---|---|
| 2. look at every row | `SCAN` (no index) | a True/False mask `(df["timestamp_utc"] >= start) & ...`, O(n) every time |
| 3. build a sorted structure once | `CREATE INDEX` | `df.set_index("timestamp_utc").sort_index()`, O(n log n) once |
| 3. jump to the range | `SEARCH ... USING INDEX` | `.loc[start:last_row]` on the sorted index, O(log n + k) |
| do the jump by hand | (the B-tree does it) | `np.searchsorted(sorted_array, a)`, O(log n) per bound |

`.loc` on a sorted index includes its end label, so the pandas script names the week's last row
(`2026-05-07 23:55:00+00:00`) rather than the next midnight.

`np.searchsorted` is plain binary search: halve the sorted array until you find the spot. A B-tree is the same idea
made friendly to disks (many keys per node, so fewer steps), and it stays sorted as rows are added, which an array
does not.

**Big-O intuition.** A mask touches every row, so it costs about c·n per query. A sorted structure costs a
**one-time build** of about n·log n, then about log n + k per query. If the build costs B, one scan costs S and one
lookup costs L, the index pays for itself after about B / (S − L) queries. Both scripts print B, S and L, so you can
work it out: it is small here (a handful of queries) because the build is cheap. At 100 million rows the
build costs more in absolute time, but the scan grows 1000× while the lookup barely moves, so the index wins by more
and more. If you will only ask once, don't build an index: a scan is cheaper than build plus lookup.

**An index is not free, and not always useful.** It takes space, it must be updated on every insert (slowing
writes), and it only helps queries that are *selective*. Asking for 40% of the table through an index means jumping
around for 14,000 rows, and reading the table straight through is about as fast. Try it below.

## Run
```bash
uv run python lessons/course.py run 11
```

That runs [`day11_pandas.py`](day11_pandas.py), then [`day11_sql.py`](day11_sql.py). The row counts and the average
must match; the **timings differ** from run to run and machine to machine (the tests compare only the answers). Both
print:

```
Rows in the week: 2016
Rows in the week (index lookup): 2016
Average duct static in the week (inH2O): 0.5701
Rows with duct static above 1.7 inH2O: 32
```

then their own timings in milliseconds (scan, index lookup, building the index once), and the SQL script adds its two
plans:

```
Plan before the index: SCAN copy
Plan after the index:  SEARCH copy USING INDEX copy_time (timestamp_utc>? AND timestamp_utc<?)
```

The week is 2,016 rows (7 days × 288 five-minute rows) both ways. The lookup is faster than the scan, and building the
index costs about as much as one or a few scans.

## Try it

1. In the SQL script, add `conn.execute("CREATE INDEX temp.copy_da_p ON copy (da_p_inwc)")` and print the plan of
   step 4's query before and after. What changes?
2. Now raise the threshold to `1.2` inH2O (about 14,000 rows). Does the plan change? Is the indexed query still
   faster than a scan?
3. Why can't `set_index("timestamp_utc")` speed up "`da_p_inwc > 1.7`" in pandas?

<details><summary>Answers</summary>

1. Before: `SCAN copy`. After: `SEARCH copy USING COVERING INDEX copy_da_p (da_p_inwc>?)` ("covering" because the
   index holds every column the query needs), and the 32 rows are found without reading the other 35,504.
2. 14,237 rows match. The plan still says `SEARCH ... USING INDEX`, but the time is about the same as a scan. An index
   only wins when it lets the engine skip most of the table. When 40% of rows match, the cost is dominated by reading
   and returning those rows. Selectivity decides, not the plan wording.
3. An index on the timestamp is sorted by timestamp, so it only answers questions about timestamps. Another filter
   needs another sort order: `df.sort_values("da_p_inwc")` (or `np.argsort` of that column, the row numbers in value
   order) would be exactly what a second database index is.

</details>

## Why it matters

Real FDD queries are almost always "this equipment, this time range, this point". The database must jump straight
there, or a rule scales with the *whole history* instead of the slice it needs. Production historians use a
composite index on (series, time) for exactly this reason. Day 14's overlap check is a place to try one. Day 12
uses windows to look at neighbouring rows, and Day 13 turns that into streaks.
