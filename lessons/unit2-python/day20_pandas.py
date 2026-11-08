"""Day 20, pandas side: Day 14's FC1 confirmation streaks as a Python loop and as vectorized pandas.

    uv run python lessons/unit2-python/day20_pandas.py

The rule is Day 14's: raw fault = fan running and duct static more than 25 Pa below setpoint; a
fault is confirmed once the raw fault has held for 2 consecutive rows. "Consecutive" is what makes
the tools differ: each row's answer depends on the rows before it.

Here: the plain Python state machine (one pass, O(1) state) and the pandas column trick (shift,
cumsum, cumcount), checked row by row, then timed on data that grows 10x per step. Also the "stop
early" experiment and the Week 4 challenge (longest confirmed episode per AHU, three ways; the loop
and pandas versions are here, the SQL one in day20_sql.py). Same synthetic rows as day20_sql.py.
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lessons"))
import lab  # noqa: E402

TOL_PA = 25.0  # how far below setpoint counts as a fault
CONFIRM = 2  # rows (10 minutes at 5-minute spacing)
SIZES = lab.sizes([1_000, 10_000, 100_000, 1_000_000])
N_PARITY = 5_000  # rows per AHU for the row-by-row check
N_FIRST = 20_000 if lab.QUICK else 200_000  # rows for the stop-early experiment
N_CHALLENGE = 5_000 if lab.QUICK else 20_000  # rows per AHU for the challenge


# 1. The plain Python state machine: only streak_len survives from one row to the next.
def loop_rule(d):
    """d is sorted by (equipment_id, ts). Returns (per-row fault flags, fault_rows, episodes)."""
    flags = []
    cur_eq = prev_raw = None
    streak_len = fault_rows = episodes = 0
    for eq, fan, static, sp in zip(
        d.equipment_id, d.fan_status, d.duct_static, d.duct_static_sp, strict=True
    ):
        if eq != cur_eq:  # a new AHU: reset the state, as PARTITION BY does for SQL
            cur_eq, prev_raw, streak_len = eq, None, 0
        raw = 1 if fan == 1 and static < sp - TOL_PA else 0
        streak_len = streak_len + 1 if raw == prev_raw else 1
        prev_raw = raw
        fault = 1 if raw == 1 and streak_len >= CONFIRM else 0
        fault_rows += fault
        episodes += 1 if fault and streak_len == CONFIRM else 0  # the row where a streak confirms
        flags.append(fault)
    return flags, fault_rows, episodes


# 2. pandas: Day 14's column trick. A new streak starts where raw changes; cumsum numbers them.
def pandas_rule(d):
    """d is sorted by (equipment_id, ts). Returns (per-row fault Series, fault_rows, episodes)."""
    raw = ((d.fan_status == 1) & (d.duct_static < d.duct_static_sp - TOL_PA)).astype(int)
    eq = d.equipment_id
    streak = raw.ne(raw.groupby(eq).shift()).astype(int).groupby(eq).cumsum()
    length = raw.groupby([eq, streak]).cumcount() + 1
    fault = ((raw == 1) & (length >= CONFIRM)).astype(int)
    episodes = int(((raw == 1) & (length == CONFIRM)).sum())
    return fault, int(fault.sum()), episodes


# 3. Parity row by row, on two AHUs (so the reset / partition matters)
df2 = lab.synthetic_history(N_PARITY, equips=2)
flags_loop, loop_faults, loop_eps = loop_rule(df2)
fault_pd, pd_faults, pd_eps = pandas_rule(df2)
per_row = df2[["equipment_id", "ts"]].assign(fault=fault_pd)
print(
    f"two AHUs x {N_PARITY:,} rows: loop {loop_faults} / {loop_eps}, pandas {pd_faults} / {pd_eps}"
)
print("loop and pandas flag the same rows:", flags_loop == fault_pd.tolist())

# 4. The showdown: time both as the data grows 10x per step (one AHU)
timing, totals = [], []
for n in SIZES:
    d = lab.synthetic_history(n)
    reps = 3 if n <= 100_000 else 1
    _, faults, eps = pandas_rule(d)
    totals.append({"rows": n, "fault_rows": faults, "episodes": eps})
    timing.append(
        {
            "rows": n,
            "loop": lab.best_time(lambda d=d: loop_rule(d), reps),
            "pandas": lab.best_time(lambda d=d: pandas_rule(d), reps),
        }
    )
totals = pd.DataFrame(totals)
t = pd.DataFrame(timing).set_index("rows")
growth = (t / t.shift(1)).dropna()


# 5. Stop early: the loop can return at the first confirmed fault; pandas has to compute every row
#    before you can ask for the first one.
def first_fault_loop(d):
    streak_len, prev_raw = 0, None
    for fan, static, sp, ts in zip(
        d.fan_status, d.duct_static, d.duct_static_sp, d.ts, strict=True
    ):
        raw = 1 if fan == 1 and static < sp - TOL_PA else 0
        streak_len = streak_len + 1 if raw == prev_raw else 1
        prev_raw = raw
        if raw == 1 and streak_len >= CONFIRM:
            return ts  # early exit: the rest of the table is never read
    return None


def first_fault_pandas(d):
    fault, _, _ = pandas_rule(d)
    return int(d.ts[fault == 1].iloc[0])


dn = lab.synthetic_history(N_FIRST)
first_fault = pd.DataFrame({"first_fault_ts": [first_fault_loop(dn)]})
early = {
    "loop, early exit": lab.best_time(lambda: first_fault_loop(dn)),
    "loop, whole table": lab.best_time(lambda: loop_rule(dn)),
    "pandas (computes every row)": lab.best_time(lambda: first_fault_pandas(dn)),
}


# 6. Week 4 challenge, loop and pandas: the longest confirmed episode per AHU, in rows and minutes.
#    An episode is a maximal run of raw-fault rows that lasts at least CONFIRM rows.
def longest_loop(d):
    best = {}
    cur_eq = prev_raw = None
    run = 0
    for eq, fan, static, sp in zip(
        d.equipment_id, d.fan_status, d.duct_static, d.duct_static_sp, strict=True
    ):
        raw = 1 if fan == 1 and static < sp - TOL_PA else 0
        if eq != cur_eq:
            cur_eq, prev_raw, run = eq, None, 0
            best.setdefault(eq, 0)
        run = run + 1 if raw == prev_raw else 1
        prev_raw = raw
        if raw == 1 and run >= CONFIRM:
            best[eq] = max(best[eq], run)
    return pd.DataFrame({"equipment_id": list(best), "longest_rows": list(best.values())})


def longest_pandas(d):
    raw = ((d.fan_status == 1) & (d.duct_static < d.duct_static_sp - TOL_PA)).astype(int)
    eq = d.equipment_id
    streak = raw.ne(raw.groupby(eq).shift()).astype(int).groupby(eq).cumsum()
    runs = raw.groupby([eq, streak]).agg(["first", "size"])  # one row per streak
    episodes = runs[(runs["first"] == 1) & (runs["size"] >= CONFIRM)]["size"]
    return episodes.groupby("equipment_id").max().rename("longest_rows").reset_index()


dc = lab.synthetic_history(N_CHALLENGE, equips=2)
longest_l, longest_p = longest_loop(dc), longest_pandas(dc)
longest = longest_p.assign(longest_min=longest_p.longest_rows * 5.0)

RESULTS = {
    "per_row": per_row,
    "totals_by_size": totals,
    "first_fault": first_fault,
    "longest_episode": longest,
}

print("\nFC1 totals at every size (the SQL script finds the same numbers):")
print(totals.to_string(index=False))
print("\nseconds (times vary by machine; read the shape, not the digits)")
print(t.map(lambda x: f"{x:,.4g}").to_string())
print("\ngrowth: time at this size / time at the previous (10x smaller) size")
print(growth.round(1).to_string())
print(f"\nFirst confirmed fault in {N_FIRST:,} rows: ts {first_fault.first_fault_ts[0]}")
for name, secs in early.items():
    print(f"  {name:<30} {secs:.4f} s")
print(f"\nLongest confirmed episode per AHU ({N_CHALLENGE:,} rows each):")
print(longest.to_string(index=False))
print("\nchecks (printed, not asserted):")
print("  longest episode, loop == pandas:", longest_l.equals(longest_p))
print("  first fault, loop == pandas:", first_fault_loop(dn) == first_fault_pandas(dn))
big = t.iloc[-1]
print(f"  at {t.index[-1]:,} rows: loop {big['loop']:.3f} s, pandas {big['pandas']:.3f} s")
print("  loop is slower than pandas at the largest size:", bool(big["loop"] > big["pandas"]))
