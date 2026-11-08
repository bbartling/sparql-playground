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

1. **A time range:** one week of rows. `timestamp_utc` is the table's `PRIMARY KEY`, so SQLite already keeps a
   B-tree sorted on it. The plan says `SEARCH ahu_1 USING INDEX sqlite_autoindex_ahu_1_1 (timestamp_utc>? AND
   timestamp_utc<?)`. (The timestamps are text in one fixed format, so text order *is* time order and a range
   works on text.)
2. **A rare value:** rows where duct static is above 1.7 inH2O (32 rows). Nobody indexed `da_p_inwc`, so the plan
   says `SCAN ahu_1`: it reads all 35,536 rows to return 32.

Then we **build an index on that column**. We do it on a `TEMP` copy of the table, so the lessons database is not
changed. The plan flips to `SEARCH ... USING INDEX copy_da_p (da_p_inwc>?)` and the query gets much faster.

pandas has no query planner. *You* choose the access path, and there are three:

| Question | SQL (`day11_sql.py`) | pandas (`day11_pandas.py`) |
|---|---|---|
| look at every row | `SCAN` (no index) | boolean mask `h[h.ts >= a]`, O(n) every time |
| build a sorted structure once | `CREATE INDEX` | `set_index("timestamp_utc").sort_index()`, O(n log n) once |
| jump to the range | `SEARCH ... USING INDEX` | `.loc[a:b]` on the sorted index, O(log n + k) |
| do the jump by hand | (the B-tree does it) | `np.searchsorted(sorted_array, a)`, O(log n) per bound |

`np.searchsorted` is plain binary search: halve the sorted array until you find the spot. A B-tree is the same idea
made friendly to disks (many keys per node, so fewer steps), and it stays sorted as rows are added, which an array
does not.

**Big-O intuition.** A mask touches every row, so it costs about c·n per query. A sorted structure costs a
**one-time build** of about n·log n, then about log n + k per query. If the build costs B, one scan costs S and one
lookup costs L, the index pays for itself after about B / (S − L) queries. Both scripts print that number for the
rare-value query. It is small here (roughly 8 to 10 queries) because the build is cheap. At 100 million rows the
build costs more in absolute time, but the scan grows 1000× while the lookup barely moves, so the index wins by more
and more. If you will only ask once, don't build an index: a scan is cheaper than build plus lookup.

**An index is not free, and not always useful.** It takes space, it must be updated on every insert (slowing
writes), and it only helps queries that are *selective*. Asking for 40% of the table through an index means jumping
around for 14,000 rows, and reading the table straight through is about as fast. Try it below.

## Run

```bash
uv run python lessons/course.py run 11
```

That runs [`day11_pandas.py`](day11_pandas.py), then [`day11_sql.py`](day11_sql.py). The row counts must match; the
**timings differ** from run to run and machine to machine (the tests compare only the rows). Expected shape of the
output (your milliseconds will vary):

```
One week of rows, by mask / .loc / searchsorted: 2016 / 2016 / 2016
  mask 3.262 ms | .loc 0.037 ms | searchsorted 0.020 ms
  building the index once: 1.887 ms
Rows with duct static > 1.7 inH2O: 32 (lookup finds 32)
  the sort pays for itself after about 8.0 queries
...
Plan, one week by timestamp_utc (the PRIMARY KEY):
  SEARCH ahu_1 USING INDEX sqlite_autoindex_ahu_1_1 (timestamp_utc>? AND timestamp_utc<?)
Plan, da_p_inwc > 1.7 (no index on that column):
  SCAN ahu_1
TEMP copy, before the index:
  SCAN ahu_1_copy
TEMP copy, after CREATE INDEX:
  SEARCH ahu_1_copy USING INDEX copy_da_p (da_p_inwc>?)
```

The week is 2,016 rows (7 days × 288 five-minute rows) in every method. The pandas script ends with a scaling table:
a mask over 10 million sorted floats takes milliseconds and grows with n, while `searchsorted` stays near two
microseconds.

## Try it

1. In both scripts raise the threshold to `1.2` inH2O (about 14,000 rows). Do the plans change? Is the indexed
   query still faster?
2. The TEMP copy has no primary key. Run `EXPLAIN QUERY PLAN` for the one-week range on the *copy*, then
   `CREATE INDEX temp.j ON ahu_1_copy (timestamp_utc)` and ask again.
3. Why can't `set_index("timestamp_utc")` speed up "`da_p_inwc > 1.7`" in pandas?

<details><summary>Answers</summary>

1. The plan still says `SEARCH ... USING INDEX`, but the time is the same as the scan (about 13 ms either way on
   the author's machine). An index only wins when it lets the engine skip most of the table. When 40% of rows
   match, the cost is dominated by reading and returning those rows. Selectivity decides, not the plan wording.
2. Before: `SCAN ahu_1_copy` (a copy made with `CREATE TABLE ... AS SELECT` has no primary key). After:
   `SEARCH ahu_1_copy USING INDEX j (timestamp_utc>? AND timestamp_utc<?)`. The original table gets this for free
   from its `PRIMARY KEY`.
3. An index on the timestamp is sorted by timestamp, so it only answers questions about timestamps. Another filter
   needs another sort order. That is why the script builds `np.argsort(da_p_inwc)` (row numbers in value order)
   for the rare-value query: it is exactly what a second database index is.

</details>

## Why it matters

Real FDD queries are almost always "this equipment, this time range, this point". The database must jump straight
there, or a rule scales with the *whole history* instead of the slice it needs. Production historians use a
composite index on (series, time); Day 14 builds one on its results (`fc1_eq_ts`) for exactly this reason. Day 12
uses windows to look at neighbouring rows, and Day 13 turns that into streaks.
