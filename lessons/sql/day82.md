# Day 82 — Package a portable API and Plotly figure with provenance

[Previous: Day 81](day81.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 83](day83.md)

**Week 12 · 45–75 minutes.** Prerequisites: Days 1–81, or equivalent SQL skills.

## Goal

Carry a consistent result cohort from SQL through a language-neutral API response into a small plot artifact.

## Before you start

Reuse day59’s contract and one day80 diagnostic or day81 metric. A JSON response and Plotly figure specification are sufficient; no running app, CDN or new UI is required. Keep all data synthetic.

## Concept

A result cohort fixes site, equipment set, model revision, rule/query version, effective tuners, window and data snapshot. Summary cards and plots must refer to that same cohort. A plot of raw samples may support diagnosis but cannot silently stand in for a confirmed-fault mask. Missing intervals need visible gaps. Plotly figure JSON uses `data` traces and `layout`; the API can supply this or a documented typed series contract without depending on one server language.

## Tiny example

```json
{
  "data": [{"type": "scatter", "mode": "lines+markers",
    "x": ["2026-01-05T08:20:00Z", "2026-01-05T08:25:00Z"],
    "y": [100, null], "connectgaps": false,
    "name": "Duct static (Pa)"}],
  "layout": {"yaxis": {"title": {"text": "Pa"}}}
}
```

This small figure preserves one explicit gap. Keep point identity and revision provenance in the surrounding response rather than relying on a human-readable trace name.

## SQL challenge

Produce a bounded response for north Supply A’s low-pressure hour with raw pressure/setpoint, confirmation mask, coverage and summary. Include run/cohort ID, UTC half-open range, units, source point UUIDs, model/data revisions, SQL/template hash, effective tuners and result status. Define point/trace/payload caps. Prepare the same contract for a second server language without rewriting the SQL equation.

## Experiment

Attempt to pair a day80 summary with a plot generated using different confirmation or window parameters. Show that cohort validation rejects the mismatch. Compare full-resolution mask evidence with a downsampled visual; explain which facts the latter cannot establish.

## Acceptance checks

- Summary and figure share the same declared cohort.
- Aligned arrays, null gaps, units and UTC timestamps are valid.
- SQL values are bound and role identifiers come from a reviewed allowlist.
- Any downsampling method and loss of detail are disclosed.

## Stretch and reflection

Which provenance fields should survive an exported figure so another reviewer can reproduce it?

Save your SQL, actual output, and one explanation in `student-work/sql/day82/`. Use only `brickts_course`; see [this week’s primary references](SOURCES.md#week-12).

[Previous: Day 81](day81.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 83](day83.md)
