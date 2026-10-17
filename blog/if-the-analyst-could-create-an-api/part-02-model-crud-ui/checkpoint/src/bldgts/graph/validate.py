from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from bldgts.graph.namespaces import BLDG, BRICK, REF
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS

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
    severity: str = "error"  # error | warn
    samples: list[str] | None = None


def run_sparql_checks(model: Graph, ontology: Graph) -> list[ValidationIssue]:
    union = model + ontology
    issues: list[ValidationIssue] = []
    for name, path in VALIDATION_QUERIES.items():
        if not path.is_file():
            continue
        text = path.read_text()
        rows = list(union.query(text))
        issues.append(
            ValidationIssue(
                check=name,
                message=f"{name}: {len(rows)} rows",
                count=len(rows),
                severity="error" if rows else "ok",
                samples=[str(r[0]) for r in rows[:5] if r],
            )
        )
    return issues


def _local(iri: URIRef) -> str:
    text = str(iri)
    if "#" in text:
        return text.rsplit("#", 1)[-1]
    return text.rsplit("/", 1)[-1]


def _is_point(g: Graph, iri: URIRef) -> bool:
    if (iri, REF.hasExternalReference, None) in g:
        return True
    for _, _, t in g.triples((iri, RDF.type, None)):
        name = _local(URIRef(t))
        if "Point" in name or "Sensor" in name or "Setpoint" in name or "Status" in name:
            return True
    return False


def run_rdf_integrity(model: Graph, ontology: Graph | None = None) -> dict[str, Any]:
    """Generic RDF model hygiene: orphans, duplicate refs/labels, missing wiring."""
    g = model
    issues: list[ValidationIssue] = []

    # Points with a timeseries ref but missing owner (orphan points).
    orphans: list[str] = []
    for s, _, _ in g.triples((None, REF.hasExternalReference, None)):
        point = URIRef(s)
        has_owner = (point, BRICK.isPointOf, None) in g or (None, BRICK.hasPoint, point) in g
        if not has_owner:
            orphans.append(_local(point))
    if orphans:
        issues.append(
            ValidationIssue(
                check="orphan_points",
                message="Points with timeseries refs but no equipment/part owner",
                count=len(orphans),
                severity="error",
                samples=orphans[:8],
            )
        )

    # Duplicate timeseries ids across different points.
    by_ts: dict[str, list[str]] = defaultdict(list)
    for s, _, ref in g.triples((None, REF.hasExternalReference, None)):
        point = URIRef(s)
        for tid in g.objects(URIRef(ref), REF.hasTimeseriesId):
            by_ts[str(tid)].append(_local(point))
    dup_ts = {tid: pts for tid, pts in by_ts.items() if len(set(pts)) > 1}
    if dup_ts:
        samples = [f"{tid[:13]}… → {', '.join(pts[:4])}" for tid, pts in list(dup_ts.items())[:5]]
        issues.append(
            ValidationIssue(
                check="duplicate_timeseries_id",
                message="Same timeseries id attached to multiple points",
                count=len(dup_ts),
                severity="error",
                samples=samples,
            )
        )

    # Duplicate rdfs:label among points (ambiguous UI names).
    by_label: dict[str, list[str]] = defaultdict(list)
    for s, _, _ in g.triples((None, REF.hasExternalReference, None)):
        point = URIRef(s)
        labels = list(g.objects(point, RDFS.label))
        if not labels:
            continue
        by_label[str(labels[0]).strip().lower()].append(_local(point))
    dup_labels = {lab: ids for lab, ids in by_label.items() if len(ids) > 1}
    if dup_labels:
        samples = [f"{lab} → {', '.join(ids[:4])}" for lab, ids in list(dup_labels.items())[:5]]
        issues.append(
            ValidationIssue(
                check="duplicate_point_labels",
                message="Multiple points share the same rdfs:label",
                count=len(dup_labels),
                severity="warn",
                samples=samples,
            )
        )

    # Resources typed in the building namespace with no rdf:type (stray subjects).
    typed = {s for s, _, _ in g.triples((None, RDF.type, None))}
    labeled = {s for s, _, _ in g.triples((None, RDFS.label, None))}
    stray = []
    for s in labeled:
        if not str(s).startswith(str(BLDG)):
            continue
        if s not in typed and not _is_point(g, URIRef(s)):
            stray.append(_local(URIRef(s)))
    if stray:
        issues.append(
            ValidationIssue(
                check="untyped_entities",
                message="Building-namespace entities with a label but no rdf:type",
                count=len(stray),
                severity="warn",
                samples=stray[:8],
            )
        )

    # Existing SPARQL contract checks.
    if ontology is not None:
        for issue in run_sparql_checks(model, ontology):
            if issue.count > 0:
                issue.severity = "error"
                issues.append(issue)

    errors = sum(1 for i in issues if i.severity == "error" and i.count > 0)
    warns = sum(1 for i in issues if i.severity == "warn" and i.count > 0)
    if errors:
        status = "red"
    elif warns:
        status = "yellow"
    else:
        status = "green"

    return {
        "status": status,
        "error_count": errors,
        "warn_count": warns,
        "issues": [asdict(i) for i in issues if i.count > 0],
    }


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
