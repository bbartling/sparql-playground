# Day 49 — Week 7 independent challenge — a known-answer pressure FDD report

[Previous: Day 48](day48.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 50](day50.md)

**Week 7 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 43–48, or equivalent skills.

## Project brief

Independently build a bounded SQL pressure-condition report for all fixture AHUs. Use eligible fan-on status, positive pressure setpoint and `duct_static < 0.9 × duct_static_sp`. Apply a ten-minute startup delay. Confirm the third consecutive eligible true observation, break on false, unknown or a gap over 300 seconds, and do not backdate confirmation. Use bounded left-held intervals clipped to the window.

This is a declared teaching rule. It does not claim to reproduce the complete current Open-FDD FC1 implementation.

## Acceptance criteria

- Full-window north Supply A has ten raw candidate observations, two unavailable pressure instants within the excursion and two candidate islands.
- Raw duration is 3,000 seconds; confirmed duration is 1,800 seconds in two confirmed islands. Other equipment have no confirmed pressure condition.
- Off, warmup, unknown and evaluated-false states remain distinguishable.
- The short-window result agrees with an enclosing report after clipping, including starts between sample instants.
- Per-equipment applicability and a unique effective policy are checked before evaluation.

## Deliverables

Provide SQL, detail and summary outputs, a policy card and two scratch counterexamples covering a gap and a threshold boundary. Explain one way an apparently reasonable query could overstate confirmation or hide unavailable evidence.

## Self-review

Can every summary second be traced to detail? Which decisions came from SQL semantics, and which were domain policy? What additional adapter and catalog checks are required before comparing this output with production Open-FDD?

Label results **observed**, **fixture-only**, or **not run**. This page intentionally provides no worked solution or implementation sequence. Attempt the challenge independently before consulting [the week’s references](SOURCES.md#week-7).

[Previous: Day 48](day48.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 50](day50.md)
