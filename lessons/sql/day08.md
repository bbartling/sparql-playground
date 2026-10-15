# Day 08 — Choose a grain and a dependable key

[Previous: Day 7](day07.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 9](day09.md)

**Week 2 · 45–75 minutes.** Prerequisites: days 1–7, or equivalent skills.

## Goal

Describe a table's grain, distinguish candidate keys from convenient labels, and select data types that preserve meaning. Good queries begin with a clear answer to “one row per what?”

## Before you start

Connect to the course database. Keep your first site report nearby. Inspect `course.site`, `course.equipment`, `course.point`, and `course.sample` with `\d`. You are reading definitions today; keep the fixture unchanged.

## Concept

A primary key uniquely identifies a row and cannot contain nulls. A candidate key is any column set that could meet that identity requirement. A foreign key relates stored identities across tables. A label is intended for people and may change or repeat. Adding more descriptive text does not automatically create reliable identity.

The sample key `(site_id, point_id, ts)` describes one point observation at one instant within a site. Repeating a point at a different instant is legitimate; repeating the full key is not a second logical observation. The site component also makes ownership explicit.

Types constrain what a value can mean. `text` holds identifiers such as `SYN-NORTH`; `uuid` holds opaque point identities; `timestamptz` holds instants; `double precision` holds approximate measurements. Numeric measurements need units and quality metadata to be useful. A type alone cannot distinguish pascals from degrees Celsius.

## Tiny example

```sql
SELECT label, count(*) AS equipment_with_label
FROM course.equipment
GROUP BY label
ORDER BY label;
```

`Supply A` appears twice and `Supply B` once. Therefore label alone cannot be an equipment key. Inspect those two identities:

```sql
SELECT equipment_id, site_id, label
FROM course.equipment
WHERE label = 'Supply A'
ORDER BY site_id, equipment_id;
```

The two rows belong to different sites and have different UUIDs.

## SQL challenge

Write a compact schema notebook with one row per course table describing its grain, primary key, important column types, and one relationship. Include `course.sample`. Verify your descriptions against `\d` rather than inferring constraints from a few observed rows.

Write a query that groups points by site, equipment identity, and role and returns groups with more than one row. The starter fixture should return zero groups because it has one point per equipment and role. Explain why a future duplicate sensor would require a selection policy, even if both UUIDs remain unique.

## Experiment

Compare grouping equipment by label with grouping by site and label. The latter happens to distinguish all three fixture AHUs. Does that observation prove the schema enforces uniqueness of site and label? Read its constraints before answering. Data observed today and rules guaranteed tomorrow are different evidence.

## Acceptance checks

- Your notebook distinguishes 42 point identities from 24,190 sample identities.
- You demonstrate the repeated label without claiming label is a key.
- Each type explanation includes its meaning and one limit.

## Stretch and reflection

When would a numeric-looking building code need `text`? Consider leading zeros and future letters. Read [week 2 references](SOURCES.md#week-2) for keys, types, and constraints.

[Previous: Day 7](day07.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 9](day09.md)
