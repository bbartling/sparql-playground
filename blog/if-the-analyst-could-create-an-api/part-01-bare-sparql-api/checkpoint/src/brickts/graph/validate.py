from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph

VALIDATION_QUERIES = {
    "missing_refs": Path(__file__).resolve().parent.parent / "sparql/examples/missing_refs.rq",
    "multi_timeseries_id": Path(__file__).resolve().parent.parent
    / "sparql/examples/multi_timeseries_id.rq",
    "refs_without_database": Path(__file__).resolve().parent.parent
    / "sparql/examples/refs_without_database.rq",
}


@dataclass
class ValidationIssue:
    check: str
    message: str
    count: int


def run_sparql_checks(model: Graph, ontology: Graph) -> list[ValidationIssue]:
    union = model + ontology
    issues: list[ValidationIssue] = []
    for name, path in VALIDATION_QUERIES.items():
        text = path.read_text()
        rows = list(union.query(text))
        issues.append(
            ValidationIssue(
                check=name,
                message=f"{name}: {len(rows)} rows",
                count=len(rows),
            )
        )
    return issues


def run_shacl(model: Graph, ontology: Graph) -> tuple[bool, str]:
    try:
        from pyshacl import validate
    except ImportError:
        return True, "pyshacl not installed; skipped"
    conforms, _, report = validate(
        model,
        shacl_graph=ontology,
        ont_graph=ontology,
        inference="rdfs",
        abort_on_first=False,
    )
    if report is None:
        return bool(conforms), ""
    if isinstance(report, str):
        return bool(conforms), report
    return bool(conforms), report.serialize(format="txt")
