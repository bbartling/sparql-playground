# Day 18 — Gaps and coverage: sample-and-hold, three ways

**Goal:** make a fault rule honest when the data has holes: hold each reading until the next one, treat a long gap
as "unknown", confirm faults by elapsed time rather than row count, and report coverage next to fault hours.
Implement it in SQL, pandas and plain Python, and prove all three agree.

## Read

Day 14 counted rows and multiplied by 5 minutes. That works only if every 5-minute row exists. Real controllers
go offline, networks drop, a trend log gets cleared. Open-FDD's rules (read
`sql/fdd/postgres/rules/cmd1_fan_mismatch.sql`) handle this with **forward sample-and-hold**:

- A reading is assumed to hold until the *next reading arrives*. `held_seconds = next_ts - ts`. A missing row
  just means its predecessor holds for 10 minutes instead of 5, and the time is still counted.
- If the next reading is more than `MAX_GAP_HOURS` away, we don't know what happened. `held_seconds = 0`: that
  stretch is **not fault time, not covered time**, and `gap_after = 1` marks the row so the streak **breaks** there.
  The last row of each equipment has no next reading, so `held_seconds = 0`.
- A fault is **confirmed** when its streak has lasted `CONFIRM_SECONDS` *of elapsed time*:
  `streak_elapsed = running sum of held_seconds within the streak`.
- Report `fault_hours = sum(held_seconds where confirmed) / 3600` and **coverage**: the seconds we could vouch for
  divided by the seconds in the window (first to last timestamp).

**Why counting rows is wrong once there are gaps.** Three things go wrong. (1) A dropped row silently removes 5
minutes of fault time. (2) Two fault rows on either side of a six-hour outage look like consecutive rows, so the
streak "confirms" across time you never observed. (3) You cannot tell a healthy machine from one you couldn't see:
`fault_hours = 0` with 40% coverage is not good news. Coverage keeps the answer honest.

How each step maps across (compare Day 14's table):

| Step | SQL (SQLite) | pandas | plain Python |
|---|---|---|---|
| next timestamp | `LEAD(ts) OVER (PARTITION BY eq ORDER BY ts)` | `df.groupby(eq).ts.shift(-1)` | look at the next row if same equipment |
| held / gap flag | `CASE WHEN dt > :max_gap_s THEN ...` | `np.where(...)` | `if dt > limit:` |
| streak breaks | `LAG(raw)` and `LAG(gap_after)` in a `CASE` | `raw.ne(raw.shift())` or previous gap | `if raw != prev_raw or prev_gap:` |
| elapsed in streak | `SUM(held) OVER (PARTITION BY eq, streak_id ORDER BY ts)` | `held.groupby([eq, streak]).cumsum()` | `elapsed += held` |

SQLite has no `EXTRACT(EPOCH FROM ...)` like Postgres, but `ts` is already epoch seconds, so `next_ts - ts` is
seconds directly. Units are SI: Pa, and seconds for time.

## Run

```python
import sqlite3

import numpy as np
import pandas as pd

import lab

conn = lab.connect()

TOL_PA = 25.0
MAX_GAP_HOURS = 1.0
CONFIRM_SECONDS = 600  # 10 minutes, the same as Day 14's two 5-minute rows
N = 4_000  # rows per AHU before drops: about 14 days
```

**Synthetic data with holes.** Two AHUs; 3% of rows dropped at random (short gaps of 10-15 minutes), plus one long
outage on AHU_1: 100 rows (about 8 hours) deleted from from inside its weak-fan window, while the fan is on.

```python
raw_df = lab.synthetic_history(N, equips=2, gap_prob=0.03)
T0 = int(raw_df.ts.min())
outage = (raw_df.equipment_id == "AHU_1") & raw_df.ts.between(T0 + 1560 * 300, T0 + 1659 * 300)
gappy = raw_df[~outage].sort_values(["equipment_id", "ts"]).reset_index(drop=True)

mem = sqlite3.connect(":memory:")
lab.to_sqlite(gappy, mem, "gap_h", index=["equipment_id", "ts"])
dts = gappy.groupby("equipment_id").ts.diff().dropna()
print(
    f"{len(gappy):,} rows (of {2 * N:,}); step seconds seen:",
    dts.value_counts().sort_index().to_dict(),
)
assert dts.max() > MAX_GAP_HOURS * 3600 and (dts <= 900).sum() > 0.9 * len(dts)
```

**In SQL.** Same shape as `cmd1_fan_mismatch.sql`, in SQLite's dialect. One query returns every row's state;
a second wraps it to summarize.

```python
ROW_SQL = """
WITH base AS (
  SELECT equipment_id, ts,
         CASE WHEN fan_status = 1 AND duct_static < duct_static_sp - :tol THEN 1 ELSE 0 END AS raw_fault
  FROM gap_h
), stepped AS (
  SELECT *, LEAD(ts) OVER (PARTITION BY equipment_id ORDER BY ts) - ts AS dt_seconds FROM base
), elapsed_hold AS (
  SELECT *,
         CASE WHEN dt_seconds IS NULL OR dt_seconds <= 0 OR dt_seconds > :max_gap_s
              THEN 0.0 ELSE dt_seconds END AS held_seconds,
         CASE WHEN dt_seconds > :max_gap_s THEN 1 ELSE 0 END AS gap_after
  FROM stepped
), lagged AS (
  SELECT *,
         CASE WHEN raw_fault = LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts)
                   AND COALESCE(LAG(gap_after) OVER (PARTITION BY equipment_id ORDER BY ts), 0) = 0
              THEN 0 ELSE 1 END AS is_new_streak
  FROM elapsed_hold
), grp AS (
  SELECT *, SUM(is_new_streak) OVER (PARTITION BY equipment_id ORDER BY ts ROWS UNBOUNDED PRECEDING) AS streak_id
  FROM lagged
), ranked AS (
  SELECT *, SUM(held_seconds) OVER (PARTITION BY equipment_id, streak_id ORDER BY ts
                                    ROWS UNBOUNDED PRECEDING) AS streak_elapsed
  FROM grp
)
SELECT equipment_id, ts, raw_fault, held_seconds, gap_after, streak_id, streak_elapsed,
       CASE WHEN raw_fault = 1 AND streak_elapsed >= :confirm_s THEN 1 ELSE 0 END AS confirmed
FROM ranked
"""
SUMMARY_SQL = (
    """
SELECT equipment_id,
       COUNT(*) AS rows,
       SUM(gap_after) AS long_gaps,
       SUM(CASE WHEN confirmed = 1 THEN held_seconds ELSE 0.0 END) / 3600.0 AS fault_hours,
       SUM(held_seconds) / 3600.0 AS covered_hours,
       (MAX(ts) - MIN(ts)) / 3600.0 AS window_hours,
       SUM(held_seconds) / (MAX(ts) - MIN(ts)) AS coverage
FROM ("""
    + ROW_SQL
    + """)
GROUP BY equipment_id
"""
)


def sql_params(max_gap_h=MAX_GAP_HOURS, confirm_s=CONFIRM_SECONDS, tol=TOL_PA):
    return {"tol": tol, "max_gap_s": max_gap_h * 3600.0, "confirm_s": confirm_s}


rows_sql = lab.query(mem, ROW_SQL, sql_params())
sum_sql = lab.query(mem, SUMMARY_SQL, sql_params())
print(sum_sql.round(3).to_string(index=False))
```

**In pandas.** Every step a column operation. `shift(-1)` inside a `groupby` is `LEAD`; `shift()` is `LAG`.

```python
def gap_pandas(df, max_gap_h=MAX_GAP_HOURS, confirm_s=CONFIRM_SECONDS, tol=TOL_PA):
    """df sorted by (equipment_id, ts). Returns the per-row frame (same columns as ROW_SQL)."""
    eq = df["equipment_id"]
    raw = ((df.fan_status == 1) & (df.duct_static < df.duct_static_sp - tol)).astype(int)
    dt = df.groupby("equipment_id").ts.shift(-1) - df.ts  # NaN on each equipment's last row
    limit = max_gap_h * 3600.0
    held = pd.Series(
        np.where((dt > 0) & (dt <= limit), dt, 0.0), index=df.index
    )  # NaN compares False -> 0
    gap_after = (dt > limit).astype(int)
    prev_gap = gap_after.groupby(eq).shift().fillna(0)
    same = (raw == raw.groupby(eq).shift()) & (
        prev_gap == 0
    )  # first row: shift is NaN -> False -> new
    streak_id = (~same).astype(int).groupby(eq).cumsum()
    elapsed = held.groupby([eq, streak_id]).cumsum()
    confirmed = ((raw == 1) & (elapsed >= confirm_s)).astype(int)
    return df[["equipment_id", "ts"]].assign(
        raw_fault=raw,
        held_seconds=held,
        gap_after=gap_after,
        streak_id=streak_id,
        streak_elapsed=elapsed,
        confirmed=confirmed,
    )


def summarize(rows):
    g = rows.assign(fault_s=rows.held_seconds.where(rows.confirmed == 1, 0.0)).groupby(
        "equipment_id"
    )
    out = g.agg(
        rows=("ts", "size"),
        long_gaps=("gap_after", "sum"),
        fault_s=("fault_s", "sum"),
        covered_s=("held_seconds", "sum"),
        t0=("ts", "min"),
        t1=("ts", "max"),
    )
    out["fault_hours"] = out.fault_s / 3600.0
    out["covered_hours"] = out.covered_s / 3600.0
    out["window_hours"] = (out.t1 - out.t0) / 3600.0
    out["coverage"] = out.covered_s / (out.t1 - out.t0)
    return out[
        ["rows", "long_gaps", "fault_hours", "covered_hours", "window_hours", "coverage"]
    ].reset_index()


rows_pd = gap_pandas(gappy)
lab.assert_parity(rows_pd, rows_sql, keys=["equipment_id", "ts"], label="per row, pandas vs SQL")
sum_pd = summarize(rows_pd)
lab.assert_parity(sum_pd, sum_sql, label="summary, pandas vs SQL")
```

**In plain Python.** A single forward pass with four pieces of state: the previous raw flag, whether the previous row
ended in a gap, the streak number and the running elapsed time. The only look-ahead is the next row's timestamp.

```python
def gap_loop(conn, max_gap_h=MAX_GAP_HOURS, confirm_s=CONFIRM_SECONDS, tol=TOL_PA):
    data = conn.execute(
        "SELECT equipment_id, ts, fan_status, duct_static, duct_static_sp FROM gap_h ORDER BY equipment_id, ts"
    ).fetchall()
    limit = max_gap_h * 3600.0
    out, totals = [], {}
    prev_eq = prev_raw = prev_gap = None
    streak_id = 0
    elapsed = 0.0
    for i, (eq, ts, fan, static, sp) in enumerate(data):
        raw = 1 if fan == 1 and static < sp - tol else 0
        has_next = i + 1 < len(data) and data[i + 1][0] == eq
        dt = data[i + 1][1] - ts if has_next else None
        held = dt if dt is not None and 0 < dt <= limit else 0.0
        gap = 1 if dt is not None and dt > limit else 0
        if eq != prev_eq:  # a new equipment: reset the state machine
            streak_id, elapsed, prev_raw, prev_gap = 0, 0.0, None, 0
            totals[eq] = {"rows": 0, "long_gaps": 0, "fault_s": 0.0, "covered_s": 0.0, "t0": ts}
        if raw != prev_raw or prev_gap:
            streak_id += 1
            elapsed = 0.0
        elapsed += held
        confirmed = 1 if raw == 1 and elapsed >= confirm_s else 0
        out.append((eq, ts, raw, held, gap, streak_id, elapsed, confirmed))
        t = totals[eq]
        t["rows"] += 1
        t["long_gaps"] += gap
        t["covered_s"] += held
        t["fault_s"] += held if confirmed else 0.0
        t["t1"] = ts
        prev_eq, prev_raw, prev_gap = eq, raw, gap
    rows = pd.DataFrame(
        out,
        columns=[
            "equipment_id",
            "ts",
            "raw_fault",
            "held_seconds",
            "gap_after",
            "streak_id",
            "streak_elapsed",
            "confirmed",
        ],
    )
    summary = pd.DataFrame(
        [
            {
                "equipment_id": eq,
                "rows": t["rows"],
                "long_gaps": t["long_gaps"],
                "fault_hours": t["fault_s"] / 3600.0,
                "covered_hours": t["covered_s"] / 3600.0,
                "window_hours": (t["t1"] - t["t0"]) / 3600.0,
                "coverage": t["covered_s"] / (t["t1"] - t["t0"]),
            }
            for eq, t in totals.items()
        ]
    )
    return rows, summary


rows_loop, sum_loop = gap_loop(mem)
lab.assert_parity(rows_loop, rows_sql, keys=["equipment_id", "ts"], label="per row, loop vs SQL")
lab.assert_parity(sum_loop, sum_sql, label="summary, loop vs SQL")
```

Three implementations, identical on every row and on the summary. Now look at what the gaps did:

```python
s = sum_sql.set_index("equipment_id")
print(
    s[["rows", "long_gaps", "fault_hours", "covered_hours", "window_hours", "coverage"]]
    .round(3)
    .to_string()
)
assert s.loc["AHU_1", "long_gaps"] == 1 and s.loc["AHU_2", "long_gaps"] == 0
assert s.loc["AHU_2", "coverage"] == 1.0  # short drops are held over: fully covered
assert s.loc["AHU_1", "coverage"] < 1.0  # the 8-hour outage is not

# covered time = window time minus every gap longer than the limit (an independent check)
d_ts = gappy.groupby("equipment_id").ts.diff().dropna()
long_gap_s = d_ts[d_ts > MAX_GAP_HOURS * 3600].groupby(gappy.equipment_id).sum()
window_s = gappy.groupby("equipment_id").ts.agg(lambda x: x.max() - x.min())
assert (
    abs(s.loc["AHU_1", "covered_hours"] * 3600 - (window_s["AHU_1"] - long_gap_s["AHU_1"])) < 1e-6
)

print(rows_sql[rows_sql.gap_after == 1].to_string(index=False))
```

Look at the one row with `gap_after = 1`: its `held_seconds` is 0 and the next row starts a new streak, so the
fault episode that runs into the outage stops at the outage rather than stretching across it.

**Now the wrong way.** Day 14's row-counting version, run on the same gappy table:

```python
NAIVE_SQL = """
WITH base AS (
  SELECT equipment_id, ts,
         CASE WHEN fan_status = 1 AND duct_static < duct_static_sp - :tol THEN 1 ELSE 0 END AS raw_fault
  FROM gap_h
), marks AS (
  SELECT *, CASE WHEN raw_fault = LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts) THEN 0 ELSE 1 END
         AS new_streak FROM base
), streaks AS (
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id FROM marks
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts) AS streak_len FROM streaks
)
SELECT equipment_id, SUM(raw_fault = 1 AND streak_len >= 2) * 5 / 60.0 AS naive_fault_hours
FROM ranked GROUP BY equipment_id
"""
naive = lab.query(mem, NAIVE_SQL, {"tol": TOL_PA}).set_index("equipment_id")
cmp = pd.DataFrame({"row_count_hours": naive.naive_fault_hours, "gap_aware_hours": s.fault_hours})
cmp["difference_h"] = cmp.gap_aware_hours - cmp.row_count_hours
print(cmp.round(2).to_string())
assert (cmp.difference_h > 0.05).all()  # dropped rows lose time in the row-count version
```

AHU_2 has only short drops, and the row-count version is 0.5 hours low: every dropped row took 5 minutes of fault
time with it, where sample-and-hold keeps them. AHU_1 is off by much less, but not because the row-count method is
right there. It loses time to dropped rows *and* has no notion of the outage (the sample-and-hold version breaks the
streak at the outage and counts nothing inside it), so its errors partly cancel by luck. Only the gap-aware numbers
come with a coverage figure that tells you how far to trust them.

## Try it

1. Raise `MAX_GAP_HOURS` to 12. What happens to AHU_1's coverage, its `gap_after` count and its fault hours? Run all
   three implementations and check parity.
2. Confirm faults over 1 hour (`CONFIRM_SECONDS = 3600`) instead of 10 minutes. Parity again. Do fault hours rise or
   fall, and why?

<details><summary>Answers</summary>

```python
def three_way(max_gap_h, confirm_s, label):
    sq = lab.query(mem, SUMMARY_SQL, sql_params(max_gap_h, confirm_s))
    pdf = summarize(gap_pandas(gappy, max_gap_h, confirm_s))
    lp = gap_loop(mem, max_gap_h, confirm_s)[1]
    lab.assert_parity(pdf, sq, label=label + " pandas")
    lab.assert_parity(lp, sq, label=label + " loop")
    return sq.set_index("equipment_id")


# 1. a 12-hour limit makes the outage "held" like any short drop
wide = three_way(12.0, CONFIRM_SECONDS, "12 h limit")
print(wide[["long_gaps", "fault_hours", "coverage"]].round(3).to_string())
assert wide.loc["AHU_1", "long_gaps"] == 0 and wide.loc["AHU_1", "coverage"] == 1.0

# 2. a one hour confirmation
slow = three_way(MAX_GAP_HOURS, 3600, "1 h confirm")
print(slow[["fault_hours"]].round(2).to_string())
assert (slow.fault_hours < s.fault_hours).all()
```

1. Coverage goes to 1.0 and `gap_after` to 0, and AHU_1 now counts the 8 hours *as if the fault state at the start of
   the outage persisted through it*. That is the cost of a large `MAX_GAP_HOURS`: you assert knowledge you don't have.
   Pick the limit from how fast the equipment can change state, not from how much you'd like to cover.
2. Fault hours fall. Faults shorter than an hour never confirm, and in longer ones the first hour of each
   episode is not counted (a row only counts once its streak's elapsed time reaches the threshold). A longer
   confirmation time trades sensitivity for fewer false alarms.

</details>

## Why it matters

Every real Open-FDD rule has this `elapsed_hold` block, and its parity tests check it. A rule without it will pass on
clean test data and quietly over- or under-report on a building with a flaky gateway. Day 19 joins a second time
series (weather) to these rows, and the same question (how old is too old?) returns.
