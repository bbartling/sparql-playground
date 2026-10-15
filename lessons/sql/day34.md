# Day 34 — Group reporting periods in each site’s timezone

[Previous: Day 33](day33.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 35](day35.md)

**Week 5 · 45–75 minutes.** Prerequisites: Days 1–33, or equivalent SQL skills.

## Goal

Build local calendar reporting periods while preserving UTC instants and elapsed durations.

## Before you start

Inspect `course.site.tz`; use the stored IANA timezone names. Set a display timezone only if helpful, and record it. The fixture spans 48 UTC hours and may cover partial local dates or weeks.

## Concept

A `timestamptz` identifies an instant. `ts AT TIME ZONE site.tz` gives its local wall-clock representation. Local week labels describe a calendar, while energy and runtime remain elapsed seconds. PostgreSQL's `date_trunc('week', ...)` uses a Monday start. State that convention explicitly.

Do not assign an entire interval to the week containing its starting sample if the interval crosses a week boundary. Split intervals at local boundaries converted back to UTC, then aggregate the pieces. Daylight saving transitions can make a local day shorter or longer than 24 hours. A partial week in this two-day fixture does not become a complete week because its label is Monday.

## Tiny example

```sql
SELECT ts,
       ts AT TIME ZONE 'America/Chicago' AS local_time,
       date_trunc('week', ts AT TIME ZONE 'America/Chicago') AS local_week
FROM (VALUES ('2026-01-05 00:00Z'::timestamptz)) AS v(ts);
```

That instant is Sunday evening locally, so its local week starts on the preceding Monday. Changing the session display timezone does not change the underlying instant.

## SQL challenge

Extend your runtime and energy reports with site-local week labels, UTC period boundaries, requested-window intersection and a partial-period flag. Preserve each equipment's identity. Compare local-week grouping with UTC-week grouping and explain any extra group.

## Experiment

Use scratch instants around a spring daylight saving transition in a timezone that observes it. Calculate elapsed seconds between consecutive local midnights converted to UTC. Predict the result before running; do not alter fixture timestamps.

## Acceptance checks

- Your one-instant demonstration places Jan 5 00:00Z in the previous Chicago calendar week.
- Every covered interval belongs to exactly one period after splitting.
- Summing local-period observed runtime and kWh reproduces Days 32–33 totals.
- No partial period claims 168 hours of fixture coverage.

## Stretch and reflection

How should a dashboard label a weekly total when the requested data covers only Sunday evening? Propose a label containing both the calendar week and actual coverage.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day34/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-5) for exact language and domain details.

[Previous: Day 33](day33.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 35](day35.md)
