# Day 42 — Week 6 independent challenge — an analytics engineering review

[Previous: Day 41](day41.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 43](day43.md)

**Week 6 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 36–41, or equivalent skills.

## Project brief

Prepare a small analytics package for a reviewer who knows SQL but has not seen your earlier lessons. Cover comfort, power versus OAT, and supply-air temperature error for all fixture AHUs. The package should make every metric's grain, units, eligibility and denominator discoverable.

## Acceptance criteria

- Comfort includes all-time and fan-on denominators, coverage and the inclusive 20–24 °C teaching band.
- North Supply A's one-hour comfort excursion and north Supply B's one-hour warm SAT interval remain attributable to their correct equipment and time.
- A scatter detail result has an explicit unique grain, source identity and valid duration weights.
- A summary preserves sums and denominators; its weighted means can be independently recomputed.
- A stored result has documented freshness and refresh behavior, demonstrated with scratch data.
- Any synthetic web-weather comparison retains source timestamps, bounded matching and a visible synthetic label.

## Deliverables

Submit independently written SQL, a data dictionary, compact results and a brief review note. Include one unequal-weight counterexample and one join-multiplication counterexample. Explain why a visual association or out-of-range mixing fraction does not automatically justify a fault diagnosis.

## Self-review

Could a reviewer reconstruct your percentage from exported columns? Could a refresh change a result without changing the source window? Which distinctions disappear if only the final mean is retained? Identify one concrete improvement before presenting the package to another learner.

Label results **observed**, **fixture-only**, or **not run**. This page intentionally provides no worked solution or implementation sequence. Attempt the challenge independently before consulting [the week’s references](SOURCES.md#week-6).

[Previous: Day 41](day41.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 43](day43.md)
