# Day 23 — UUIDs and the long table: stable ids, `samples`, and pivoting long to wide

**Goal:** know why the history is stored under opaque, stable ids, see where Building 50's UUIDs come from, and pivot
AHU_1's three FC1 inputs from the long `samples` table back into the CSV's columns.

## Read

**Why an opaque id.** In the CSV a point's identity is its column name, `da_p_inwc`. That is fragile: the column is
renamed when a controller is replaced, two buildings use the same name for different things (Day 21), and merging two
exports collides names. A model-driven system wants an id with no meaning that never changes, so *everything else*
(names, labels, units, tags) can change around it. Day 21's `mad_c` / `mad_c_pct` mismatch can't happen to an id
nobody reads.

**Where these ids come from.** Each `timeseries_id` is a **UUIDv5**, defined in RFC 9562 (the 2024 update of RFC
4122): the SHA-1 hash of a namespace UUID plus a name, formatted as a UUID. The same name always gives the same id,
on any machine, with no registry to ask, so rebuilds and merges agree. This repo's rule:

```python
uuid.uuid5(uuid.NAMESPACE_URL, f"urn:openfdd:{building}:{equipment}:{source_column}")
# urn:openfdd:BUILDING_50:AHU_1:da_p_inwc  ->  52422584-9894-50bd-9696-2fbb8b062518
```

Both scripts recompute the id and compare it with the one in the point list. There is one trap: the id is derived
from the *name once*, then **frozen** in `model/points/*.csv`. If you re-derived it at query time and someone renamed
the column, the id would change and every stored series would be orphaned. The hash is a way to *mint* ids
reproducibly, not a way to *find* them later. (A v4 UUID, random, would also work. You'd just have to keep the table
that says which one is which, which is exactly what the frozen CSV is.)

**The long table.** The API's database, `var/timeseries.sqlite`, has no column names at all:

```sql
CREATE TABLE samples (timeseries_id TEXT, ts INTEGER, value REAL,
                      PRIMARY KEY (timeseries_id, ts)) WITHOUT ROWID
```

That is **long** (tall) form: one row per reading, 4.2 million rows for 118 points. The CSV is **wide**: one row per
timestamp, one column per point. Long form has real advantages for storage. A new point is new rows, not a new column
(`ALTER TABLE`); points that report at different times or with gaps don't need NULL padding; and the primary key
`(timeseries_id, ts)` with `WITHOUT ROWID` stores each series contiguously and in time order, so "all of one series
between two times" is one B-tree range scan. Wide form is what rules want: several signals side by side at the same
timestamp.

Going from long to wide is a **pivot**: one output row per timestamp, one output column per series.

| Step | `day23_pandas.py` | `day23_sql.py` |
|---|---|---|
| 1. role → UUID | `pd.read_csv("model/points/BUILDING_50__AHU_1.csv")` | `CREATE TEMP TABLE point` from the same CSV |
| 2. recompute the UUID | `uuid.uuid5(...)` | the same Python loop: SQLite has no SHA-1 |
| 3. read the long rows | `SELECT ts, value FROM samples WHERE timeseries_id = ?`, once per point | `FROM samples AS s JOIN point AS p ON p.timeseries_id = s.timeseries_id` |
| 4. pivot | `long.pivot(index="ts", columns="role", values="value")` | `MAX(CASE WHEN p.role = 'fan-status' THEN s.value END) ... GROUP BY s.ts` |
| 5. compare to the CSV | `merge` on epoch seconds, `==` per column | `JOIN wide AS w ON w.ts = unixepoch(c.timestamp_utc)`, with the CSV's table from an `ATTACH`ed second database |

`MAX(CASE ...)` is conditional aggregation again: within one timestamp each series has exactly one row, so `MAX`
just picks it and the other rows' NULLs are ignored. pandas' `pivot` is stricter and raises if a `(ts, series)` pair
repeats, which is a free check that your data has one value per timestamp. Either way it is O(n): one pass over the
long rows, then a group per timestamp.

The wide result has to equal the CSV's own columns, because the database was filled from that CSV. The scripts check
it value by value, and show the number of equal rows and the largest absolute difference.

## Run

This day needs `var/timeseries.sqlite`: `uv run bldgts model build && uv run bldgts bootstrap` once. (The test suite
skips the day if the file is missing.) The scripts open it read-only.

```bash
uv run python lessons/course.py run 23
```

That runs [`day23_pandas.py`](day23_pandas.py), then [`day23_sql.py`](day23_sql.py). Both print (the wide
table's columns come out in a different order, and its first rows are left out here):

```
The UUID of each FC1 input, and the same UUID minted again from its name:
                   role      source_column                        timeseries_id                      recomputed_uuid  matches
   duct-static-pressure          da_p_inwc 52422584-9894-50bd-9696-2fbb8b062518 52422584-9894-50bd-9696-2fbb8b062518     True
duct-static-pressure-sp da_p_setpoint_inwc 761c2b61-4982-5157-bc66-2010cf6e2a47 761c2b61-4982-5157-bc66-2010cf6e2a47     True
             fan-status  supply_fan_status 9ebf80dd-7821-510b-b2c0-cd0151e093c9 9ebf80dd-7821-510b-b2c0-cd0151e093c9     True

Long table: 106608 rows for 3 series.
                   role  rows   first_ts    last_ts
   duct-static-pressure 35536 1773621600 1784282100
duct-static-pressure-sp 35536 1773621600 1784282100
             fan-status 35536 1773621600 1784282100

Compared with the CSV's own columns:
                   role      source_column  rows_compared  rows_equal  max_abs_diff
   duct-static-pressure          da_p_inwc          35536       35536           0.0
duct-static-pressure-sp da_p_setpoint_inwc          35536       35536           0.0
             fan-status  supply_fan_status          35536       35536           0.0
```

3 series × 35,536 rows =
106,608 long rows become 35,536 wide rows.

## Try it

1. Change one letter of the name (`da_p_inwcX`) and mint the id again. How different is the result? What does
   that tell you about hand-editing ids?
2. Add the outside-air temperature to the pivot (role `outside-air-temp`) in both scripts. What does the long table
   cost per extra point, compared with adding a CSV column?

<details><summary>Answers</summary>

1. Completely different: a hash has no "nearby" ids. So an id can't be fixed by hand, and a rename means a new
   series unless you keep the old id. That is why the id is frozen in the point list.
2. One more role in the point filter and one more `MAX(CASE ...)` line (pandas' `pivot` adds the column by itself),
   and no schema change at all. The long table just has more rows. That is
   the storage argument for long form: points come and go without altering the table.

</details>

## Why it matters

Now the model's answer ("the fan status is `9ebf80dd-...`") leads to a series, and you can rebuild the wide
table a rule wants from the long one. The next question: the model says *an id*, but what says
*where to look it up*? Tomorrow's answer is the external timeseries reference.
