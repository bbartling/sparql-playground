"""Narrow SPARQL UPDATE planner for the agent plan/apply contract (A19).

Only ground INSERT DATA / DELETE DATA against allowlisted metadata predicates.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from bldgts.graph.namespaces import BLDG, BRICK, BTS, REF
from bldgts.haystack.metadata import (
    metadata,
    replace_metadata,
    validate_entity,
)
from bldgts.services.model_crud import _bridge_point_ownership, _write_markers
from pyparsing.exceptions import ParseException
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS
from rdflib.plugins.sparql.algebra import translateUpdate
from rdflib.plugins.sparql.parser import parseUpdate
from rdflib.term import Node

ALLOWED_OPS = frozenset({"InsertData", "DeleteData"})
ALLOWED_PREDICATES = frozenset(
    {
        RDFS.label,
        BTS.hasHaystackMarker,
        BTS.hasHaystackTag,
        BTS.tagName,
        BTS.tagKind,
        BTS.tagValue,
    }
)
PROTECTED_PREDICATES = frozenset(
    {
        RDF.type,
        REF.hasExternalReference,
        REF.hasTimeseriesId,
        REF.storedAt,
        BTS.backend,
        BTS.connectionEnv,
        BTS.schemaDescription,
        BTS.hidden,
        BRICK.hasPoint,
        BRICK.isPointOf,
        BRICK.hasPart,
        BRICK.isPartOf,
        BRICK.isLocatedIn,
        BRICK.feeds,
    }
)
_FORBIDDEN_WORDS = re.compile(
    r"\b(SERVICE|LOAD|CLEAR|DROP|CREATE|MOVE|COPY|ADD|USING|FROM)\b",
    re.IGNORECASE,
)


class AgentUpdateRejected(ValueError):
    """Unsupported or unsafe SPARQL update for the agent planner."""


@dataclass(frozen=True)
class TripleView:
    s: str
    p: str
    o: str
    o_kind: str  # uri | literal | bnode

    def as_dict(self) -> dict[str, str]:
        return {"s": self.s, "p": self.p, "o": self.o, "o_kind": self.o_kind}


def _term_view(term: Node) -> tuple[str, str]:
    if isinstance(term, URIRef):
        return str(term), "uri"
    if isinstance(term, Literal):
        return str(term), "literal"
    if isinstance(term, BNode):
        return f"_:{term}", "bnode"
    return str(term), "other"


def _triple_view(triple: tuple[Node, Node, Node]) -> TripleView:
    s, p, o = triple
    o_text, o_kind = _term_view(o)
    return TripleView(
        s=str(s) if not isinstance(s, BNode) else f"_:{s}", p=str(p), o=o_text, o_kind=o_kind
    )


def _canonical_hash(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _parse_ops(text: str) -> list[tuple[str, list[tuple[Node, Node, Node]]]]:
    if not text or not text.strip():
        raise AgentUpdateRejected("update text is empty")
    if _FORBIDDEN_WORDS.search(text):
        raise AgentUpdateRejected("update contains a forbidden keyword")
    try:
        parsed = parseUpdate(text)
    except ParseException as exc:
        raise AgentUpdateRejected(f"SPARQL UPDATE parse error: {exc}") from exc
    try:
        translated = translateUpdate(parsed)
    except Exception as exc:  # noqa: BLE001 - surface as rejection
        raise AgentUpdateRejected(f"SPARQL UPDATE translate error: {exc}") from exc
    algebra = translated.algebra
    if not isinstance(algebra, list) or not algebra:
        raise AgentUpdateRejected("UPDATE must contain INSERT DATA and/or DELETE DATA")
    ops: list[tuple[str, list[tuple[Node, Node, Node]]]] = []
    for item in algebra:
        name = getattr(item, "name", None) or type(item).__name__
        if name not in ALLOWED_OPS:
            raise AgentUpdateRejected(f"unsupported update operation: {name}")
        quads = item.get("quads") if hasattr(item, "get") else None
        if quads and any(quads.values()):
            raise AgentUpdateRejected("named-graph / GRAPH targets are not allowed")
        triples = list(item.get("triples") or [])
        if not triples:
            raise AgentUpdateRejected(f"{name} contains no triples")
        ops.append((name, triples))
    return ops


def _validate_triple(triple: tuple[Node, Node, Node]) -> None:
    s, p, o = triple
    if not isinstance(p, URIRef):
        raise AgentUpdateRejected("predicates must be IRIs")
    if p in PROTECTED_PREDICATES:
        raise AgentUpdateRejected(f"protected predicate not allowed: {p}")
    if p not in ALLOWED_PREDICATES:
        raise AgentUpdateRejected(f"predicate not allowlisted: {p}")
    if isinstance(s, Literal):
        raise AgentUpdateRejected("literal subjects are not allowed")
    if p == RDFS.label and not isinstance(o, Literal):
        raise AgentUpdateRejected("rdfs:label object must be a literal")
    if p == BTS.hasHaystackMarker and not isinstance(o, Literal):
        raise AgentUpdateRejected("hasHaystackMarker object must be a literal")
    if p == BTS.hasHaystackTag and not isinstance(o, (BNode, URIRef)):
        raise AgentUpdateRejected("hasHaystackTag object must be a blank node or IRI")
    if p in {BTS.tagName, BTS.tagKind} and not isinstance(o, Literal):
        raise AgentUpdateRejected(f"{p} object must be a literal")


def _local(iri: URIRef) -> str:
    text = str(iri)
    return text.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _scope_set(scope_iris: list[str]) -> set[URIRef]:
    out: set[URIRef] = set()
    for raw in scope_iris:
        text = str(raw).strip()
        if not text:
            continue
        if text.startswith("http://") or text.startswith("https://"):
            out.add(URIRef(text))
        elif text.startswith("bldg:"):
            out.add(BLDG[text.split(":", 1)[1]])
        elif "#" in text:
            out.add(URIRef(text))
        else:
            out.add(BLDG[text])
    if not out:
        raise AgentUpdateRejected("scope_iris must list at least one entity IRI or local id")
    return out


def _normalize_scope(scope_iris: list[str]) -> list[str]:
    return sorted({str(iri) for iri in _scope_set(scope_iris)})


def _tag_clusters(
    triples: list[tuple[Node, Node, Node]],
) -> dict[BNode, dict[str, Any]]:
    """Group blank-node tag property triples by BNode id."""
    clusters: dict[BNode, dict[str, Any]] = {}
    for s, p, o in triples:
        if isinstance(s, BNode) and p in {BTS.tagName, BTS.tagKind, BTS.tagValue}:
            entry = clusters.setdefault(s, {})
            if p == BTS.tagName:
                entry["name"] = str(o)
            elif p == BTS.tagKind:
                entry["kind"] = str(o)
            else:
                entry["value_term"] = o
    return clusters


def _entity_from_scope(term: Node, scope: set[URIRef]) -> URIRef | None:
    if isinstance(term, URIRef) and term in scope:
        return term
    return None


def compile_entity_changes(
    g: Graph,
    *,
    deleted: list[tuple[Node, Node, Node]],
    inserted: list[tuple[Node, Node, Node]],
    scope: set[URIRef],
) -> dict[URIRef, dict[str, Any]]:
    """Compile per-entity logical edits; preserve unedited metadata tag names."""
    for triple in deleted + inserted:
        _validate_triple(triple)

    insert_clusters = _tag_clusters(inserted)
    delete_clusters = _tag_clusters(deleted)
    # Map BNode -> owning entity via hasHaystackTag in the same op set.
    owners: dict[BNode, URIRef] = {}
    for s, p, o in inserted + deleted:
        if p == BTS.hasHaystackTag and isinstance(s, URIRef) and isinstance(o, BNode):
            if s not in scope:
                raise AgentUpdateRejected(f"hasHaystackTag subject outside scope: {s}")
            owners[o] = s

    changes: dict[URIRef, dict[str, Any]] = {
        iri: {"markers": None, "label": None, "metadata": None} for iri in scope
    }

    # Start marker/metadata snapshots lazily when first touched.
    def touch(entity: URIRef) -> dict[str, Any]:
        slot = changes[entity]
        if slot["markers"] is None:
            slot["markers"] = {str(m) for m in g.objects(entity, BTS.hasHaystackMarker)}
        if slot["metadata"] is None:
            slot["metadata"] = metadata(g, entity)
        return slot

    for s, p, o in deleted:
        entity = _entity_from_scope(s, scope)
        if p in {BTS.tagName, BTS.tagKind, BTS.tagValue}:
            if not isinstance(s, BNode):
                raise AgentUpdateRejected("tag property deletes must use blank-node subjects")
            owner = owners.get(s)
            if owner is None:
                raise AgentUpdateRejected("tag property delete is not linked to a scoped entity")
            slot = touch(owner)
            cluster = delete_clusters.get(s, {})
            name = cluster.get("name")
            if name and name in slot["metadata"]:
                del slot["metadata"][name]
            continue
        if entity is None:
            if isinstance(s, BNode):
                continue
            raise AgentUpdateRejected(f"delete subject outside scope: {s}")
        slot = touch(entity)
        if p == RDFS.label:
            # Label delete alone clears only if an insert does not replace it.
            slot["label"] = ""
        elif p == BTS.hasHaystackMarker:
            slot["markers"].discard(str(o))
        elif p == BTS.hasHaystackTag and isinstance(o, BNode):
            cluster = delete_clusters.get(o, {})
            name = cluster.get("name")
            if name and name in slot["metadata"]:
                del slot["metadata"][name]

    for s, p, o in inserted:
        entity = _entity_from_scope(s, scope)
        if p in {BTS.tagName, BTS.tagKind, BTS.tagValue}:
            if not isinstance(s, BNode):
                raise AgentUpdateRejected("tag property inserts must use blank-node subjects")
            owner = owners.get(s)
            if owner is None:
                raise AgentUpdateRejected("tag property insert is not linked to a scoped entity")
            slot = touch(owner)
            cluster = insert_clusters.get(s, {})
            name = cluster.get("name")
            kind = cluster.get("kind")
            value_term = cluster.get("value_term")
            if not name or not kind or value_term is None:
                raise AgentUpdateRejected("inserted tag nodes need tagName, tagKind, and tagValue")
            if kind not in {"Str", "Ref", "Number", "Bool"}:
                raise AgentUpdateRejected(f"unsupported tagKind for {name}: {kind}")
            if kind == "Ref":
                if not isinstance(value_term, URIRef):
                    raise AgentUpdateRejected(f"{name}: Ref value must be an IRI")
                val: Any = (
                    _local(value_term) if str(value_term).startswith(str(BLDG)) else str(value_term)
                )
            elif kind == "Bool":
                if not isinstance(value_term, Literal):
                    raise AgentUpdateRejected(f"{name}: Bool value must be a literal")
                val = value_term.toPython()
                if not isinstance(val, bool):
                    raise AgentUpdateRejected(f"{name}: Bool value must be true/false")
            elif kind == "Number":
                if not isinstance(value_term, Literal):
                    raise AgentUpdateRejected(f"{name}: Number value must be a literal")
                val = value_term.toPython()
                if isinstance(val, bool) or not isinstance(val, int | float):
                    raise AgentUpdateRejected(f"{name}: Number value must be numeric")
            else:
                val = str(value_term)
            slot["metadata"][name] = {"kind": kind, "value": val}
            continue
        if entity is None:
            if isinstance(s, BNode):
                continue
            raise AgentUpdateRejected(f"insert subject outside scope: {s}")
        slot = touch(entity)
        if p == RDFS.label:
            slot["label"] = str(o)
        elif p == BTS.hasHaystackMarker:
            slot["markers"].add(str(o))
        elif p == BTS.hasHaystackTag:
            # Ownership recorded above; properties processed via BNode subjects.
            touch(entity)

    # Drop untouched entities.
    return {
        iri: slot
        for iri, slot in changes.items()
        if slot["markers"] is not None or slot["label"] is not None or slot["metadata"] is not None
    }


def apply_compiled_changes(g: Graph, changes: dict[URIRef, dict[str, Any]]) -> None:
    """Mutate a graph copy using the same writers as the human UI."""
    for entity, slot in changes.items():
        if (entity, RDF.type, None) not in g:
            raise AgentUpdateRejected(f"entity not found: {_local(entity)}")
        if slot["markers"] is not None:
            _write_markers(g, entity, sorted(slot["markers"]))
        if slot["metadata"] is not None:
            replace_metadata(g, entity, slot["metadata"])
            dis = slot["metadata"].get("dis", {})
            if dis.get("kind") == "Str":
                g.set((entity, RDFS.label, Literal(str(dis["value"]).strip())))
        if slot["label"] is not None:
            text = str(slot["label"]).strip()
            if not text:
                raise AgentUpdateRejected(f"label cannot be empty for {_local(entity)}")
            g.set((entity, RDFS.label, Literal(text)))
            values = metadata(g, entity)
            if "dis" in values:
                values["dis"] = {"kind": "Str", "value": text}
                replace_metadata(g, entity, values)
    for entity in changes:
        _bridge_point_ownership(g, entity)


def profile_issues(g: Graph, entities: set[URIRef]) -> dict[str, Any]:
    reports = []
    for entity in sorted(entities, key=str):
        try:
            report = validate_entity(g, entity)
        except ValueError as exc:
            report = {
                "status": "red",
                "complete": False,
                "issues": [{"severity": "error", "tag": "entity", "message": str(exc)}],
                "metadata": {},
            }
        reports.append({"iri": str(entity), "id": _local(entity), **report})
    errors = sum(1 for r in reports if r["status"] == "red")
    warnings = sum(
        1 for r in reports for issue in r.get("issues") or [] if issue.get("severity") == "warning"
    )
    status = "red" if errors else ("yellow" if warnings else "green")
    return {"status": status, "error_count": errors, "warn_count": warnings, "entities": reports}


def build_plan(
    model: Graph,
    *,
    update_text: str,
    scope_iris: list[str],
    base_revision: int,
    max_triples: int = 500,
) -> dict[str, Any]:
    """Parse, validate, and dry-run a scoped agent update against a model copy."""
    scope = _scope_set(scope_iris)
    for iri in scope:
        if (iri, RDF.type, None) not in model:
            raise AgentUpdateRejected(f"scoped entity not found: {_local(iri)}")

    ops = _parse_ops(update_text)
    deleted: list[tuple[Node, Node, Node]] = []
    inserted: list[tuple[Node, Node, Node]] = []
    for name, triples in ops:
        if len(triples) > max_triples:
            raise AgentUpdateRejected("update exceeds max triple budget")
        if name == "DeleteData":
            deleted.extend(triples)
        else:
            inserted.extend(triples)
    if len(deleted) + len(inserted) > max_triples:
        raise AgentUpdateRejected("update exceeds max triple budget")

    before = profile_issues(model, scope)
    changes = compile_entity_changes(model, deleted=deleted, inserted=inserted, scope=scope)
    if not changes:
        raise AgentUpdateRejected("update does not change any scoped entity")

    trial = Graph()
    for triple in model:
        trial.add(triple)
    try:
        apply_compiled_changes(trial, changes)
    except ValueError as exc:
        raise AgentUpdateRejected(str(exc)) from exc
    after = profile_issues(trial, scope)

    added_views = [_triple_view(t).as_dict() for t in inserted]
    deleted_views = [_triple_view(t).as_dict() for t in deleted]
    affected = sorted(str(iri) for iri in changes)
    body = {
        "base_revision": base_revision,
        "scope_iris": _normalize_scope(scope_iris),
        "affected_iris": affected,
        "added": added_views,
        "deleted": deleted_views,
        "entity_changes": {
            str(iri): {
                "markers": sorted(slot["markers"]) if slot["markers"] is not None else None,
                "label": slot["label"],
                "metadata": slot["metadata"],
            }
            for iri, slot in changes.items()
        },
        "before": before,
        "after": after,
    }
    plan_hash = _canonical_hash(body)
    plan_id = str(uuid4())
    return {
        "plan_id": plan_id,
        "plan_hash": plan_hash,
        **body,
        "_compiled": changes,  # server-only; stripped before HTTP response
    }
