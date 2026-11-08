# Day 1 — Open the data; what one row is

**Goal:** open AHU_1's export in pandas and in SQLite, and say in one sentence what a row means.

## Read

An HVAC controller measures things (temperatures, pressures, fan status) and a **historian** saves a reading every
few minutes. Building 50's historian exported one CSV per air handler (AHU): `data/BUILDING_50/AHU_1/history_wide.csv`
and the same for `AHU_2`. This week you work with AHU_1, and bring in AHU_2 only where it helps.

The CSV is a **wide** table:

- **One row is one moment**: a timestamp, every five minutes, in UTC.
- **One column is one point**: a sensor, a setpoint, a status or a command. The cell holds that point's value at
  that moment.

So `timestamp_utc = 2026-03-16 00:40:00+00:00` and `outside_air_temp_f = 69.0327` in the same row means: at 00:40 UTC
the outside air sensor read 69.0327 °F. AHU_1's file has 84 columns (the timestamp plus 83 points) and 35,536 rows.
(The opposite shape, one row per point per timestamp, is called **long**. Day 11 converts between the two, and
Week 5's API stores long data.)

Two scripts open the same data two ways:

| | `day01_pandas.py` | `day01_sql.py` |
|---|---|---|
| open | `pd.read_csv(".../AHU_1/history_wide.csv")` | the table `ahu_1` in `var/lessons.sqlite` |
| how many rows | `len(df)` / `df.shape[0]` | `SELECT count(*) FROM ahu_1` |
| what are the columns | `df.columns`, `df.dtypes` | `PRAGMA table_info(ahu_1)` |
| first rows | `df[cols].head(5)` | `SELECT cols FROM ahu_1 ORDER BY timestamp_utc LIMIT 5` |

**What `setup_db.py` does.** `uv run python lessons/course.py setup` runs `lessons/setup_db.py`, which reads each CSV
and writes one SQLite table: `ahu_1`, `ahu_2` (and `fdd_events`, which Day 14 uses). Nothing is transformed. The
columns keep their names and their order, `timestamp_utc` is stored as the same text as in the file and is the
`PRIMARY KEY`, and every other column is `REAL`. So the pandas script and the SQL script look at identical rows.
SQLite is a whole SQL database in one file: no server, no login, and Python ships with it (`import sqlite3`).

**What the columns mean.** Next to each CSV sits `columns.csv`: one line per column with the historian's point name
(`bld_50_AHU_1 AHU1 OA-T`), its unit and a rough role. Names like `outside_air_temp_f` are cleaned-up versions
of those.
Units are US units: °F, inches of water (`inwc`), percent 0–100, and statuses are 0 or 1 stored as numbers.
`columns.csv` is a file, not a table in the database, so only the pandas script reads it (step 6).

**Why the column names are typed into code.** All of Weeks 1–4 write names like `outside_air_temp_f` and
`supply_fan_status` straight into the scripts. That is how a first analysis looks, and it is fine for one building. It
also means the code only works on exports that use exactly those names: AHU_2's file has 67 columns, and calls its
outside-air damper `mad_c_pct` where AHU_1 has `mad_c`. Week 5 replaces typed names with a model that says which
column is the duct static pressure, so the same rule runs on any air handler.

## Run

```bash
uv run python lessons/course.py setup        # once
uv run python lessons/course.py run 1
```

That runs [`day01_pandas.py`](day01_pandas.py), then [`day01_sql.py`](day01_sql.py). Read them side by side: each
numbered comment in one has the same number in the other. Both print the same shape, column names, first rows and
time span:

```
rows x columns per AHU:
equipment_id  rows  columns
       AHU_1 35536       84
       AHU_2 35536       67

the first five rows, five columns:
            timestamp_utc  outside_air_temp_f  da_p_inwc  da_p_setpoint_inwc  supply_fan_status
2026-03-16 00:40:00+00:00             69.0327   0.024594                 1.2                0.0
...

time span:
                first_utc                  last_utc  distinct_timestamps
2026-03-16 00:40:00+00:00 2026-07-17 09:55:00+00:00                35536
```

35,536 rows × 5 minutes is about 123 days, and 35,536 distinct timestamps means every row is its own moment. pandas
reports dtype `float64` for the 83 points and `object` (text) for the timestamp; SQLite reports declared types `REAL`
and `TEXT`. The same fact in each tool's vocabulary.

Two things to notice:

- `supply_fan_status` prints as `0.0`, not `0`. A status is a number in a historian, and the CSV stores it as a
  decimal.
- `read_csv` pulled all 84 columns into memory (about 24 MB). Fine here. From Day 2 on the scripts load only the
  columns they use (`usecols=[...]`).

## Try it

1. How many columns does AHU_2 share with AHU_1? Which non-zone columns does only one of them have?
2. How many of AHU_1's columns are zone temperatures (names starting `zone_t50_`)?

<details><summary>Answers</summary>

1. 34 columns are common, 50 are only in AHU_1 and 33 only in AHU_2. Outside the zone temperatures, AHU_1 alone has
   `50ahu1aalrm`, `mad_c` and a long auto-generated `hu_50_duration_...` column; AHU_2 alone has `50ahu2aalrm` and
   `mad_c_pct`. The `mad_c`/`mad_c_pct` pair is the same kind of point (outside air damper) under two names: a rule
   written with a typed column name would work on one AHU and not the other.

   ```python
   a = set(pd.read_csv(DATA / "AHU_1" / "history_wide.csv", nrows=0).columns)  # nrows=0: header only
   b = set(pd.read_csv(DATA / "AHU_2" / "history_wide.csv", nrows=0).columns)
   print(len(a & b), sorted(a - b), sorted(b - a))
   ```

   In SQL the same comparison is `SELECT name FROM pragma_table_info('ahu_1') EXCEPT SELECT name FROM
   pragma_table_info('ahu_2')`.

2. 47 of the 84 (31 in AHU_2). In pandas: `sum(c.startswith("zone_t50_") for c in df.columns)`; in SQL, count the rows
   of `pragma_table_info('ahu_1')` whose `name LIKE 'zone%'`. Most of an AHU's columns are readings from the zones
   it serves, not from the AHU itself.

</details>

## Why it matters

Every analysis starts with "what is one row, and what is one column?". Here a row is a moment and a column is a point,
which makes questions about one moment easy (compare the fan and the duct static in the same row) and questions about
one point easy (take a column). What this table does not say is what each column *is*: `da_p_inwc` is the duct static
pressure only because `columns.csv`, and some building knowledge, say so. Closing that gap is the point of Week 5.
