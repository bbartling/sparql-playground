# Day 07 — Week 1 challenge — the first site report

[Previous: Day 6](day06.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 8](day08.md)

**Week 1 review · 2–4 hours.** Prerequisites: days 1–6.

## Project brief

Produce a small SQL report pack for a colleague who has never seen this synthetic building dataset. Explain the inventory, sample coverage at the count level, and measurement quality using the tools from days 1–6. Work independently: choose the report structure and queries yourself. Allow 2–4 hours, split across sessions if useful.

Use the dedicated course database and preserve the main fixtures. Consult [the lab guide](LAB_GUIDE.md) for running saved files. The output should be understandable without a live narration. This is a storage and inventory report; counts alone do not establish operating duration or identify every missing timestamp.

## Acceptance criteria

- Inventory totals reconcile to 2 sites, 3 equipment identities, and 42 point identities; repeated equipment labels remain distinguishable.
- Stored sample totals reconcile to 24,190, including 1 bad/null observation and the 2-row pressure shortfall against the declared expectation.
- Include a site summary, a role summary, and at least one useful temperature summary with named units and a stated quality policy.
- Every result has a declared grain, descriptive columns, and a deterministic display order where appropriate.
- A bounded detail excerpt supports one finding without printing the entire history.

## Deliverables

Submit saved SQL, a compact actual-output transcript, and a short report interpreting three findings. Label results observed or not run. Include one corrected query mistake and explain what made its first answer misleading.

## Review questions

What can an equipment label identify reliably? Why do row counts and non-null counts differ? How could a correct aggregate still describe the wrong population? Which questions require joins or explicit time windows you have not learned yet?

Attempt the challenge before reading examples in [week 1 references](SOURCES.md#week-1). Record any unmet criterion and a specific next experiment.

[Previous: Day 6](day06.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 8](day08.md)
