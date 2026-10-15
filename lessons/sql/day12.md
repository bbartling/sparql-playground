# Day 12 — Detect a join that multiplies observations

[Previous: Day 11](day11.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 13](day13.md)

**Week 2 · 45–75 minutes.** Prerequisites: days 1–11, or equivalent skills.

## Goal

Recognize an accidental many-to-many join, measure its effect, and repair it using the relationship that matches your intended grain.

## Before you start

Keep yesterday's point inventory available. The fixture has three points for each role, one on each AHU. Role names describe a measurement category; a role name alone does not identify a point or its owning equipment.

## Concept

A join emits every pair that satisfies its condition. If three left rows and three right rows share the same role, joining only on role creates nine pairs. SQL has done exactly what was requested, even if a report author expected three.

`DISTINCT` can hide repeated output values, but it cannot establish that the correct physical entities were paired. Aggregating after a mistaken join can silently inflate counts and sums. Test row counts and key uniqueness before trusting an engineering calculation. The correct join condition follows the relationship: sample identity to point identity with site ownership, then point's equipment identity to equipment.

## Tiny example

```sql
SELECT p.point_id AS left_point, q.point_id AS right_point,
       p.role
FROM course.point AS p
JOIN course.point AS q ON q.role = p.role
WHERE p.role = 'duct_static'
ORDER BY p.point_id, q.point_id;
```

This deliberately incorrect identity match returns nine rows. Only three pair a point with itself. Inspect the UUIDs to see the six cross-equipment pairs instead of merely noting repeated role text.

## SQL challenge

Write an explicit `course.sample` → `course.point` → `course.equipment` query for `kw` observations. Show site ID, equipment identity and label, point identity, timestamp, value, and quality. Count its rows in a separate query: 1,728 are stored, including one unusable power observation. Check that no `(site_id, point_id, ts)` group occurs more than once.

Now document a deliberately wrong version that joins a sample's point metadata to another point by role alone. Keep it bounded or count its rows; do not present it as a valid report. Explain how your corrected version retains the intended observation grain.

## Experiment

Predict the wrong power-query row count. Since each original power row can match three role peers, expect 5,184 rows. Compare counts before and after the additional join. Why might an average happen to stay unchanged while the count triples? A plausible average is not proof of a correct relationship.

## Acceptance checks

- The valid power join has 1,728 rows and no repeated logical sample key.
- Your evidence demonstrates the nine-pair point example and explains its cause.
- The fix uses declared identities and ownership, with no arbitrary first-row selection.

## Stretch and reflection

Imagine two temperature sensors with the same role on one AHU. What metadata or explicit selection policy would a report need? Write the ambiguity as an unresolved requirement rather than choosing one by UUID order. Read [week 2 references](SOURCES.md#week-2) for join semantics and uniqueness.

[Previous: Day 11](day11.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 13](day13.md)
