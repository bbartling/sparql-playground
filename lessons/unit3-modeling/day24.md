# Day 24 — External timeseries references: one model, history in SQLite or in a CSV

**Goal:** see how the model says *where* a point's history lives, add a second kind of store (a CSV file) to an
in-memory copy of the graph, write a resolver that reads a series from whichever store a reference names, and check
that both stores give the same series.

## Read

**What plain Haystack leaves out.** Haystack marks a point as having history with the marker `his` and reads it by
point id (the `hisRead` operation: "give me the history of point X"). But it has no standard tag for *where* that
history is stored. Which database? Which table, key, file? That is left to the server you ask.

**What the ref schema adds.** Brick's **ref schema** (the page "Timeseries storage" in the Brick docs) fills exactly
that gap, and it doesn't care what the store is. A point has a `ref:hasExternalReference` to a
`ref:TimeseriesReference`. The reference has exactly one `ref:hasTimeseriesId` (a string: the key of the series in
the store) and a `ref:storedAt` pointing at the store, which Brick types as a `ref:Database`. Brick doesn't say what
a database node must contain. This repo combines the two vocabularies, Haystack tags for *what the point is* and
reference nodes for *where its data is*:

```turtle
bldg:AHU_1_DA_P  bts:hasHaystackMarker "his", "point", ... ;
    ref:hasExternalReference [ a ref:TimeseriesReference ;
        ref:hasTimeseriesId "52422584-9894-50bd-9696-2fbb8b062518" ;
        ref:storedAt bldg:timeseries_db ] .

bldg:timeseries_db a ref:Database ;
    bts:backend "sqlite" ;  bts:connectionEnv "BLDGTS_DB_PATH" ;
    bts:schemaDescription "samples(timeseries_id TEXT, ts INTEGER epoch-s UTC, value REAL)" .
```

So the model has, for every point, "ask `timeseries_db` (SQLite; path in `$BLDGTS_DB_PATH`) for id `52422584-...`".
Because the reference is a node, a point can have **several**: the same sensor's history in the live database and in
an archive, or in a file someone sent you.

**A second store.** Today we add one, in memory, without touching `model/building_50.ttl`. Each AHU's CSV export
becomes a store, and each point gets a second reference to it. A CSV has no UUIDs: a series is identified by its
column, so that CSV reference's `hasTimeseriesId` is the **column name** (`da_p_inwc`). Where does the script learn
which column goes with which role? From Day 21's `column_map.json`. The model's roles plus the map give the column.

```turtle
bldg:csv_AHU_1 a bts:CsvFile ;  bts:path "data/BUILDING_50/AHU_1/history_wide.csv" ;
                                bts:timeColumn "timestamp_utc" .
bldg:AHU_1_DA_P ref:hasExternalReference [ a ref:TimeseriesReference ;
        ref:hasTimeseriesId "da_p_inwc" ; ref:storedAt bldg:csv_AHU_1 ] .
```

The store gets its own class, `bts:CsvFile`, and not `ref:Database`. Brick's `ref:Database` represents a storage
*system*; calling a file a "database" would stretch that class's meaning, and anything that dispatches on the class
("a database: connect to it") would be wrong about a file. A class of our own keeps the dispatch honest.

**The resolver** is the one function that knows about stores. Given a reference it looks at the store's class and
reads the series from the right place:

| Store class | `day24_pandas.py` | `day24_sql.py` |
|---|---|---|
| `ref:Database` (sqlite) | `read_sql_query("SELECT ts, value FROM samples WHERE timeseries_id = ?")` | the same `SELECT`, against an `ATTACH`ed database |
| `bts:CsvFile` | `read_csv(path, usecols=[time, column])`, time text → epoch seconds | load the needed columns into a `TEMP` table, `unixepoch(timestamp_utc)` as `ts` |
| anything else | `raise ValueError` | `raise ValueError` |

Notice what stays the same: the rule asks the model for "the fan status of AHU_1" and gets back references; the
resolver picks the store. Nothing in the rule knows whether the data came from a database or a file. Swapping
storage means changing the model (and, for a brand-new store *type*, adding a branch to the resolver), not the rules.

**One gotcha.** Once a point has two references, a query that joins through `ref:hasExternalReference` returns that
point *twice* (once per reference). The scripts use `SELECT DISTINCT ?point` to find the points and then ask for
their references separately. If a result suddenly has twice the rows after you add a reference, this is why.

The scripts compare the two stores for each of the 6 FC1 input series (3 per AHU): same number of rows, same values?

## Run

Needs `var/timeseries.sqlite` (`uv run bldgts model build && uv run bldgts bootstrap`).

```bash
uv run python lessons/course.py run 24
```

That runs [`day24_pandas.py`](day24_pandas.py), then [`day24_sql.py`](day24_sql.py). Both build the same graph with
rdflib (SQL can't read RDF), then differ in how they read the series. Both print:

```
       point_id         store store_class                        timeseries_id
     AHU_1_DA_P     csv_AHU_1     CsvFile                            da_p_inwc
     AHU_1_DA_P timeseries_db    Database 52422584-9894-50bd-9696-2fbb8b062518
     ...
       point_id  rows_sqlite  rows_csv  rows_equal  max_abs_diff
     AHU_1_DA_P        35536     35536       35536           0.0
     ...
```

All six series have 35,536 rows in each store and every value is identical.

## Try it

1. Add a third reference to one point: another `ref:Database`-typed node, with `bts:backend "postgres"`. What does the
   resolver do when it meets it? Is that the right behaviour?
2. Make the resolver pick the store: add a parameter `prefer` ("Database" or "CsvFile") that chooses among a point's
   references. What does a rule need to know to use it?

<details><summary>Answers</summary>

1. `read_series` raises `ValueError: no reader for database backend 'postgres'`. That is the right behaviour: failing
   loudly beats returning an empty series. To support it you add one branch (and a driver).
2. Nothing: `prefer` is part of the resolver call, not of the rule. Today's `refs` table has `store_class`; filter
   it before `read_series`. Day 25's challenge does exactly this.

</details>

## Why it matters

This is why model-driven FDD survives a change of storage. When history moves from CSV to SQLite, or SQLite to a
real time-series database, you change the *references*. The rules, written against roles and tags, don't move.
Tomorrow's rule runs through the app's API, which does the resolving for us.
