# Day 09 — Create a small table with useful constraints

[Previous: Day 8](day08.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 10](day10.md)

**Week 2 · 45–75 minutes.** Prerequisites: days 1–8, or equivalent skills.

## Goal

Create a scratch table whose constraints reject a few clearly invalid states, and distinguish missing values from out-of-range values.

## Before you start

Use only the `student` schema in `brickts_course` for new objects. Save the DDL in a file. DDL means data definition language: statements such as `CREATE TABLE` that define a database structure. If an object already exists from an earlier attempt, inspect it and choose another scratch name; do not delete unknown objects to clear an error.

## Concept

A table definition is a contract for every writer. `PRIMARY KEY` prevents duplicate identities. `NOT NULL` requires a value. `CHECK` requires a Boolean condition that is not false, which means a null result can pass a check. Combine `NOT NULL` with a range check when both are required.

A useful constraint describes a durable rule, such as a percentage being within zero and one hundred. A short-term expectation, such as the current outdoor temperature, does not belong in a universal type rule. Database constraints protect stored states; they do not prove that a sensor was calibrated or that an operator chose the right point.

## Tiny example

```sql
CREATE TABLE student.day09_setting (
    setting_id text PRIMARY KEY,
    fan_speed_pct double precision NOT NULL,
    CHECK (fan_speed_pct BETWEEN 0 AND 100)
);

INSERT INTO student.day09_setting (setting_id, fan_speed_pct)
VALUES ('practice-1', 40);

SELECT setting_id, fan_speed_pct
FROM student.day09_setting;
```

One row should exist with `fan_speed_pct = 40`. The grain is one scratch setting per chosen identifier; this is not a command sent to equipment. Inspect the definition with `\d student.day09_setting`.

## SQL challenge

Design a separate scratch table for a lab threshold configuration. Give it a text identity, a required role name, a required unit, and required lower and upper numeric bounds. Enforce that the lower bound does not exceed the upper bound. State the table's grain and which rules it guarantees.

Insert two valid rows with different identities. Test a reversed range, a repeated identity, and a missing required value in separate statements. Record which named or described constraint rejects each input. Keep failed tests separate so you can understand each diagnostic.

## Experiment

Test `0` and `100` in the tiny percentage table, using fresh setting IDs. Both boundaries pass. Test `-1`, `101`, and `NULL`; all fail for reasons you should distinguish. Do these checks enforce a particular sampling unit or make an actual fan safe to operate? Explain their limited scope.

## Acceptance checks

- Your DDL runs in `student`, and two valid threshold rows persist.
- Invalid bounds, null required fields, and duplicate keys are rejected with recorded evidence.
- Your explanation distinguishes a check from a not-null requirement.

## Stretch and reflection

Read the meaning of finite floating-point values in [week 2 references](SOURCES.md#week-2). The main fixture has additional finite-value protection. Explain why “is numeric” is not a complete measurement-quality policy.

[Previous: Day 8](day08.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 10](day10.md)
