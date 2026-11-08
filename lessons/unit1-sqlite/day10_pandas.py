"""Day 10, pandas: Open-FDD's results. Episodes per rule, then tag each row with its episode.

    uv run python lessons/unit1-sqlite/day10_pandas.py

`fdd_events.csv` holds one row per fault *episode* (start, end, rule). The interval join asks, for
each 5-minute history row: which episode(s) is this timestamp inside? Two pandas answers: binary
search with np.searchsorted (counts all episodes, even overlapping ones) and merge_asof (the
latest-starting episode).
Compare the printout with day10_sql.py: the numbers should match.
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"

RULE = "fc13"  # which Open-FDD rule to tag the rows with
EPOCH = pd.Timestamp("1970-01-01", tz="UTC")


def seconds(text: pd.Series) -> pd.Series:
    """ISO text -> seconds since 1970 (a number compares and sorts cheaply)."""
    return (pd.to_datetime(text, utc=True) - EPOCH).dt.total_seconds()


# 1. Load: Open-FDD's episodes for both AHUs, and the history timestamps
events = pd.concat(
    [pd.read_csv(DATA / e / "fdd_events.csv") for e in ("AHU_1", "AHU_2")], ignore_index=True
)
events["equipment_id"] = events["hvac_system"].str.replace("bld_50_", "", regex=False)
events["start_sec"] = seconds(events["start_time_utc"])
events["end_sec"] = seconds(events["end_time_utc"])

frames = []
for equip in ("AHU_1", "AHU_2"):
    df = pd.read_csv(DATA / equip / "history_wide.csv", usecols=["timestamp_utc"])
    df.insert(0, "equipment_id", equip)
    frames.append(df)
h = pd.concat(frames, ignore_index=True)
h["ts_sec"] = seconds(h["timestamp_utc"])

# 2. Episodes and hours per rule: GROUP BY two keys
rule_summary = (
    events.groupby(["equipment_id", "rule_name"])
    .agg(episodes=("rule_name", "size"), duration_min=("duration_min", "sum"))
    .assign(hours=lambda d: d["duration_min"] / 60)
    .drop(columns="duration_min")
    .reset_index()
)

# 3. Interval join, version 1: how many episodes of RULE is each row inside? (start <= t <= end)
#    Sort the starts and the ends once. #(start <= t) - #(end < t) = episodes containing t.
#    Two binary searches per row: O((n + E) log E) overall.
fc = events[events["rule_name"] == RULE]
open_count = pd.Series(0, index=h.index, dtype="int64")
for equip, rows in h.groupby("equipment_id"):
    ev = fc[fc["equipment_id"] == equip]
    starts, ends = np.sort(ev["start_sec"].to_numpy()), np.sort(ev["end_sec"].to_numpy())
    t = rows["ts_sec"].to_numpy()
    open_count.loc[rows.index] = np.searchsorted(starts, t, side="right") - np.searchsorted(
        ends, t, side="left"
    )

# 4. Interval join, version 2: merge_asof = "the latest episode that started at or before this row",
#    then keep it only if it has not ended yet. It gives ONE episode per row, so with overlapping
#    episodes it can miss a row that an earlier, longer episode still covers.
asof = pd.merge_asof(
    h.sort_values("ts_sec"),
    fc[["equipment_id", "start_sec", "end_sec", "start_time_utc"]].sort_values("start_sec"),
    left_on="ts_sec",
    right_on="start_sec",
    by="equipment_id",
)
asof["latest_start"] = asof["start_time_utc"].where(asof["ts_sec"] <= asof["end_sec"], None)
tagged = (
    h[["equipment_id", "timestamp_utc"]]
    .assign(episodes_open=open_count)
    .merge(
        asof[["equipment_id", "timestamp_utc", "latest_start"]],
        on=["equipment_id", "timestamp_utc"],
    )
    .sort_values(["equipment_id", "timestamp_utc"], ignore_index=True)
)

# 5. Rows covered vs episode hours. 5-minute rows x 5 / 60 = hours the rule was "open"
tagged_summary = (
    tagged.assign(
        covered=tagged["episodes_open"] > 0,
        asof_hit=tagged["latest_start"].notna(),
    )
    .assign(missed_by_asof=lambda d: d["covered"] & ~d["asof_hit"])
    .groupby("equipment_id")
    .agg(
        rows=("timestamp_utc", "size"),
        rows_in_episode=("covered", "sum"),
        max_open=("episodes_open", "max"),
        rows_missed_by_asof=("missed_by_asof", "sum"),
    )
    .assign(covered_h=lambda d: d["rows_in_episode"] * 5 / 60)
    .reset_index()
)
episode_h = rule_summary[rule_summary["rule_name"] == RULE][["equipment_id", "hours"]]
tagged_summary = tagged_summary.merge(
    episode_h.rename(columns={"hours": "episode_hours_summed"}), on="equipment_id"
)

RESULTS = {"rule_summary": rule_summary, "tagged": tagged, "tagged_summary": tagged_summary}

print("Open-FDD episodes and hours per rule:")
print(rule_summary.round(1).to_string(index=False))
print(f"\nEvery 5-minute row tagged with its {RULE} episodes:")
print(tagged_summary.round(1).to_string(index=False))
print(tagged[tagged["episodes_open"] > 0].head(3).to_string(index=False))

# Timing (not part of RESULTS): the same count by brute force (compare every row with every
#    episode).
sub = h[h["equipment_id"] == "AHU_1"]
ev = fc[fc["equipment_id"] == "AHU_1"]
t0 = time.perf_counter()
t = sub["ts_sec"].to_numpy()[:, None]
brute = ((ev["start_sec"].to_numpy() <= t) & (t <= ev["end_sec"].to_numpy())).sum(axis=1)
t_brute = time.perf_counter() - t0
t0 = time.perf_counter()
tt = sub["ts_sec"].to_numpy()
fast = np.searchsorted(np.sort(ev["start_sec"].to_numpy()), tt, "right") - np.searchsorted(
    np.sort(ev["end_sec"].to_numpy()), tt, "left"
)
t_fast = time.perf_counter() - t0
print(f"\nbrute force, {len(sub):,} rows x {len(ev)} episodes: {t_brute * 1000:6.1f} ms")
print(f"binary search, same answer ({(brute == fast).all()}):   {t_fast * 1000:6.1f} ms")
