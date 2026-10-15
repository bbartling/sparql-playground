# Day 10 — Separate facts and enforce relationships

[Previous: Day 9](day09.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 11](day11.md)

**Week 2 · 45–75 minutes.** Prerequisites: days 1–9, or equivalent skills.

## Goal

Recognize repeated facts, explain basic normalization, and use a foreign key to keep related scratch tables consistent.

## Before you start

Review the grains and keys in your schema notebook. Today's scratch objects are independent of yesterday's table. All inserts stay in `student`; you do not need to add any course sites or equipment.

## Concept

Suppose every sample row repeats a site's label and timezone. Renaming that label would require changing many rows, and missed updates could leave contradictory descriptions. Normalization places each fact with the identity it describes: site facts with a site, equipment facts with equipment, and observations with point and instant.

Splitting tables is useful only when their relationships remain explicit. A foreign key requires a referenced key to exist. A composite foreign key checks a combination together. In the course, a point's equipment must belong to the same site as the point; checking only that an equipment UUID exists would not establish that ownership rule.

## Tiny example

```sql
CREATE TABLE student.day10_site (
    site_id text PRIMARY KEY,
    label text NOT NULL
);
CREATE TABLE student.day10_equipment (
    equipment_code text PRIMARY KEY,
    site_id text NOT NULL
        REFERENCES student.day10_site (site_id),
    label text NOT NULL
);
INSERT INTO student.day10_site (site_id, label)
VALUES ('practice-site', 'Practice site');
INSERT INTO student.day10_equipment (equipment_code, site_id, label)
VALUES ('practice-ahu', 'practice-site', 'Practice supply');
```

There is one parent and one child. The text equipment code is a scratch simplification; real course equipment continues to use its frozen UUID identity. A child with `site_id = 'unknown-site'` fails because no matching parent exists.

## SQL challenge

Sketch a small normalized design for maintenance notes tied to equipment identity. Decide where equipment labels live and what one note row represents. Create a scratch notes table referencing `course.equipment(equipment_id)` and insert one note by selecting an equipment UUID from metadata. Your query must show the site and label used to choose that equipment, so the repeated label cannot cause an accidental choice.

Explain what happens if a note refers to an invented UUID. Test rejection using your scratch table and a clearly synthetic UUID; do not alter course metadata.

## Experiment

Change the label of the practice site and read the child row. Its relationship still uses the stable site ID, so the equipment does not need a new identity. Try inserting an equipment row before its missing practice parent exists. Record the foreign-key diagnostic and explain the required relationship.

## Acceptance checks

- Your design stores each equipment label in its metadata location and stores note-specific facts with each note.
- A valid equipment reference is accepted; an unknown reference is rejected.
- You can explain why the course also checks site/equipment ownership together.

## Stretch and reflection

What should happen to notes when equipment is retired? Compare rejecting deletion, retaining a retired metadata row, and cascading deletion conceptually. Do not test destructive policies on the fixture. Read [week 2 references](SOURCES.md#week-2) for referential integrity and normalization.

[Previous: Day 9](day09.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 11](day11.md)
