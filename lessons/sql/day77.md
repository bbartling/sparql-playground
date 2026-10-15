# Day 77 — Independent challenge — an honest stress qualification packet

[Previous: Day 76](day76.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 78](day78.md)

**Week 11 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 71–76, or equivalent skills.

## Project brief

Qualify one bounded historian and analytics design using correctness, isolation and recovery evidence. Choose the workload and failure matrix independently. Keep limits at two clients, forty operations, 241,900 synthetic rows and five seconds per statement, with a total deadline. Use only the dedicated lab.

The packet should let a reviewer reproduce the test and understand what remains unknown. References are in [week 11’s reading list](SOURCES.md#week-11).

## Acceptance criteria

- Independent known answers cover units, scope, gaps and boundaries.
- Mutation tests demonstrate that important checks can fail.
- Negative tests cover cross-site identity and relevant constraints; RLS claims include account properties.
- Cancellation/transaction recovery and one concurrency failure have actual evidence or explicit unrun status.
- Model/query/data revisions, run-copy consistency and installed-schema checks are represented.
- Resource observations and performance claims stay within the measured workload.

## Deliverables

Submit the workload definition, SQL/assertions, environment manifest, result ledger, representative plans and replay instructions for one failure. Report **pass**, **fail**, **skipped** and **blocked** separately. Neither skipped nor blocked checks count as passing. Include cleanup verification and the next necessary experiment for each unresolved requirement.

## Self-review

Which failure would a happy-path test miss? What can your account bypass? Why does a low average latency fail to establish reliable service? Explain the strongest claim your evidence supports, then identify its practical limit.

[Previous: Day 76](day76.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 78](day78.md)
