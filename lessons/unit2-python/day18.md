# Day 18 — Gaps and coverage: sample-and-hold, three ways

**Goal:** make a fault rule honest when the data has holes: hold each reading until the next one, treat a long gap
as "unknown", confirm faults by elapsed time rather than row count, and report coverage next to fault hours.
Implement it in SQL, pandas and plain Python, and compare all three.

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

The data is synthetic (`lab.synthetic_history(4000, equips=2, gap_prob=0.03)`): two AHUs with 3% of rows dropped at
random (short gaps of 10-15 minutes), plus one long outage on AHU_1: 100 rows (about 8 hours) deleted from inside its
weak-fan window, while the fan is on. Both scripts build exactly the same table (7,648 of 8,000 rows). The constants
are at the top of each script: `MAX_GAP_HOURS = 1`, `CONFIRM_SECONDS = 600` (the same 10 minutes as Day 14's two rows).

How each step maps across (compare Day 14's table):

| Step | `day18_sql.py` | `day18_pandas.py` (vectorized) | `day18_pandas.py` (plain Python loop) |
|---|---|---|---|
| next timestamp | `LEAD(ts) OVER (PARTITION BY eq ORDER BY ts)` | `df.groupby(eq).ts.shift(-1)` | look at the next row if same equipment |
| held / gap flag | `CASE WHEN dt > :max_gap_s THEN ...` | `np.where(...)` | `if dt > limit:` |
| streak breaks | `LAG(raw)` and `LAG(gap_after)` in a `CASE` | `raw.ne(raw.shift())` or previous gap | `if raw != prev_raw or prev_gap:` |
| elapsed in streak | `SUM(held) OVER (PARTITION BY eq, streak_id ORDER BY ts)` | `held.groupby([eq, streak]).cumsum()` | `elapsed += held` |

SQLite has no `EXTRACT(EPOCH FROM ...)` like Postgres, but `ts` is already epoch seconds, so `next_ts - ts` is
seconds directly. Units are SI: Pa, and seconds for time.

## Run

```bash
uv run python lessons/course.py run 18
```

That runs [`day18_pandas.py`](day18_pandas.py) (vectorized pandas, then the plain Python loop in its own section 3),
then [`day18_sql.py`](day18_sql.py). `RESULTS` in both holds the per-row state (`rows`), the per-AHU `summary`, the
row-counting comparison (`naive_fault_hours`) and the two Try-it variants. Both print the summary:

```
equipment_id  rows  long_gaps  fault_hours  covered_hours  window_hours  coverage
       AHU_1  3785          1        6.750        324.833        333.25     0.975
       AHU_2  3863          0       14.417        333.250        333.25     1.000
```

Look at what the gaps did. AHU_2 has only short drops, and sample-and-hold covers them: coverage 1.0. AHU_1's 8-hour
outage is longer than `MAX_GAP_HOURS`, so it is `long_gaps = 1` and coverage falls to 0.975 (covered time = window
time minus the long gaps; the pandas script prints that check). The one row with `gap_after = 1` has `held_seconds` 0
and the next row starts a new streak, so the fault episode that runs into the outage stops at the outage rather than
stretching across it.

The pandas script also checks the loop against the vectorized version, and prints `loop rows == pandas rows: True` and
`loop summary == pandas summary: True`. The `streak_id` of each row and the `streak_elapsed` are in `rows` for a
row-by-row comparison with the SQL.

**Now the wrong way.** Day 14's row-counting version, run on the same gappy rows (section 4 in both scripts):

```
equipment_id  naive_fault_hours  fault_hours  difference_h
       AHU_1               6.67         6.75          0.08
       AHU_2              13.92        14.42          0.50
```

AHU_2 has only short drops, and the row-count version is 0.5 hours low: every dropped row took 5 minutes of fault time
with it, where sample-and-hold keeps them. AHU_1 is off by much less, but not because the row-count method is right
there. It loses time to dropped rows *and* has no notion of the outage (the sample-and-hold version breaks the streak
at the outage and counts nothing inside it), so its errors partly cancel by luck. Only the gap-aware numbers come with
a coverage figure that tells you how far to trust them.

**Where the plain loop wins.** The loop is one forward pass with four pieces of state (the previous raw flag, whether
the previous row ended in a gap, the streak number, the running elapsed time), and it reads like the description in
"Read". SQL needs four window functions and a CTE per step for the same thing. The loop has to reset its state when the
equipment changes (`if eq != prev_eq`); `PARTITION BY` does that for SQL for free.

## Try it

1. Raise `MAX_GAP_HOURS` to 12. What happens to AHU_1's coverage, its `gap_after` count and its fault hours?
2. Confirm faults over 1 hour (`CONFIRM_SECONDS = 3600`) instead of 10 minutes. Do fault hours rise or fall, and why?

Both are already computed in each script's `RESULTS` (`summary_12h_limit`, `summary_confirm_1h`), so the pandas
and SQL answers are compared. Change the constants at the top of a script to see them from a different angle.

<details><summary>Answers</summary>

1. The printout shows `long_gaps` 0 and coverage 1.0 for both AHUs, and AHU_1's fault hours jump from 6.75 to 15.17:
   it now counts the 8 hours *as if the fault state at the start of the outage persisted through it*. That is the
   cost of a large `MAX_GAP_HOURS`: you assert knowledge you don't have. Pick the limit from how fast the equipment can
   change state, not from how much you'd like to cover.
2. Fault hours fall (AHU_1 6.75 to 5.08 h, AHU_2 14.42 to 12.75 h). Faults shorter than an hour never confirm, and in
   longer ones the first hour of each episode is not counted (a row only counts once its streak's elapsed time reaches
   the threshold). A longer confirmation time trades sensitivity for fewer false alarms.

</details>

## Why it matters

Every real Open-FDD rule has this `elapsed_hold` block, and its parity tests check it. A rule without it will pass on
clean test data and quietly over- or under-report on a building with a flaky gateway. Day 19 joins a second time
series (weather) to these rows, and the same question (how old is too old?) returns.
