# Day 14 — Week 2 challenge — design a small relational schema

[Previous: Day 13](day13.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 15](day15.md)

**Week 2 review · 2–4 hours.** Prerequisites: days 8–13.

## Project brief

Design a reviewable scratch schema for an additional synthetic site, its equipment, point metadata, and a bounded observation excerpt. Use only `student` objects. Keep course metadata and samples intact. Work independently from a written statement of each table's grain; allow 2–4 hours.

Your design should let another learner understand ownership, units, quality, and repeated ingest without guessing from names. It may be smaller than the course schema, but explain every omitted rule. Use frozen synthetic identities and explicit relationships rather than deriving runtime identity from labels.

## Acceptance criteria

- Each table has a stated grain and a key that identifies that grain.
- Foreign keys prevent unknown parent references, and ownership across sites is explained and enforced wherever your design stores both identities.
- Required values, valid quality states, and basic measurement/configuration checks have appropriate constraints.
- A repeated logical observation cannot create a duplicate; your correction policy is written down.
- A join report preserves the intended observation grain and distinguishes two equipment records with the same label.
- Evidence includes valid input, rejected invalid input, duplicate ingest, and a scratch rollback.

## Deliverables

Submit DDL, bounded seed/ingest SQL, a schema sketch or relationship description, a report query, and a short transcript. Explain one design tradeoff, one rule enforced by the database, and one rule that still needs application or human judgment. Mark evidence observed or not run.

## Review questions

Which repeated fact would cause inconsistent updates? How do you know a join did not multiply rows? What does a foreign key guarantee about ownership, and what extra combination might be needed? When should a retry change a value?

Use [week 2 references](SOURCES.md#week-2) after your independent attempt; no worked implementation is supplied here.

[Previous: Day 13](day13.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 15](day15.md)
