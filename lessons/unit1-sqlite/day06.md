# Day 6 — Units and SI: convert once, then do all fault math in °C, Pa and fractions

**Goal:** turn the BAS's US-unit columns into SI columns (a SQL view, a pandas `assign`), and avoid the one
conversion mistake everybody makes: converting a temperature *difference*.

## Read

The CSV is what the building automation system (BAS) logged: temperatures in °F, pressures in inches of water
(inH2O), valve and fan speeds in percent 0–100. **Open-FDD's fault math is SI-only**: °C (or K for differences),
pascals, and fractions 0–1. There are two reasons:

1. **One set of thresholds.** Rules ship with numbers like "25 Pa" or "2 K". If every site could feed °F one day and
   °C the next, every rule would need a unit switch. Instead the *ingest* step converts, and the rules never see US
   units.
2. **Fewer silent bugs.** A rule that compares `percent` to `0.95` is wrong by 100× and never throws an error. If
   everything is a fraction, "95%" is `0.95` everywhere.

So the first step of every rule is a conversion. You write it **once**, in one place (a view in SQL, a function or
`assign` in pandas), and every later day reuses it.

| Quantity | CSV unit → SI | Formula |
|---|---|---|
| temperature (absolute) | °F → °C | `(F - 32) * 5 / 9` |
| temperature (difference) | °F → K | `F * 5 / 9` (**no 32**) |
| static pressure | inH2O → Pa | `inwc * 249.08891` |
| valve, damper, fan speed | percent → fraction | `pct / 100` |

**The delta trap.** The 32 in `(F - 32) * 5 / 9` exists because 0 °F and 0 °C are different *places* on the scale.
A *difference* has no zero point to shift: a 5 °F rise is a 5 × 5/9 = **2.78 K** rise. Push it through the absolute
formula and you get `(5 - 32) * 5 / 9 = -15`, a cooling of 15 degrees. It's a typo-sized mistake that turns a
"DAT is 5 °F over setpoint" check into nonsense. The scripts build the discharge-air-temperature error three ways:
convert the difference (right), subtract two converted temperatures (right, same numbers), and the wrong one.

Conversions of this kind are linear, so the mean of the converted column equals the converted mean. That's a
cheap sanity check, but only for linear conversions.

| Step | `day06_sql.py` | `day06_pandas.py` |
|---|---|---|
| load | `FROM ahu_1` | `pd.read_csv(..., usecols=COLUMNS)` |
| convert | `CREATE TEMP VIEW ahu_1_si AS SELECT (x - 32) * 5 / 9.0 AS ...` | `raw.assign(x_c=(raw.x_f - 32) * 5 / 9)` |
| percent → fraction | `supply_fan_speed_pct / 100.0` | `raw.supply_fan_speed_pct / 100` |
| delta | `(a_f - b_f) * 5 / 9.0` | `(raw.a_f - raw.b_f) * 5 / 9` |
| mean of every column | one `avg()` per column, `UNION ALL` | `si.mean()` |

Watch the `/ 9.0` and `/ 100.0` in SQL: SQLite divides integers as integers (`5 / 9` is `0`), so one operand must be
a float. pandas always does true division.

## Run

```bash
uv run python lessons/course.py run 6
```

That runs [`day06_pandas.py`](day06_pandas.py), then [`day06_sql.py`](day06_sql.py). Both print:

```
A 5 degF *difference*:
 delta_f  right_k  wrong_k
     5.0     2.78    -15.0
...
Mean of each SI column:
               column    mean
 discharge_air_temp_c  16.206
       dat_setpoint_c   9.424
   outside_air_temp_c  16.265
       duct_static_pa 195.035
    duct_static_sp_pa 340.226
supply_fan_speed_frac   0.390
       chw_valve_frac   0.189
```

A SQL view stores the query, not the rows: every `SELECT` from `ahu_1_si` re-runs the conversion. That costs nothing
for arithmetic on 35,536 rows, and it means the view can't go stale. Day 9 compares views with summary tables.

## Try it

1. Add a column in both scripts for the mixed-air temperature, `mixed_air_temp_f` → °C. Is the mean what you expect
   next to the discharge and outside air means?
2. A rule says "fault if discharge air is more than 5 K above its setpoint". Which of `dat_error_k` and
   `dat_error_wrong` do you compare with 5? How many rows does each flag? And if the threshold were written as
   9 °F, what do you compare against?

<details><summary>Answers</summary>

1. SQL: `(mixed_air_temp_f - 32) * 5 / 9.0 AS mixed_air_temp_c`; pandas: `mixed_air_temp_c=(raw["mixed_air_temp_f"] -
   32) * 5 / 9`. Remember to add the column to `usecols`.
2. `dat_error_k > 5` flags 16,488 rows (about 46% of the history). The wrong column flags only 2,058, because it is
   shifted by about -17 K. A 9 °F threshold is itself a *difference*, so convert it as `9 * 5 / 9 = 5 K`: multiply,
   don't subtract 32.

</details>

## Why it matters

Every fault threshold from here on is written in SI, so every script from here on starts with the conversion you
wrote today. If the conversion is wrong, every fault count downstream is wrong in a way no test on the *rule* will
catch. Week 5 moves the unit into the data model (each point says what unit it logs), so a rule can ask for "duct
static in Pa" and the conversion is looked up, not typed.
