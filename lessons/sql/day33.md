# Day 33 — Integrate kW into observed kWh

[Previous: Day 32](day32.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 34](day34.md)

**Week 5 · 45–75 minutes.** Prerequisites: Days 1–32, or equivalent SQL skills.

## Goal

Calculate electrical energy from bounded power intervals and explain the effect of one bad reading.

## Before you start

Use the same UTC boundaries and 300 second maximum hold as runtime. Read the power unit from `course.point`; it is kW. Do not assume a role name alone guarantees units in another dataset.

## Concept

Power is a rate. Energy for a constant interval is `kW × seconds / 3600`, producing kWh. Summing kW values yields neither a mean power nor an energy total. This lesson uses a left-held rectangle, with each eligible power sample held through its bounded interval. A trapezoid needs two eligible endpoints and a different gap policy; it must not appear silently inside the same report.

Power coverage differs from status coverage. A fan may be known to run while its power reading is unavailable. Preserve that missing energy interval. An estimate derived from the schedule or neighboring readings belongs in a separately labelled field with its own assumptions.

## Tiny example

```sql
SELECT sum(kw * seconds / 3600.0) AS observed_kwh
FROM (VALUES (12.0, 300), (6.0, 120)) AS v(kw, seconds);
```

The result is 1.2 kWh. Here, the average of 12 and 6 kW would not correctly weight the unequal interval lengths.

## SQL challenge

Integrate eligible `kw` samples per equipment. Return observed kWh, valid power seconds, unknown power seconds and a coverage percentage. Calculate scheduled energy separately from the contract's stated power and schedule, and name that result as an estimate.

## Experiment

Inspect the north Supply A reading at Jan 5 15:10Z. Compare excluding that interval, replacing null with zero and interpolating it. All three can produce a number; explain which claim each number supports. Keep experimental replacements in scratch data.

## Acceptance checks

- North Supply A's observed energy is 287 kWh, with 300 unknown power seconds. Scheduled energy is 288 kWh.
- North Supply B has 72 kWh; south Supply A has 108 kWh.
- A missing interval is not reported as known zero consumption.
- Output retains units and the integration policy.

## Stretch and reflection

Explain why 287 kWh is an observed subtotal under this policy. Which additional evidence would justify estimating the missing 1 kWh?

Save SQL, actual output and a short interpretation in your own `student-work/sql/day33/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-5) for exact language and domain details.

[Previous: Day 32](day32.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 34](day34.md)
