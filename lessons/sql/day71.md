# Day 71 — Assert known answers and test the tests

[Previous: Day 70](day70.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 72](day72.md)

**Week 11 · 45–75 minutes.** Prerequisites: Days 1–70, or equivalent SQL skills.

## Goal

Turn fixture facts into SQL assertions and show that a plausible implementation mistake is detected.

## Before you start

Keep the canonical fixture intact. Use scratch views for mutations and `psql` with `ON_ERROR_STOP` for the final assertion script. Save a deliberately failing transcript separately from the passing run.

## Concept

A test oracle is an independent statement of the expected result. Repeating the same formula in two queries can reproduce the same mistake twice. Derive a small expected answer from a calendar, a hand-counted interval or an explicitly constructed table. SQL assertions can raise exceptions inside a `DO` block. Mutation testing deliberately introduces a bug to check whether the assertions fail. Optional pandas may provide a testing oracle; SQL remains the primary implementation.

## Tiny example

```sql
DO $$
BEGIN
  IF (SELECT count(*) FROM course.site) <> 2 THEN
    RAISE EXCEPTION 'expected two synthetic sites';
  END IF;
  IF (SELECT count(*) FROM course.sample) <> 24190 THEN
    RAISE EXCEPTION 'sample fixture changed';
  END IF;
END $$;
```

A raised exception must make the script fail. Notices or printed booleans alone can be overlooked by CI.

## SQL challenge

Assert north Supply A’s January 5 kW energy using the declared five-minute, clipped duration convention: 12 on-hours at 12 kW would be 144 kWh; one unknown five-minute kW interval leaves 143 observed kWh and five minutes unknown. Assert the missing duct-static instants separately: ten eligible samples in 08:00–09:00 UTC. Use UUID resolution and explicit site/window predicates. Compare floating results with a declared tolerance.

## Experiment

Create two defective scratch versions: one replaces bad/null kW with 12, and another bridges the two missing pressure intervals as though observations existed. Show that the relevant assertions fail. Restore correct versions and rerun. Keep the expected constants independent of those mutated queries.

## Acceptance checks

- The unmodified fixture passes exact counts and tolerant numeric checks.
- Each mutation triggers the intended failing assertion.
- Failure produces a nonzero script exit status.
- Coverage, unknown duration and observed energy remain separate fields.

## Stretch and reflection

Which boundary case would catch an inclusive end timestamp? Design its expected answer before writing the query.

Save your SQL, actual output, and one explanation in `student-work/sql/day71/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-11).

[Previous: Day 70](day70.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 72](day72.md)
