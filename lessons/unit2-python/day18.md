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
- If the next reading is more than `MAX_GAP_HOURS` away (`MAX_GAP_SECONDS` in our scripts), we don't know what
  happened. `held_seconds = 0`: that stretch is **not fault time, not covered time**, and `gap_after = 1` marks
  the row so the streak **breaks** there. The last row of each equipment has no next reading, so `held_seconds = 0`.
- A fault is **confirmed** when its streak has lasted `CONFIRM_SECONDS` *of elapsed time*:
  `streak_elapsed = running sum of held_seconds within the streak`.
- Report `fault_hours = sum(held_seconds where confirmed) / 3600` and **coverage**: the seconds we could vouch for
  divided by the seconds in the window (first to last timestamp).

**Why counting rows is wrong once there are gaps.** Three things go wrong. (1) A dropped row silently removes 5
minutes of fault time. (2) Two fault rows on either side of a six-hour outage look like consecutive rows, so the
streak "confirms" across time you never observed. (3) You cannot tell a healthy machine from one you couldn't see:
`fault_hours = 0` with 40% coverage is not good news. Coverage keeps the answer honest.

The data is the synthetic AHUs from Day 16, cut to the first **4,000 rows** (about 14 days) of each AHU. Then the
scripts punch holes in it, the way a flaky network does: every 37th row is dropped (a 10-minute gap), and on AHU_1
100 rows in a row are deleted (an outage of about 8 hours, while the fan is on). Both scripts build exactly the same
table: 7,687 of 8,000 rows. The constants are at the top of each script: `MAX_GAP_SECONDS = 3600` (1 hour),
`CONFIRM_SECONDS = 600` (the same 10 minutes as Day 14's two rows).

How each step maps across (compare Day 14's table):

| Step | `day18_sql.py` | `day18_pandas.py` |
|---|---|---|
| 4. next timestamp | `LEAD(ts) OVER (PARTITION BY equipment_id ORDER BY ts) - ts` | `df.groupby("equipment_id")["ts"].shift(-1)` |
| 4. held / gap flag | `CASE WHEN seconds_to_next > :max_gap_seconds THEN 0 ...` | `seconds_to_next.where(~gap_after, 0)` |
| 5. streak breaks | `LAG(raw_fault)` and `LAG(gap_after)` | `changed \| after_gap \| new_ahu` |
| 6. elapsed in streak | `SUM(held_seconds) OVER (PARTITION BY equipment_id, streak_id ORDER BY ts)` | `groupby("streak_id")["held_seconds"].cumsum()` |

The pandas script keeps both AHUs in one table, so a streak must also break at the first row of the next AHU
(`new_ahu`); in SQL `PARTITION BY equipment_id` does that for free. SQLite has no `EXTRACT(EPOCH FROM ...)` like
Postgres, but `ts` is already epoch seconds, so `next_ts - ts` is seconds directly. Units are SI: Pa, and seconds for
time.

## Run

```bash
uv run python lessons/course.py run 18
```

That runs [`day18_pandas.py`](day18_pandas.py), then [`day18_sql.py`](day18_sql.py). `RESULTS` in both holds the
per-AHU `summary` and the row-counting comparison (`naive_fault_hours`). Both print:

```
Rows left after the holes: 7687 of 8000

Gap-aware FC1 per AHU:
equipment_id  rows  long_gaps  fault_hours  covered_hours  window_hours  coverage
       AHU_1  3795          1       39.167        324.833        333.25     0.975
       AHU_2  3892          0       41.500        333.250        333.25     1.000

Row counting (Day 14) on the same rows:
equipment_id  naive_fault_hours
       AHU_1              38.33
       AHU_2              40.42
```

Look at what the gaps did. AHU_2 has only short drops, and sample-and-hold covers them: coverage 1.0. AHU_1's 8-hour
outage is longer than the limit, so it is `long_gaps = 1` and coverage falls to 0.975 (covered time = window time
minus the long gap: 333.25 − 8.42 = 324.83 h). The row before the outage has `held_seconds` 0 and the next row starts
a new streak, so the fault episode that runs into the outage stops at the outage rather than stretching across it.

**Now the wrong way.** Step 8 runs Day 14's row-counting rule on the same gappy rows. It is low on
both AHUs: 1.08 hours on AHU_2 and 0.83 on AHU_1. Every dropped row took 5 minutes of fault time with it, where
sample-and-hold keeps them. On AHU_1 the row count also has no notion of the outage: its streak runs straight across
8 unobserved hours. Only the gap-aware numbers come with a coverage figure that tells you how far to trust them.

**A loop would be simple here too.** One forward pass with four pieces of state (the previous raw flag, whether the
previous row ended in a gap, the streak's elapsed time, the AHU) reads just like the description in "Read". SQL needs
a window function per step. Day 20 writes that loop and times it.

## Try it

1. Raise `MAX_GAP_SECONDS` to 12 hours (`12 * 3600`; `"max_gap_seconds"` in SQL). What happens to AHU_1's coverage,
   its `long_gaps` count and its fault hours?
2. Confirm faults over 1 hour (`CONFIRM_SECONDS = 3600`) instead of 10 minutes. Do fault hours rise or fall, and why?

Change the constant in both scripts and check that they still agree.

<details><summary>Answers</summary>

1. `long_gaps` 0 and coverage 1.0 for both AHUs, and AHU_1's fault hours jump from 39.17 to 47.67: it now counts
   the 8 hours *as if the fault state at the start of the outage persisted through it*. That is the cost of a large
   gap limit: you assert knowledge you don't have. Pick the limit from how fast the equipment can change state, not
   from how much you'd like to cover.
2. Fault hours fall (AHU_1 39.17 to 35.58 h, AHU_2 41.50 to 38.17 h). Faults shorter than an hour never confirm, and
   in longer ones the first hour of each episode is not counted (a row only counts once its streak's elapsed time
   reaches the threshold). A longer confirmation time trades sensitivity for fewer false alarms.

</details>

## Why it matters

Every real Open-FDD rule has this `elapsed_hold` block, and its parity tests check it. A rule without it will pass on
clean test data and quietly over- or under-report on a building with a flaky gateway. Day 19 joins a second time
series (weather) to these rows, and the same question (how old is too old?) returns.
