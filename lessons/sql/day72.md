# Day 72 — Test scope, constraints and row security negatively

[Previous: Day 71](day71.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 73](day73.md)

**Week 11 · 45–75 minutes.** Prerequisites: Days 1–71, or equivalent SQL skills.

## Goal

Show that unauthorized site combinations and invalid data are rejected, and state the limits of an RLS test.

## Before you start

Use scratch tables and approved existing lab accounts only. Do not create cluster roles or alter a shared server. Record the executing account’s `rolsuper` and `rolbypassrls`; if no suitable restricted account exists, mark the RLS enforcement test blocked.

## Concept

Composite foreign keys prevent cross-site identity combinations even when each UUID exists individually. Query predicates still need authorization derived from trusted caller context. Row-level security can add another boundary, but table owners normally bypass it unless forced, and superusers/BYPASSRLS roles bypass it. A custom session setting is not authentication when an untrusted caller can change it. PostgreSQL’s [row-security guide](https://www.postgresql.org/docs/16/ddl-rowsecurity.html) explains these account-dependent behaviors.

## Tiny example

```sql
CREATE TABLE student.scope_demo (
  site_id text NOT NULL, amount integer NOT NULL
);
INSERT INTO student.scope_demo VALUES ('SYN-NORTH', 1), ('SYN-SOUTH', 2);
ALTER TABLE student.scope_demo ENABLE ROW LEVEL SECURITY;
ALTER TABLE student.scope_demo FORCE ROW LEVEL SECURITY;
CREATE POLICY north_demo ON student.scope_demo
USING (site_id = 'SYN-NORTH') WITH CHECK (site_id = 'SYN-NORTH');
```

The fixed policy demonstrates filtering. A valid enforcement check requires an existing account with the necessary table privileges and no bypass. Seeing both rows as a superuser is expected bypass evidence.

## SQL challenge

Build a negative-test matrix for history and ingest: south point with north site, duplicate key, invalid quality, nonfinite value, bad/null eligibility and unknown UUID. Execute data mutations only against scratch tables carrying the relevant constraints. If using an approved restricted role, verify that disallowed-site reads return zero rows and disallowed inserts or site-changing updates are rejected; record account properties and grants.

## Experiment

Remove a site predicate from a scratch query. Confirm that the test detects cross-site leakage, including the repeated `Supply A` label. Then restore the predicate. Compare the result under a bypass account without mistaking it for an enforcement test.

## Acceptance checks

- Every negative case has an expected outcome and actual evidence or a blocked label.
- Failed writes leave no invalid scratch rows.
- Scope tests use identity and site together.
- No role, policy or grant is installed in an application database.

## Stretch and reflection

Where must trusted site authorization enter the connection/request lifecycle?

Save your SQL, actual output, and one explanation in `student-work/sql/day72/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-11).

[Previous: Day 71](day71.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 73](day73.md)
