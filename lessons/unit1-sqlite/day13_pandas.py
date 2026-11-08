"""Day 13, pandas: streaks ("gaps and islands") with the cumsum trick.

    uv run python lessons/unit1-sqlite/day13_pandas.py

Two questions: what is the longest continuous run of the supply fan on each AHU, and when has the
fan been at (nearly) full speed for 30 minutes (6 rows) in a row? Each is a streak problem. The
trick: mark the rows where the value changes, cumulatively sum the marks to number the streaks,
then count rows inside each streak.
A second route to "true for N rows in a row" (a rolling sum) is checked against it.
Compare the printout with day13_sql.py: the numbers should match.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"

FULL_SPEED_PCT = 95.0  # "at or near full speed"
CONFIRM_ROWS = 6  # 6 rows x 5 min = 30 minutes

# 1. Load: both AHUs, the columns we need, in (equipment, time) order.
COLUMNS = ["timestamp_utc", "supply_fan_status", "supply_fan_speed_pct"]
frames = []
for equip in ("AHU_1", "AHU_2"):
    df = pd.read_csv(DATA / equip / "history_wide.csv", usecols=COLUMNS)
    df.insert(0, "equipment_id", equip)
    frames.append(df)
h = pd.concat(frames, ignore_index=True)
h = h.sort_values(["equipment_id", "timestamp_utc"], ignore_index=True)
eq = h["equipment_id"]


def streaks(value):
    """Number the runs of equal consecutive values per AHU, and the row position inside each run.

    1) new_streak = 1 where the value differs from the previous row (an AHU's first row starts one);
    2) streak_id = running sum of new_streak, so every row in a run shares one id;
    3) streak_len = 1, 2, 3, ... inside each (AHU, streak).
    """
    new_streak = value.ne(value.groupby(eq).shift()).astype(int)
    streak_id = new_streak.groupby(eq).cumsum()
    streak_len = value.groupby([eq, streak_id]).cumcount() + 1
    return streak_id, streak_len


# 2. Fan runs: streaks of supply_fan_status, keeping the ones where the fan is on (status 1).
run_id, run_len = streaks(h["supply_fan_status"])
rows = h[["equipment_id", "timestamp_utc", "supply_fan_status"]].assign(
    run_id=run_id, run_len=run_len
)
on = rows[rows["supply_fan_status"] == 1]
fan_runs = (
    on.groupby(["equipment_id", "run_id"])
    .agg(
        start_utc=("timestamp_utc", "min"),
        end_utc=("timestamp_utc", "max"),
        rows=("run_len", "max"),
    )
    .reset_index()
)
fan_runs["hours"] = fan_runs["rows"] * 5 / 60

# 3. The longest run per AHU (ties: the earliest). Sort, then take the first row of each group.
longest = (
    fan_runs.sort_values(["equipment_id", "rows", "start_utc"], ascending=[True, False, True])
    .groupby("equipment_id")
    .head(1)
    .rename(
        columns={"rows": "longest_rows", "hours": "longest_hours", "start_utc": "longest_start"}
    )
)
run_summary = (
    fan_runs.groupby("equipment_id")
    .agg(runs=("run_id", "size"), avg_run_hours=("hours", "mean"))
    .join(longest.set_index("equipment_id")[["longest_rows", "longest_hours", "longest_start"]])
    .reset_index()
)

# 4. Confirmation: "full speed for 6 rows in a row". Same trick, on a 0/1 raw flag.
raw = ((h["supply_fan_status"] == 1) & (h["supply_fan_speed_pct"] >= FULL_SPEED_PCT)).astype(int)
raw_id, raw_len = streaks(raw)
confirmed_streak = ((raw == 1) & (raw_len >= CONFIRM_ROWS)).astype(int)

# 5. The other route: a rolling sum over the last 6 rows equals 6 only if all six were 1.
rolling = raw.groupby(eq).transform(lambda s: s.rolling(CONFIRM_ROWS).sum())
confirmed_window = (rolling == CONFIRM_ROWS).astype(int)

confirm = h[["equipment_id", "timestamp_utc"]].assign(
    raw=raw, streak_id=raw_id, streak_len=raw_len,
    confirmed_streak=confirmed_streak, confirmed_window=confirmed_window,
)  # fmt: skip
confirm_summary = (
    confirm.groupby("equipment_id")
    .agg(
        raw_rows=("raw", "sum"),
        confirmed_rows_streak=("confirmed_streak", "sum"),
        confirmed_rows_window=("confirmed_window", "sum"),
    )
    .join(
        confirm[confirm["confirmed_streak"] == 1]
        .groupby("equipment_id")["streak_id"]
        .nunique()
        .rename("episodes")
    )
    .fillna({"episodes": 0})
    .reset_index()
)

RESULTS = {
    "fan_runs": fan_runs,
    "run_summary": run_summary,
    "confirm_rows": confirm,
    "confirm_summary": confirm_summary,
}

print("Fan runs per AHU (status = 1 streaks):")
print(run_summary.round(2).to_string(index=False))
print("\nFull speed (>= 95 %) for 6 rows in a row, by streak id and by rolling sum:")
print(confirm_summary.to_string(index=False))
