"""Day 19, pandas side: the as-of join (latest weather at or before each row) and a weather rule.

    uv run python lessons/unit2-python/day19_pandas.py

Each 5-minute AHU row gets the most recent weather reading at or before its time, but only if that
reading is at most TOL_S old (otherwise: unknown). pandas does it with `merge_asof`; plain Python
with a sorted list and binary search (`bisect`) or a nested loop. Then an OAT-METEO style rule: flag
the AHU while its fan runs and its outdoor sensor differs from the weather by more than DIFF_C.

AHU rows come from the Building 50 CSVs. The weather is a stand-in feed made from AHU_1's own
outdoor sensor (see make_weather). The timing section uses synthetic rows so the size can grow.
Compare with day19_sql.py.
"""

import sys
from bisect import bisect_right
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"
sys.path.insert(0, str(ROOT / "lessons"))
import lab  # noqa: E402

TOL_S = 2 * 3600  # weather older than this is stale
DIFF_C = 3.0  # sensor-vs-weather disagreement, degrees C
CONFIRM_ROWS = 6  # 6 x 5 min = 30 minutes
STEP_H = 5 / 60  # one row = 5 minutes, in hours


def make_weather(ts, temp_c, seed=3):
    """A stand-in weather feed: hourly means of a sensor (+ 0.5 C noise), with some hours missing.

    Real weather never matches a sensor exactly, and real feeds have failures: 12% of the hours are
    deleted and one 6-hour block is missing. In production this table is the Open-Meteo feed.
    """
    rng = np.random.default_rng(seed)
    hour = (np.asarray(ts) // 3600) * 3600
    wx = pd.DataFrame({"ts": hour, "t": np.asarray(temp_c)}).groupby("ts").t.mean()
    wx = wx.rename("wx_oat").reset_index()
    wx["wx_oat"] = (wx.wx_oat + rng.normal(0, 0.5, len(wx))).round(2)
    wx = wx[rng.random(len(wx)) >= 0.12]
    return wx[~wx.index.isin(range(len(wx) // 2, len(wx) // 2 + 6))].reset_index(drop=True)


# 1. Load: both AHUs' CSVs, only the columns we need. Weeks 1-4 hard-code the column names.
COLUMNS = ["timestamp_utc", "supply_fan_status", "outside_air_temp_f"]
frames = []
for equip in ("AHU_1", "AHU_2"):
    f = pd.read_csv(DATA / equip / "history_wide.csv", usecols=COLUMNS)
    f.insert(0, "equipment_id", equip)
    frames.append(f)
ahu = pd.concat(frames, ignore_index=True)
ahu["ts"] = pd.to_datetime(ahu["timestamp_utc"], utc=True).dt.as_unit("s").astype("int64")
ahu["oat_c"] = (
    (ahu["outside_air_temp_f"] - 32.0) * 5.0 / 9.0
)  # the CSV is in degF; fault math is SI
ahu = ahu.rename(columns={"supply_fan_status": "fan_status"})
ahu = ahu[["equipment_id", "ts", "oat_c", "fan_status"]]

# 2. The stand-in weather feed, from AHU_1's own sensor
a1 = ahu[ahu.equipment_id == "AHU_1"]
wx = make_weather(a1.ts, a1.oat_c)
print(f"{len(ahu):,} AHU rows, {len(wx):,} weather rows (of {len(a1) * 300 // 3600:,} hours)")


# 3. The as-of join. merge_asof needs both sides sorted by the key. Our table has two AHUs
#    interleaved by time, so sort by ts for the merge. wx_ts shows which weather row matched.
def join_pandas(ahu, wx, tol_s=TOL_S):
    left = ahu.sort_values("ts", kind="mergesort")
    right = wx.assign(wx_ts=wx.ts).sort_values("ts")
    out = pd.merge_asof(left, right, on="ts", direction="backward", tolerance=tol_s)
    return out[["equipment_id", "ts", "oat_c", "fan_status", "wx_ts", "wx_oat"]]


asof_join = join_pandas(ahu, wx)
print(asof_join.sort_values(["equipment_id", "ts"]).head(3).to_string(index=False))
print("rows with no usable weather:", int(asof_join.wx_ts.isna().sum()))


# 4. Sensor-versus-weather rule. No weather (stale or missing) means unknown, so no fault. The
#    confirmation is Day 14's streak machinery: streak ids by cumsum, rows inside by cumcount.
def rule_pandas(joined, diff_c=DIFF_C, confirm=CONFIRM_ROWS):
    j = joined.sort_values(["equipment_id", "ts"]).reset_index(drop=True)
    eq = j.equipment_id
    raw = ((j.fan_status == 1) & j.wx_oat.notna() & ((j.oat_c - j.wx_oat).abs() > diff_c)).astype(
        int
    )
    streak = raw.ne(raw.groupby(eq).shift()).astype(int).groupby(eq).cumsum()
    length = raw.groupby([eq, streak]).cumcount() + 1
    fault = ((raw == 1) & (length >= confirm)).astype(int)
    return j[["equipment_id", "ts", "wx_oat"]].assign(raw_fault=raw, streak_id=streak, fault=fault)


rule = rule_pandas(asof_join)
rule_hours = (
    rule.groupby("equipment_id")
    .agg(fault_rows=("fault", "sum"), raw_rows=("raw_fault", "sum"))
    .assign(fault_hours=lambda d: d.fault_rows * STEP_H)
    .reset_index()
)

# 5. Try it 1: tighten the tolerance to 1 hour. How many rows lose their weather?
no_weather = pd.DataFrame(
    [
        {"tol_s": t, "rows_without_weather": int(join_pandas(ahu, wx, t).wx_ts.isna().sum())}
        for t in (TOL_S, 3600)
    ]
)


# 6. Two ways in plain Python. The nested loop is what a database does with no index; the bisect
#    version is the same idea as an index: keep the weather timestamps sorted and binary-search.
def nested_loop(ts_list, wx_ts_list, tol_s=TOL_S):
    out = []
    for ts in ts_list:
        best = None
        for w in wx_ts_list:  # scans every weather row: O(M) per AHU row
            if w <= ts and (best is None or w > best):
                best = w
        out.append(best if best is not None and ts - best <= tol_s else None)
    return out


def bisect_loop(ts_list, wx_ts_list, tol_s=TOL_S):
    out = []
    for ts in ts_list:
        i = bisect_right(wx_ts_list, ts) - 1  # O(log M); wx_ts_list must be sorted
        out.append(wx_ts_list[i] if i >= 0 and ts - wx_ts_list[i] <= tol_s else None)
    return out


ts_list, wx_ts_list = ahu.ts.tolist(), sorted(wx.ts.tolist())
bisect_ts = pd.Series(bisect_loop(ts_list, wx_ts_list), dtype="float64")
key = pd.MultiIndex.from_arrays([ahu.equipment_id, ahu.ts])
want = asof_join.set_index(["equipment_id", "ts"]).wx_ts.reindex(key)
bisect_agrees = np.array_equal(bisect_ts.to_numpy(), want.to_numpy(), equal_nan=True)

# 7. Timing on synthetic rows (one AHU; weather one hour per 12 rows). The two O(N*M) methods stop
#    at 10,000 rows; at a million rows they would run for hours. NaN means "not run".
timing, matches = [], []
for n in lab.sizes([1_000, 10_000, 100_000, 1_000_000]):
    d = lab.synthetic_history(n)
    w = make_weather(d.ts, d.oat)
    reps = 3 if n <= 100_000 else 1
    tl, wl = d.ts.tolist(), sorted(w.ts.tolist())
    left = d[["ts"]]
    right = w.assign(wx_ts=w.ts)

    def asof(left=left, right=right):
        return pd.merge_asof(left, right, on="ts", direction="backward", tolerance=TOL_S)

    row = {"N": n, "M": len(w)}
    if n <= 10_000:
        row["nested_s"] = lab.best_time(lambda tl=tl, wl=wl: nested_loop(tl, wl), reps)
    row["bisect_s"] = lab.best_time(lambda tl=tl, wl=wl: bisect_loop(tl, wl), reps)
    row["asof_s"] = lab.best_time(asof, reps)
    timing.append(row)
    matches.append({"N": n, "M": len(w), "matched": int(asof().wx_oat.notna().sum())})
timing = pd.DataFrame(timing).reindex(columns=["N", "M", "nested_s", "bisect_s", "asof_s"])
timing_matches = pd.DataFrame(matches)

RESULTS = {
    "asof_join": asof_join,
    "oat_meteo_hours": rule_hours,
    "rows_without_weather": no_weather,
    "timing_matches": timing_matches,
}

print("\nSensor vs weather rule (fan running, |sensor - weather| > 3 C for 30 minutes):")
print(rule_hours.round(2).to_string(index=False))
print("\nRows without weather by tolerance:")
print(no_weather.to_string(index=False))
print("\nTiming, seconds (nested loop and bisect are plain Python; times vary by machine):")
print(timing.to_string(index=False, float_format=lambda x: f"{x:,.4g}"))
print("\nMatched rows at every size (the SQL script finds the same numbers):")
print(timing_matches.to_string(index=False))
print("\nchecks (printed, not asserted):")
print("  bisect loop finds the same weather row as merge_asof:", bisect_agrees)
