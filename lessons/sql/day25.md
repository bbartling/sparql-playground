# Day 25 — Inspect privileges and the limits of a row policy

[Previous: Day 24](day24.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 26](day26.md)

**Week 4 · 45–75 minutes.** Prerequisites: days 1–24, or equivalent skills.

## Goal

Explain database roles, object privileges, and row-level security, or RLS, while inspecting your own disposable lab connection. No server-wide role creation or administrative grant changes are required.

## Before you start

Connect to `brickts_course` and record `SELECT current_user, session_user;`. Credentials stay outside your notes. The lab connection may own its objects or have broad privileges; that is convenient for learning, but it is not evidence that an application reader has restricted access.

## Concept

A role can own objects and receive privileges. A schema needs `USAGE` for objects inside it to be reachable; table `SELECT` grants reading, while `INSERT`, `UPDATE`, and `DELETE` allow different writes. Ownership and membership affect the effective rights. A grant on one table does not automatically establish the desired policy for all future tables.

RLS adds row conditions to applicable queries; it does not replace ordinary object privileges. Superusers and roles with `BYPASSRLS` bypass policies. Table owners normally bypass RLS unless forced, and even forcing it does not constrain a superuser. Testing as the owner therefore cannot establish a restricted user's isolation. A caller-controlled site setting is also not authenticated site ownership.

## Tiny example

```sql
SELECT current_user,
       has_schema_privilege(current_user, 'course', 'USAGE') AS course_usage,
       has_table_privilege(current_user, 'course.sample', 'SELECT') AS can_read_samples;

SELECT rolname, rolsuper, rolbypassrls
FROM pg_catalog.pg_roles
WHERE rolname = current_user;
```

A working fixture reader should report true for schema usage and sample reading. The other flags depend on the actual lab role; record them rather than inventing a result.

A policy definition on a scratch object uses this syntax:

```sql
CREATE TABLE student.day25_note (
    note_id integer PRIMARY KEY,
    site_id text NOT NULL,
    note text NOT NULL
);
ALTER TABLE student.day25_note ENABLE ROW LEVEL SECURITY;
CREATE POLICY day25_north_read ON student.day25_note
    FOR SELECT USING (site_id = 'SYN-NORTH');
SELECT row_security_active('student.day25_note'::regclass) AS policy_applies;
```

As this table's owner, you normally get `false`: the policy exists but does not restrict your current reads. Do not confuse successful policy creation with a successful isolation test.

## SQL challenge

Write a privilege matrix for three conceptual roles: metadata reader, sample ingester, and migration owner. For each, name required schema/table actions and explain any ownership. These are design notes, not commands to alter server roles.

Populate the scratch notes table with one explicitly synthetic note for each site. Inspect its policy through `pg_catalog.pg_policies`, limiting the result to the `student` schema and this table. Read the notes and compare their visibility with `row_security_active`. Explain why the observed output does or does not establish isolation for an intended reader. If your role bypasses the policy, document that limitation instead of claiming isolation.

## Experiment

Compare the observed privilege booleans with your successful and failed operations from earlier lessons. Explain why a zero-row result can come from a filter, an RLS policy, or genuinely absent data, while a permission error is a different outcome. Avoid changing shared roles to manufacture a result.

## Acceptance checks

- Your evidence identifies the current role's read privilege and bypass flags without exposing credentials.
- Your matrix assigns only the actions each role needs.
- Your RLS note explicitly states whether enforcement was active for the testing role.

## Stretch and reflection

What separate test identity would be needed to verify two-site isolation? Describe the expected allowed and denied cases for a DBA to provision. Read [week 4 references](SOURCES.md#week-4) for grants and RLS caveats.

[Previous: Day 24](day24.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 26](day26.md)
