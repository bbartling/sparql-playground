# Day 6 — Units and SI: convert once, then do all fault math in °C, Pa and fractions

**Goal:** turn the BAS's US-unit columns into SI (°C, pascals, fractions 0–1) in a few lines of pandas and one SQL
query, and avoid the one conversion mistake everybody makes: converting a temperature *difference*.

## Read

The CSV is what the building automation system (BAS) logged: temperatures in °F, pressures in inches of water
(inH2O), valve and fan speeds in percent 0–100. **Open-FDD's fault math is SI-only**: °C (or K for differences),
pascals, and fractions 0–1. There are two reasons:

1. **One set of thresholds.** Rules ship with numbers like "25 Pa" or "2 K". If every site could feed °F one day and
   °C the next, every rule would need a unit switch. Instead the *ingest* step converts, and the rules never see US
   units.
2. **Fewer silent bugs.** A rule that compares `percent` to `0.95` is wrong by 100× and never throws an error. If
   everything is a fraction, "95%" is `0.95` everywhere.

So the first step of every rule is a conversion. Every script from here on starts with it.

| Quantity | CSV unit → SI | Formula |
|---|---|---|
| temperature (absolute) | °F → °C | `(F - 32) * 5 / 9` |
| temperature (difference) | °F → K | `F * 5 / 9` (**no 32**) |
| static pressure | inH2O → Pa | `inwc * 249.08891` |
| valve, damper, fan speed | percent → fraction | `pct / 100` |

**The delta trap.** The 32 in `(F - 32) * 5 / 9` exists because 0 °F and 0 °C are different *places* on the scale.
A *difference* has no zero point to shift: a 5 °F rise is a 5 × 5/9 = **2.78 K** rise. Push it through the absolute
formula and you get `(5 - 32) * 5 / 9 = -15`, a cooling of 15 degrees. It's a typo-sized mistake that turns a
"DAT is 5 °F over setpoint" check into nonsense. The scripts average the discharge-air-temperature error (discharge
air minus its setpoint) both ways, the right way and the wrong way.

Conversions of this kind are linear, so the mean of the converted column equals the converted mean. That's a
cheap sanity check, but only for linear conversions.

In pandas each conversion is one line that makes a new column (`df["outside_air_temp_c"] = (df["outside_air_temp_f"]
- 32) * 5 / 9`). In SQL the same arithmetic goes inside `AVG(...)`. Watch the `/ 9.0` and `/ 100.0` in SQL: SQLite
divides integers as integers (`5 / 9` is `0`), so one number must be a float. pandas always does true division.

## Run

```bash
uv run python lessons/course.py run 6
```

That runs [`day06_pandas.py`](day06_pandas.py), then [`day06_sql.py`](day06_sql.py). Both print:

```
Average discharge air temperature (C): 16.206
Average outside air temperature (C):   16.265
Average duct static pressure (Pa):     195.035
Average supply fan speed (fraction):   0.39
Average DAT error, right (K):          6.782
Average DAT error, wrong (K):          -10.996
```

The right and wrong DAT errors differ by 17.8 K, which is 32 × 5/9: the shift the absolute formula adds.

A SQL *view* (`CREATE VIEW ahu_1_si AS SELECT ...`) would store these conversions once so every later query could
reuse them; Day 9's Read section says more about views. Here one query is enough.

## Try it

1. Add the mixed-air temperature, `mixed_air_temp_f` → °C, to both scripts. Is the mean what you expect next to the
   discharge and outside air means? (In pandas, add the column to `columns` first.)
2. A rule says "fault if discharge air is more than 5 K above its setpoint". Count the rows where the right DAT error
   is above 5 K and where the wrong one is. In pandas: `(dat_error_k > 5).sum()`; in SQL:
   `SUM((discharge_air_temp_f - dat_reset_f) * 5 / 9.0 > 5)`. And if the threshold were written as 9 °F, what do
   you compare against?

<details><summary>Answers</summary>

1. SQL: `AVG((mixed_air_temp_f - 32) * 5 / 9.0)`; pandas: `df["mixed_air_temp_c"] = (df["mixed_air_temp_f"] - 32) *
   5 / 9`.
2. The right error is above 5 K in 16,488 rows (about 46% of the history). The wrong one only in 2,058, because it
   is shifted by about −17.8 K. A 9 °F threshold is itself a *difference*, so convert it as `9 * 5 / 9 = 5 K`:
   multiply, don't subtract 32.

</details>

## Why it matters

Every fault threshold from here on is written in SI, so every script from here on starts with the conversion you
wrote today. If the conversion is wrong, every fault count downstream is wrong in a way no test on the *rule* will
catch. Week 5 moves the unit into the data model (each point says what unit it logs), so a rule can ask for "duct
static in Pa" and the conversion is looked up, not typed.
