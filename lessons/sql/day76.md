# Day 76 — Replay a small failure qualification matrix

[Previous: Day 75](day75.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 77](day77.md)

**Week 11 · 45–75 minutes.** Prerequisites: Days 1–75, or equivalent SQL skills.

## Goal

Combine correctness and operational evidence into a repeatable, bounded qualification run.

## Before you start

Reuse earlier SQL and scripts. Cap the run at two clients, forty operations, 241,900 scratch rows and a five-second statement deadline. Set a total deadline and stop conditions before starting. Do not stop shared services or inject network faults into production.

## Concept

A stress result is useful only alongside correct answers, workload shape and failure accounting. A fast query returning the wrong site’s data fails qualification. Replaying failures means preserving a small synthetic input, revisions, SQL parameters, expected behavior and observed error category. A skipped cancellation test cannot become a successful cancellation claim. Recovery includes connection/transaction cleanup and removal of scratch jobs or locks.

## Tiny example

```sql
CREATE TABLE student.qualification_case (
  case_id text PRIMARY KEY,
  expected text NOT NULL,
  observed text,
  status text NOT NULL CHECK (
    status IN ('pending', 'pass', 'fail', 'skipped', 'blocked'))
);
INSERT INTO student.qualification_case
VALUES ('empty-window', 'zero rows, valid request', NULL, 'pending');
```

A case starts pending. Set its final status only after recording evidence. This ledger organizes results; it does not execute the test for you.

## SQL challenge

Build a matrix covering correct history, a missing-data bucket, wrong-site scope, duplicate ingest, conflicting correction, statement cancellation, lock contention and aggregate freshness. Reuse an independent expected answer from day71. Execute the safe cases available in your lab and attach a transcript or result artifact to each status. Write a replay note containing enough information for another learner to reproduce one failure without accessing your machine.

## Experiment

Run a small normal workload, inject one bounded error, then rerun the normal query in the same session after cleanup. Compare correctness and elapsed time. Record whether the recovery path restored service within your declared deadline; do not infer that from the final query alone.

## Acceptance checks

- Every case has a status, expected outcome and evidence or a specific unrun reason.
- Counts distinguish passing, failing, skipped and blocked cases.
- Recovery leaves no aborted transaction, held lab lock or scheduled scratch job.
- The report stays within its declared data and concurrency caps.

## Stretch and reflection

Which unavailable test most limits your confidence? Propose a bounded environment requirement for running it later.

Save your SQL, actual output, and one explanation in `student-work/sql/day76/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-11).

[Previous: Day 75](day75.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 77](day77.md)
