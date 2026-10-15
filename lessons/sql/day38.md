# Day 38 — Keep BAS and web weather as separate sources

[Previous: Day 37](day37.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 39](day39.md)

**Week 6 · 45–75 minutes.** Prerequisites: Days 1–37, or equivalent SQL skills.

## Goal

Compare weather measurements and temperature bins without erasing provenance or duplicating HVAC observations.

## Before you start

The course fixture contains BAS `oat` points only. It contains no downloaded weather history. Use a small, locally written scratch weather relation for this exercise; mark it synthetic. No external account or network call is required.

## Concept

An OAT value needs source, timestamp, unit and location context. A building sensor and a weather website can differ because of placement, averaging, publication delay or measurement method. Neither becomes interchangeable simply because both columns say temperature.

A join must declare its matching policy. An exact timestamp join may lose observations; an unbounded nearest-time join may borrow stale weather. More than one weather row within tolerance can multiply a BAS row and inflate every later denominator. Retain original source timestamps and match age. If multiple AHUs have BAS OAT sensors, choose a site weather policy explicitly rather than averaging them accidentally.

## Tiny example

```sql
SELECT source, floor(oat_c / 5.0) * 5 AS bin_lower_c
FROM (VALUES ('BAS', 18.0), ('synthetic_web', 20.0),
             ('BAS', -1.0)) AS v(source, oat_c);
```

The bins are 15, 20 and -5 °C. Here a bin is `[lower, lower + 5)`; negative temperatures expose truncation mistakes.

## SQL challenge

Create a scratch comparison dataset with at least three synthetic weather timestamps, a source label and explicit °C units. Match it to a bounded BAS window under a declared tolerance and tie policy. Report unmatched observations and weather age. Produce OAT-bin summaries of BAS fan-on kW with sample count and valid seconds, retaining source identity.

## Experiment

Add a second weather row inside one match tolerance. Predict the row count of a naive join and then show how your chosen policy preserves at most one weather match per BAS observation. Include a timestamp outside tolerance.

## Acceptance checks

- Scratch weather is visibly labelled synthetic and remains outside `course` fixtures.
- The negative-temperature example bins to -5 °C.
- Matching does not multiply BAS intervals or reuse weather without a bounded age.
- Every bin names source, boundaries, equipment scope and coverage.

## Stretch and reflection

Would aggregating hourly BAS data before joining hourly web data remove all alignment issues? Explain the remaining timezone and averaging-window questions.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day38/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-6) for exact language and domain details.

[Previous: Day 37](day37.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 39](day39.md)
