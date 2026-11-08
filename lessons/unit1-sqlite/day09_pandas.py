"""Day 9, pandas: time buckets. Hourly and daily averages, recompute vs compute once.

    uv run python lessons/unit1-sqlite/day09_pandas.py

A bucket is "which hour (day) does this 5-minute row belong to". pandas has three ways to say it:
`dt.floor` + `groupby`, `resample`, or plain integer division. SQL's `strftime` and
`unixepoch()/3600` map to them.
Compare the printout with day09_sql.py: the numbers should match.
"""

import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "BUILDING_50"

PA_PER_INH2O = 249.08891  # Day 6: the historian logged inches of water; fault math is SI
EPOCH = pd.Timestamp("1970-01-01", tz="UTC")

# 1. Load + stack both AHUs
COLUMNS = ["timestamp_utc", "outside_air_temp_f", "da_p_inwc", "supply_fan_status"]
frames = []
for equip in ("AHU_1", "AHU_2"):
    df = pd.read_csv(DATA / equip / "history_wide.csv", usecols=COLUMNS)
    df.insert(0, "equipment_id", equip)
    frames.append(df)
h = pd.concat(frames, ignore_index=True)

# 2. SI units, and real timestamps (the CSV holds text; floor/resample need datetimes)
h["ts"] = pd.to_datetime(h["timestamp_utc"], utc=True)
h["outside_air_temp_c"] = (h["outside_air_temp_f"] - 32) * 5 / 9
h["duct_static_pa"] = h["da_p_inwc"] * PA_PER_INH2O
h["static_running_pa"] = h["duct_static_pa"].where(
    h["supply_fan_status"] == 1
)  # NaN when the fan is off


# 3. Hourly: floor each timestamp to its hour, then group
def summarize(df: pd.DataFrame, bucket: pd.Series, name: str) -> pd.DataFrame:
    return (
        df.groupby(["equipment_id", bucket.rename(name)])
        .agg(
            rows=("ts", "size"),
            mean_oa_c=("outside_air_temp_c", "mean"),
            mean_static_running_pa=(
                "static_running_pa",
                "mean",
            ),  # mean skips NaN, like avg() skips NULL
            fan_on_fraction=("supply_fan_status", "mean"),
        )
        .reset_index()
    )


hourly = summarize(h, h["ts"].dt.floor("h"), "hour_start")

# 4. Daily: the same, with the date as the bucket
daily = summarize(h, h["ts"].dt.strftime("%Y-%m-%d"), "day")

# 5. The same hourly buckets two other ways: resample, and integer division (hours since 1970)
resampled = h.set_index("ts").groupby("equipment_id")["outside_air_temp_c"].resample("h").mean()
hour_int = (h["ts"] - EPOCH).dt.total_seconds() // 3600  # hours since 1970, like unixepoch() / 3600
bucket_check = pd.DataFrame(
    {
        "hour_buckets_floor": h.groupby("equipment_id")["ts"].apply(
            lambda s: s.dt.floor("h").nunique()
        ),
        "hour_buckets_int": hour_int.groupby(h["equipment_id"]).nunique(),
    }
).reset_index()

# 6. One day of the hourly table: what a dashboard asks for
july1 = hourly[
    (hourly.equipment_id == "AHU_1") & (hourly.hour_start.dt.strftime("%Y-%m-%d") == "2026-07-01")
]

RESULTS = {"hourly": hourly, "daily": daily, "bucket_check": bucket_check, "ahu_1_july_1": july1}

print("Hourly averages, first rows (AHU_1):")
print(hourly[hourly.equipment_id == "AHU_1"].head(3).round(2).to_string(index=False))
print("\nDaily averages, first rows (AHU_1):")
print(daily[daily.equipment_id == "AHU_1"].head(3).round(2).to_string(index=False))
print(f"\nhourly rows: {len(hourly):,}, daily rows: {len(daily):,}")
print("\nSame hourly buckets by floor and by integer division:")
print(bucket_check.to_string(index=False))
same = resampled.dropna().to_numpy()
print(f"hourly means: {hourly['mean_oa_c'].notna().sum():,}  (resample gives {len(same):,})")
print("\nAHU_1, 2026-07-01, mean outside air by hour (C):")
print(july1.set_index(july1["hour_start"].dt.strftime("%H:%M"))["mean_oa_c"].round(1).to_string())

# Timing (not part of RESULTS): view = compute on every read; summary table = compute once.
READS = 10


def hourly_view() -> pd.DataFrame:  # "a view": rebuild the summary every time someone asks
    return summarize(h, h["ts"].dt.floor("h"), "hour_start")


t0 = time.perf_counter()
for _ in range(READS):
    hourly_view().query("equipment_id == 'AHU_1'")["mean_oa_c"].agg(["mean", "max"])
t_view = time.perf_counter() - t0
t0 = time.perf_counter()
for _ in range(READS):
    hourly.query("equipment_id == 'AHU_1'")["mean_oa_c"].agg(["mean", "max"])
t_table = time.perf_counter() - t0
print(f"\n{READS} reads, recompute each time:   {t_view * 1000:8.1f} ms")
print(f"{READS} reads, compute once and keep: {t_table * 1000:8.1f} ms")
