# Day 52 — Follow point ownership through an equipment part tree

[Previous: Day 51](day51.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 53](day53.md)

**Week 8 · 45–75 minutes.** Prerequisites: Days 1–51, or equivalent SQL skills.

## Goal

Discover an AHU's points whether ownership is direct or attached to a component part.

## Before you start

Run `uv run python lessons/sql/graph_lab.py lessons/sql/sparql/day52_owned_points.rq`. The starter model places points directly on AHUs; its zero-length path case is therefore meaningful. It does not contain a fabricated fan subassembly.

## Concept

`brick:isPointOf` links a point to its owner. Equipment can have parts: `brick:isPartOf` walks from child toward parent, while `^brick:hasPart` traverses the inverse of a parent-to-child assertion. The path `(brick:isPartOf|^brick:hasPart)*` accepts either form and zero or more steps. Zero steps let the owner already be the requested AHU.

Do not equate ownership with airflow or spatial containment. A point's owner, a system that feeds a zone and a building containing equipment express different relationships. Keep the intermediate owner in discovery results when it helps explain why a point was selected. A future model with multiple paths may require explicit duplicate checks and sensor-selection policy.

## Tiny example

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
SELECT ?point ?owner ?equipment
WHERE {
  ?equipment a brick:Air_Handler_Unit .
  ?point brick:isPointOf ?owner .
  ?owner (brick:isPartOf|^brick:hasPart)* ?equipment .
}
LIMIT 10
```

This returns metadata associations, not aligned timeseries observations. The supplied file also projects site and teaching role.

## SQL challenge

Discover all points in each AHU's ownership tree. Compare discovered equipment/role pairs with `course.point`, preserving equipment identity and counting selected points per required role. Design the SQL-side audit that would reject a missing or ambiguous pressure-role selection before reading history.

## Experiment

In your copied query, replace `*` with `+`, which requires at least one part-tree step. Predict the result on the direct-ownership fixture. Explain why this differs from simply joining `isPointOf` directly to an AHU when parts exist in a larger model.

## Acceptance checks

- The complete ownership query returns 42 point associations, 14 per AHU.
- Direct ownership works because zero path steps are allowed.
- The `+` experiment has no matching AHU part path in this starter graph.
- Every discovered point retains its site, equipment and explicit role context.

## Stretch and reflection

If two pressure sensors share a role, which selection information is missing? Explain why `LIMIT 1` would conceal that problem rather than resolve it.

Save SQL, actual output and a short interpretation in your own `student-work/sql/day52/` directory. Label evidence **observed**, **fixture-only**, or **not run**. Consult [this week’s primary references](SOURCES.md#week-8) for exact language and domain details.

[Previous: Day 51](day51.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 53](day53.md)
