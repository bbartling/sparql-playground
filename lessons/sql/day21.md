# Day 21 — Week 3 challenge — a time-series quality report

[Previous: Day 20](day20.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 22](day22.md)

**Week 3 review · 2–4 hours.** Prerequisites: days 15–20.

## Project brief

Produce a time-series quality report for the two-day synthetic fixture. Use precise UTC half-open windows and separate observations, measurement usability, and supported duration. Work independently with your earlier lessons and references; allow 2–4 hours.

The report should help a colleague decide where a later engineering calculation would have enough evidence. It should state its limits clearly: a normal sample count is not proof of valid values, and known schedule hours are not observed run hours. Keep raw evidence bounded and preserve every fixture row.

## Acceptance criteria

- Report per-point stored and usable counts with site/equipment identity and role/unit context.
- Identify the affected pressure point and its Jan 5 08:20→08:35 UTC spacing, including the two absent expected instants.
- Distinguish the one bad/null power sample from an absent row.
- Quantify pressure coverage for Jan 5 08:00–09:00 UTC under the declared maximum-300-second support convention; the affected point has 3,000 covered and 600 unknown seconds.
- Adjacent half-open report windows reconcile without sharing boundary observations.
- Any pivot has a documented single-point-per-role assumption and leaves unknown values visible.

## Deliverables

Submit saved SQL, compact actual results, and a report explaining at least one count issue, one quality issue, and one boundary decision. Include grain and units for every result. Mark output observed or not run; record an unmet check explicitly.

## Review questions

What does the first visible row know about the prior interval? Why can a bad-value row preserve cadence? Which time is known, supported by a convention, scheduled, or unknown? How would duplicate sensors change the report?

Attempt this independently before consulting [week 3 references](SOURCES.md#week-3). No worked implementation or calculation sequence is supplied.

[Previous: Day 20](day20.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 22](day22.md)
