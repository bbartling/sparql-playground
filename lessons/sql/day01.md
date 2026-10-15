# Day 01 — Open the SQL workbench

[Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 2](day02.md)

**Week 1 · 45–75 minutes.** Prerequisites: none; start here.

## Goal

Start the disposable course database, connect with `psql`, and explain the difference between a terminal command, a SQL statement, and a database server. Your first successful query should be something you understand completely.

## Before you start

Choose [the local lab](LAB_GUIDE.md) or follow [the remote Timescale setup](REMOTE_SETUP.md) on a separate test machine. Read the prerequisites and database isolation rules. The commands below are for the local route; the remote guide shows where each command runs. From the repository root, run these terminal commands separately:

```bash
uv run python lessons/sql/lab.py up
uv run python lessons/sql/lab.py load
uv run python lessons/sql/lab.py psql
```

Use only the dedicated `brickts_course` database. Save your notes and SQL under your own `student-work/sql/day01/` directory. Keep passwords and connection strings out of evidence files.

## Concept

The terminal runs programs. `psql` is a client program: it sends SQL to PostgreSQL, the server that stores tables and executes queries. Closing the client does not delete the database. A SQL statement normally ends with a semicolon; pressing Enter alone can leave the client waiting for the rest of it.

A literal is a value written directly in a statement. Single quotes surround SQL text values. An alias gives an output column a useful name; it does not create a stored column. Double quotes have a different job: they quote identifiers. We will use simple lowercase identifiers so that distinction stays visible.

## Tiny example

Inside `psql`, run:

```sql
SELECT 'synthetic building lab' AS purpose,
       2 + 3 AS arithmetic_result;
SELECT current_database() AS database_name;
```

The first query returns one row with arithmetic result `5`; the second should name `brickts_course`. Neither query reads building samples. Try `\conninfo` to inspect the current connection and `\q` to leave the client. Backslash commands belong to `psql`, so they do not need SQL semicolons.

## SQL challenge

Reconnect and write a query that returns your chosen report title, the number of minutes in an hour, and a clearly named numeric expression. Use separate aliases that describe each result. Record `SELECT version();` so your notes identify the actual server. Explain which process produced the answer and which process displayed it.

## Experiment

Enter `SELECT 10 +` and press Enter. Observe the changed prompt, then finish with `5;`. Repeat with an accidental unfinished statement and use Ctrl+C to cancel it. Do not paste terminal commands into the SQL prompt. Predict what each input will do before running it.

## Acceptance checks

- The connection identifies `brickts_course`, and your arithmetic has the expected result.
- You can cancel unfinished input and successfully run another statement.
- Your notes distinguish the shell, `psql`, SQL, and PostgreSQL in your own words.

## Stretch and reflection

Use `\?` and `\h SELECT` to find client and SQL help. Which information belongs to the client, and which describes the server language? Record one error message and the correction you understood. Read [week 1 references](SOURCES.md#week-1) before changing installation settings.

[Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 2](day02.md)
