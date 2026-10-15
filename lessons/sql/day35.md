# Day 35 — Week 5 independent challenge — an observed runtime and energy report

[Previous: Day 34](day34.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 36](day36.md)

**Week 5 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 29–34, or equivalent skills.

## Project brief

Deliver a reproducible report for all three synthetic AHUs over the contract's complete 48 hour window. An operator should be able to distinguish observed fan runtime, observed energy, schedule estimates and unknown coverage. Include a second report grouped by site-local week. Work only in the disposable course database; preserve the starter fixtures.

## Acceptance criteria

- One summary row per site/equipment UUID includes window, units, duration convention and signal precedence.
- Observed fan-on hours reconcile to 24, 12 and 12 for north Supply A, north Supply B and south Supply A respectively.
- Observed energy across the three AHUs totals 467 kWh; scheduled energy totals 468 kWh. Explain the difference using evidence.
- Power unknown time is visible, with no invented energy value. On/off/unknown status seconds reconcile to each equipment window.
- Local weekly pieces reconcile to the full-window totals and expose partial periods.
- A separate partial-window case proves clipping and predecessor handling.

## Deliverables

Submit SQL, compact result tables and a one-page interpretation. Include one failed or misleading calculation you corrected, its consequence and a reproducible counterexample. Keep your independently written implementation separate from earlier tiny examples.

## Self-review

Could somebody mistake an estimate for a measurement? Which rule limits forward holding? How does your report behave if status is known while power is missing? Explain each answer using a specific output field.

Label results **observed**, **fixture-only**, or **not run**. This page intentionally provides no worked solution or implementation sequence. Attempt the challenge independently before consulting [the week’s references](SOURCES.md#week-5).

[Previous: Day 34](day34.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 36](day36.md)
