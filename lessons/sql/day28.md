# Day 28 — Week 4 challenge — a reviewable ingest schema

[Previous: Day 27](day27.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 29](day29.md)

**Week 4 review · 2–4 hours.** Prerequisites: days 22–27.

## Project brief

Build a small, reviewable ingest design in `student` for synthetic point observations. Combine keys, ownership, quality, retry behavior, transactions, parameters, migrations, and contract evidence. Work independently; allow 2–4 hours and keep the dataset bounded to a small fixture excerpt.

The reviewer should be able to understand what a row means, why a retry is safe, which values are eligible for calculations, and what remains unknown. Preserve the original course fixtures. Your submission is a learning artifact, not a deployment to an operational database.

## Acceptance criteria

- Tables have explicit grains, keys, types, units, quality rules, and site-consistent relationships; repeated labels do not become identity.
- Repeating one ingest batch creates no duplicate logical rows, and a correction policy is documented.
- A transaction demonstrates atomic success and rollback with compact actual evidence.
- A parameterized read uses point identity, a half-open UTC window, explicit order, and a bounded result.
- A saved scratch migration includes truthful backfill policy and pre/postconditions.
- A privilege design explains intended reader/writer access and any limits of the testing role's RLS evidence.
- An index choice follows an observed plan and a named access pattern.
- Checks cover both fixture facts and lasting relationships, including one deliberately failing scratch case.

## Deliverables

Submit DDL, bounded ingest SQL, prepared-query SQL, migration, contract checks, and a short review note. Include actual outputs or mark a check not run. State at least one remaining limitation and a concrete next test; do not report an untested claim as verified.

## Review questions

What happens after a retry, a bad late correction, or an interrupted transaction? Which ownership rule spans more than one column? What does your role permit that a reader should not receive? Which plan observation justifies an index?

Consult [week 4 references](SOURCES.md#week-4) after your independent design. Next week develops engineering calculations on top of these contracts.

[Previous: Day 27](day27.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 29](day29.md)
