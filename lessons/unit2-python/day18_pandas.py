"""Day 18, pandas side: FC1 with sample-and-hold, a gap limit and coverage, on data with holes.

    uv run python lessons/unit2-python/day18_pandas.py

Day 14 counted rows and multiplied by 5 minutes. With dropped rows that is wrong. Here each reading
holds until the next one arrives (`held_seconds = next_ts - ts`), a gap longer than MAX_GAP_HOURS is
"unknown" (held 0, the streak breaks), a fault confirms after CONFIRM_SECONDS of elapsed time, and
coverage says how much of the window we could vouch for.

This script has the vectorized pandas version and the plain Python loop (one forward pass with four
pieces of state). Both run on the same synthetic gappy rows as day18_sql.py.
"""

import contextlib
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lessons"))
import lab  # noqa: E402

TOL_PA = 25.0  # how far below setpoint counts as a fault
MAX_GAP_HOURS = 1.0  # a longer silence is "unknown", not "still faulty"
CONFIRM_SECONDS = 600  # 10 minutes, the same as Day 14's two 5-minute rows
N = 4_000  # rows per AHU before drops: about 14 days

# 1. Data with holes: 3% of rows dropped at random (short gaps of 10-15 minutes), plus one long
#    outage on AHU_1: 100 rows (about 8 hours) deleted from inside its weak-fan window.
raw_df = lab.synthetic_history(N, equips=2, gap_prob=0.03)
T0 = int(raw_df.ts.min())
outage = (raw_df.equipment_id == "AHU_1") & raw_df.ts.between(T0 + 1560 * 300, T0 + 1659 * 300)
gappy = raw_df[~outage].sort_values(["equipment_id", "ts"]).reset_index(drop=True)
steps = gappy.groupby("equipment_id").ts.diff().dropna()
print(f"{len(gappy):,} rows (of {2 * N:,}); seconds between rows:")
print(steps.value_counts().sort_index().to_dict())

COLUMNS = ["equipment_id", "ts", "raw_fault", "held_seconds", "gap_after", "streak_id"]
COLUMNS += ["streak_elapsed", "confirmed"]


# 2. pandas: every step a column operation. shift(-1) inside a groupby is LEAD; shift() is LAG.
def gap_pandas(df, max_gap_h=MAX_GAP_HOURS, confirm_s=CONFIRM_SECONDS, tol=TOL_PA):
    """df sorted by (equipment_id, ts). Returns one row of state per input row."""
    eq = df["equipment_id"]
    raw = ((df.fan_status == 1) & (df.duct_static < df.duct_static_sp - tol)).astype(int)
    dt = df.groupby("equipment_id").ts.shift(-1) - df.ts  # NaN on each equipment's last row
    limit = max_gap_h * 3600.0
    held = pd.Series(np.where((dt > 0) & (dt <= limit), dt, 0.0), index=df.index)  # NaN -> 0
    gap_after = (dt > limit).astype(int)
    prev_gap = gap_after.groupby(eq).shift().fillna(0)
    same = (raw == raw.groupby(eq).shift()) & (prev_gap == 0)  # first row: NaN -> False -> new
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
    cols = ["rows", "long_gaps", "fault_hours", "covered_hours", "window_hours", "coverage"]
    return out[cols].reset_index()


rows_pd = gap_pandas(gappy)
summary = summarize(rows_pd)


# 3. Plain Python: a single forward pass. State: previous raw flag, whether the previous row ended
#    in a gap, the streak number and the running elapsed time. The only look-ahead is the next
#    row's timestamp.
def gap_loop(df, max_gap_h=MAX_GAP_HOURS, confirm_s=CONFIRM_SECONDS, tol=TOL_PA):
    data = list(
        df[["equipment_id", "ts", "fan_status", "duct_static", "duct_static_sp"]].itertuples(
            index=False, name=None
        )
    )
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
    rows = pd.DataFrame(out, columns=COLUMNS)
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


rows_loop, summary_loop = gap_loop(gappy)


def same(a, b):
    """True if two frames hold the same values (row order and dtypes ignored)."""
    try:
        with contextlib.redirect_stdout(io.StringIO()):  # assert_parity prints on success
            lab.assert_parity(a, b, label="")
    except AssertionError:
        return False
    return True


# 4. The wrong way: Day 14's row-counting version on the same gappy rows
raw = ((gappy.fan_status == 1) & (gappy.duct_static < gappy.duct_static_sp - TOL_PA)).astype(int)
eq = gappy.equipment_id
streak = raw.ne(raw.groupby(eq).shift()).astype(int).groupby(eq).cumsum()
length = raw.groupby([eq, streak]).cumcount() + 1
naive_rows = ((raw == 1) & (length >= 2)).groupby(eq).sum()
naive = (naive_rows * 5 / 60.0).rename("naive_fault_hours").reset_index()

# 5. Try-it variants: a 12-hour gap limit, and confirming over 1 hour
summary_12h = summarize(gap_pandas(gappy, max_gap_h=12.0))
summary_confirm_1h = summarize(gap_pandas(gappy, confirm_s=3600))

RESULTS = {
    "rows": rows_pd,
    "summary": summary,
    "naive_fault_hours": naive,
    "summary_12h_limit": summary_12h,
    "summary_confirm_1h": summary_confirm_1h,
}

print("\nGap-aware summary (loop and pandas give the same table):")
print(summary.round(3).to_string(index=False))
print("\nThe one row with gap_after = 1 per AHU that has an outage:")
print(rows_pd[rows_pd.gap_after == 1].round(1).to_string(index=False))

cmp = naive.merge(summary[["equipment_id", "fault_hours"]], on="equipment_id")
cmp["difference_h"] = cmp.fault_hours - cmp.naive_fault_hours
print("\nRow counting (Day 14) vs gap-aware, fault hours:")
print(cmp.round(2).to_string(index=False))

print("\nTry-it variants (fault hours / coverage):")
print("MAX_GAP_HOURS = 12:")
print(
    summary_12h[["equipment_id", "long_gaps", "fault_hours", "coverage"]]
    .round(3)
    .to_string(index=False)
)
print("CONFIRM_SECONDS = 3600:")
print(summary_confirm_1h[["equipment_id", "fault_hours"]].round(2).to_string(index=False))

print("\nchecks (printed, not asserted):")
print("  loop rows == pandas rows:", same(rows_loop, rows_pd))
print("  loop summary == pandas summary:", same(summary_loop, summary))
s = summary.set_index("equipment_id")
print("  AHU_2 (short drops only) coverage:", round(s.loc["AHU_2", "coverage"], 6))
print("  AHU_1 (with the 8 h outage) coverage:", round(s.loc["AHU_1", "coverage"], 6))
long_gap_s = steps[steps > MAX_GAP_HOURS * 3600].groupby(gappy.equipment_id).sum()
window_s = gappy.groupby("equipment_id").ts.agg(lambda x: x.max() - x.min())
print(
    "  AHU_1 covered hours:",
    round(s.loc["AHU_1", "covered_hours"], 3),
    "= window minus long gaps:",
    round((window_s["AHU_1"] - long_gap_s["AHU_1"]) / 3600.0, 3),
)
