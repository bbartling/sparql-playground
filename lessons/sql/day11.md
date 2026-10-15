# Day 11 — Join metadata and preserve empty groups

[Previous: Day 10](day10.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 12](day12.md)

**Week 2 · 45–75 minutes.** Prerequisites: days 1–10, or equivalent skills.

## Goal

Use an inner join to combine related facts and a left join to retain a parent that has no matching detail. Explain what one result row represents after each join.

## Before you start

Revisit the fixture's relationships: site → equipment → point → sample. A join uses these stored identities to combine rows. Similar labels are not evidence that two rows describe the same entity.

## Concept

An inner join emits matching pairs. If one equipment has fourteen points, joining it to points produces fourteen rows, each with repeated equipment facts. This repetition is expected because the result's grain is now a point.

A left join keeps each left-side row even when no right-side row matches, filling right-side columns with nulls. A filter on the right table placed in `WHERE` can remove these unmatched rows. Put a condition in `ON` when it defines which optional matches are eligible. Count a non-null child key to count matches: `count(*)` would also count the left join's preserved row.

## Tiny example

```sql
SELECT e.equipment_id, e.site_id, e.label AS equipment_label,
       s.label AS site_label
FROM course.equipment AS e
JOIN course.site AS s ON s.site_id = e.site_id
ORDER BY e.site_id, e.equipment_id;
```

There are three rows, one per equipment identity. Joining site metadata does not multiply these rows because each site ID identifies one site.

A useful optional-detail report is:

```sql
SELECT s.site_id, count(h.point_id) AS bad_sample_rows
FROM course.site AS s
LEFT JOIN course.history AS h
  ON h.site_id = s.site_id AND h.quality = 'bad'
GROUP BY s.site_id
ORDER BY s.site_id;
```

It returns north `1` and south `0`.

## SQL challenge

Build a point inventory by joining `course.point` to `course.equipment` and `course.site`. Use point/equipment UUIDs and matching site IDs in the relationship. Show site ID, equipment identity and label, point identity, role, and unit. Predict and verify forty-two rows.

Then create a site report that counts matching `duct_static` sample rows while retaining every site. Explain which relation supplies the group identities and which key counts detail rows.

## Experiment

Move `h.quality = 'bad'` from the tiny left join's `ON` to a `WHERE` clause. South disappears because its preserved row has null right-side values. Restore the condition to `ON` and replace `count(h.point_id)` with `count(*)`; south misleadingly becomes `1`. Describe both mistakes in terms of rows, not syntax memorization.

## Acceptance checks

- Your point inventory has 42 distinct point identities and enough ownership context.
- The optional bad-quality report retains both sites with counts 1 and 0.
- You can explain the effect of moving a right-side filter after a left join.

## Stretch and reflection

Read [week 2 references](SOURCES.md#week-2) for join types. Which questions need unmatched parents to remain visible, and which deliberately ask only for existing matches?

[Previous: Day 10](day10.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 12](day12.md)
