"""Explicit, typed Haystack metadata stored in the application's RDF model.

This is an application RDF mapping, not a claim to implement a Haystack wire
format. Each ``bts:hasHaystackTag`` node carries name, kind and RDF value so the
same metadata is discoverable through the existing read-only SPARQL endpoint.
Entity levels come from Haystack markers and opaque timeseries refs — not Brick.
"""

from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from bldgts.graph.namespaces import BLDG, BTS, REF
from bldgts.haystack.defs import is_subtype, load_defs_index

TAG_KINDS = frozenset({"Str", "Ref", "Number", "Bool"})
FUNCTION_MARKERS = frozenset({"sensor", "cmd", "sp", "synthetic"})
KNOWN_TYPES = {
    "kind": "Str",
    "siteRef": "Ref",
    "equipRef": "Ref",
    "spaceRef": "Ref",
    "unit": "Str",
    "tz": "Str",
    "hisMode": "Str",
    "enum": "Str",
    "dis": "Str",
    "description": "Str",
    "precision": "Number",
    "minVal": "Number",
    "maxVal": "Number",
}
PROFILE = "Application Haystack core profile (not full ontology conformance)"
PROFILE_LIMITS = [
    "Point kinds supported: Number, Bool, Str; metadata values: Str, Ref, Number, Bool.",
    "Validates core tags, references, history metadata and standard unit membership.",
    "Does not validate quantity/unit dimensions, every equipment taxonomy rule or live values.",
    "Uses an application RDF mapping; does not implement a Haystack Zinc/JSON server.",
]


def local_name(iri: URIRef) -> str:
    return str(iri).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def markers_of(g: Graph, entity: URIRef) -> set[str]:
    return {str(m) for m in g.objects(entity, BTS.hasHaystackMarker)}


def entity_level(g: Graph, entity: URIRef, ontology: Graph | None = None) -> str:
    """Determine level from Haystack markers / timeseries refs (ontology unused)."""
    del ontology  # Live app no longer unions a Brick ontology.
    present = (
        (entity, RDF.type, None) in g
        or (entity, BTS.hasHaystackMarker, None) in g
        or (entity, BTS.hasHaystackTag, None) in g
        or (entity, REF.hasExternalReference, None) in g
    )
    if not present:
        raise ValueError(f"entity not found: {local_name(entity)}")
    marks = markers_of(g, entity)
    if "point" in marks or (entity, REF.hasExternalReference, None) in g:
        return "point"
    if "site" in marks:
        return "site"
    if "floor" in marks:
        return "floor"
    if "space" in marks:
        return "space"
    if "equip" in marks:
        meta = metadata(g, entity)
        parent = meta.get("equipRef", {})
        if parent.get("kind") == "Ref":
            parent_iri = (
                URIRef(str(parent["value"]))
                if ":" in str(parent["value"])
                else BLDG[str(parent["value"])]
            )
            if "equip" in markers_of(g, parent_iri):
                return "part"
        return "equip"
    raise ValueError(f"entity is not an editable model entity: {local_name(entity)}")


def metadata(g: Graph, entity: URIRef) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for tag in g.objects(entity, BTS.hasHaystackTag):
        name = g.value(tag, BTS.tagName)
        kind = g.value(tag, BTS.tagKind)
        value = g.value(tag, BTS.tagValue)
        if name is None or kind is None or value is None:
            continue
        tag_kind = str(kind)
        if tag_kind == "Ref":
            val: Any = local_name(value) if str(value).startswith(str(BLDG)) else str(value)
        elif tag_kind in {"Bool", "Number"}:
            val = value.toPython() if isinstance(value, Literal) else str(value)
        else:
            val = str(value)
        out[str(name)] = {"kind": tag_kind, "value": val}
    return dict(sorted(out.items()))


def replace_metadata(g: Graph, entity: URIRef, values: dict[str, Any]) -> None:
    """Replace an entity's explicit metadata, rejecting malformed JSON types."""
    if not isinstance(values, dict) or len(values) > 128:
        raise ValueError("metadata must be an object with at most 128 tags")
    parsed: list[tuple[str, str, URIRef | Literal]] = []
    for name, entry in values.items():
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][A-Za-z0-9]*", name):
            raise ValueError(f"invalid Haystack tag name: {name}")
        if load_defs_index().get(name, {}).get("kind") == "marker":
            raise ValueError(f"{name} is a marker; put it in markers, not value metadata")
        if not isinstance(entry, dict) or set(entry) != {"kind", "value"}:
            raise ValueError(f"{name}: typed metadata requires kind and value")
        kind, val = entry["kind"], entry["value"]
        if not isinstance(kind, str) or kind not in TAG_KINDS:
            raise ValueError(f"{name}: unsupported metadata kind: {kind}")
        if kind in {"Str", "Ref"}:
            if not isinstance(val, str) or len(val) > 2048 or not val.strip():
                raise ValueError(f"{name}: {kind} requires nonempty text (max 2048 characters)")
            if kind == "Ref":
                if re.search(r'[\s<>"{}|\\^`]', val):
                    raise ValueError(f"{name}: Ref contains invalid IRI characters")
                if ":" not in val and not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", val):
                    raise ValueError(f"{name}: Ref must be an entity ID or absolute IRI")
                if ":" in val and not re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", val):
                    raise ValueError(f"{name}: Ref must be an entity ID or absolute IRI")
            term = (URIRef(val) if ":" in val else BLDG[val]) if kind == "Ref" else Literal(val)
        elif kind == "Bool":
            if not isinstance(val, bool):
                raise ValueError(f"{name}: Bool requires true or false")
            term = Literal(val, datatype=XSD.boolean)
        else:
            try:
                finite = math.isfinite(val) if isinstance(val, int | float) else False
            except OverflowError:
                finite = False
            if isinstance(val, bool) or not finite:
                raise ValueError(f"{name}: Number requires a finite JSON number")
            term = Literal(val)
        parsed.append((name, kind, term))
    for tag in list(g.objects(entity, BTS.hasHaystackTag)):
        g.remove((entity, BTS.hasHaystackTag, tag))
        g.remove((tag, None, None))
    for name, kind, term in parsed:
        tag = BNode()
        g.add((entity, BTS.hasHaystackTag, tag))
        g.add((tag, BTS.tagName, Literal(name)))
        g.add((tag, BTS.tagKind, Literal(kind)))
        g.add((tag, BTS.tagValue, term))


@lru_cache(maxsize=256)
def _timezone(value: str) -> str | None:
    """Resolve IANA names and unambiguous Haystack city suffixes."""
    try:
        return ZoneInfo(value).key
    except (ZoneInfoNotFoundError, ValueError):
        if "/" not in value:
            matches = sorted(z for z in available_timezones() if z.endswith("/" + value))
            if len(matches) == 1:
                return matches[0]
    return None


def _ref(value: str) -> URIRef:
    return URIRef(value) if ":" in value else BLDG[value]


@lru_cache(maxsize=1)
def _units() -> frozenset[str]:
    enum = str(load_defs_index().get("unit", {}).get("enum", ""))
    result = set()
    for line in enum.splitlines():
        match = re.match(r"- (.+?): ([^\s(]+)", line)
        if match:
            result.update(match.groups())
    return frozenset(result)


def _enum_names(value: str) -> list[str]:
    if value.lstrip().startswith("-"):
        return [
            line.strip()[1:].strip().split(":", 1)[0].strip()
            for line in value.splitlines()
            if line.strip().startswith("-")
        ]
    return [part.strip() for part in re.split(r"[,\n]", value)]


def validate_entity(g: Graph, entity: URIRef, level: str | None = None) -> dict[str, Any]:
    """Validate the supported Haystack profile without manufacturing metadata.

    Errors are required/malformed modeling; warnings are recommendations. This
    focused profile is deliberately not a full Project Haystack ontology checker.
    """
    level = level or entity_level(g, entity)
    tags = metadata(g, entity)
    markers = {str(m) for m in g.objects(entity, BTS.hasHaystackMarker)}
    issues: list[dict[str, str]] = []

    def issue(tag: str, message: str, severity: str = "error") -> None:
        issues.append({"severity": severity, "tag": tag, "message": message})

    def value(tag: str) -> Any:
        return tags.get(tag, {}).get("value")

    def required(tag: str) -> None:
        if tag not in tags:
            issue(tag, f"Add {tag} metadata.")

    index = load_defs_index()
    for marker in sorted(markers):
        if index.get(marker, {}).get("kind") != "marker":
            issue(marker, f"{marker} is not a marker in the vendored Haystack definitions.")
    for name, entry in tags.items():
        expected = KNOWN_TYPES.get(name)
        if expected and entry["kind"] != expected:
            issue(name, f"{name} must be {expected}, not {entry['kind']}.")
    for name in ("siteRef", "equipRef", "spaceRef"):
        if name not in tags or tags[name]["kind"] != "Ref":
            continue
        raw = str(value(name))
        target = _ref(raw)
        if (target, RDF.type, None) not in g or (
            target,
            BTS.hidden,
            Literal(True, datatype=XSD.boolean),
        ) in g:
            issue(name, f"{name} must reference an existing visible model entity.")
            continue
        try:
            target_level = entity_level(g, target)
        except ValueError:
            target_level = "unknown"
        allowed = {
            "siteRef": {"site", "building"},
            "equipRef": {"equip", "part"},
            "spaceRef": {"floor", "space"},
        }[name]
        if target == entity or target_level not in allowed:
            issue(name, f"{name} references the wrong entity type.")
        # A building or legacy Brick type is only a migration hint: a target
        # must be explicitly tagged before its reference can count as modeled.
        required_marker = {"siteRef": "site", "equipRef": "equip", "spaceRef": "space"}[name]
        target_markers = {str(m) for m in g.objects(target, BTS.hasHaystackMarker)}
        if required_marker not in target_markers:
            issue(name, f"Referenced entity needs its explicit {required_marker} marker.")
        if name == "equipRef":
            seen = {entity}
            cursor = target
            while cursor not in seen:
                seen.add(cursor)
                parent = metadata(g, cursor).get("equipRef", {})
                if parent.get("kind") != "Ref":
                    break
                cursor = _ref(str(parent["value"]))
            else:
                issue(name, "Equipment containment must not contain a cycle.")
            owner_site = metadata(g, target).get("siteRef", {})
            if (
                tags.get("siteRef", {}).get("kind") == "Ref"
                and owner_site.get("kind") == "Ref"
                and _ref(str(value("siteRef"))) != _ref(str(owner_site["value"]))
            ):
                issue("siteRef", "Entity and referenced equipment must belong to the same site.")

    if level == "point":
        if "point" not in markers:
            issue("point", "Add the point marker.")
        functions = {
            function
            for function in FUNCTION_MARKERS
            if any(is_subtype(marker, function) for marker in markers)
        }
        if len(functions) != 1:
            issue("function", "Choose exactly one point function: sensor, cmd, sp, or synthetic.")
        for name in ("kind", "siteRef", "equipRef"):
            required(name)
        if "kind" in tags and value("kind") not in {"Number", "Bool", "Str"}:
            issue("kind", "Point kind must be Number, Bool, or Str in this app profile.")
        if value("kind") == "Number" and "unit" not in tags:
            issue(
                "unit", "Consider a unit for a numeric point; unitless values are valid.", "warning"
            )
        if value("kind") == "Str" and "enum" not in tags:
            issue("enum", "Consider enum for a string point with a fixed set of states.", "warning")
        if "his" in markers:
            required("tz")
            required("hisMode")
            if "hisMode" in tags and value("hisMode") not in {"sampled", "cov", "consumption"}:
                issue("hisMode", "hisMode must be sampled, cov, or consumption.")
            site_raw = value("siteRef")
            if isinstance(site_raw, str):
                site = URIRef(site_raw) if ":" in site_raw else BLDG[site_raw]
                site_tz = metadata(g, site).get("tz", {}).get("value")
                if not site_tz:
                    issue("tz", "Historized points require an explicit timezone on their site.")
                elif "tz" in tags and _timezone(str(value("tz"))) != _timezone(str(site_tz)):
                    issue("tz", "Historized point timezone must match its site timezone.")
        if "hisMode" in tags and "his" not in markers:
            issue("hisMode", "hisMode requires the his marker.")
        if "hisTotalized" in markers and ("his" not in markers or value("kind") != "Number"):
            issue("hisTotalized", "hisTotalized requires his and a Number point kind.")
    elif level in {"equip", "part"}:
        if "equip" not in markers:
            issue("equip", "Add the equip marker.")
        required("siteRef")
    elif level in {"site", "building"}:
        if "site" not in markers:
            issue("site", "Add the site marker.")
        if "tz" not in tags:
            issue("tz", "Consider setting the site timezone for historized points.", "warning")
    elif level in {"floor", "space"}:
        if "space" not in markers:
            issue("space", "Add the space marker for this location.")
        required("siteRef")
    if "tz" in tags and not _timezone(str(value("tz"))):
        issue("tz", "Use a valid IANA timezone or unambiguous Haystack timezone name.")
    if "unit" in tags:
        if value("kind") != "Number":
            issue("unit", "unit is valid only for Number points in this profile.")
        elif tags["unit"]["kind"] == "Str" and value("unit") not in _units():
            issue("unit", "Use a standard unit symbol or name from the vendored unit database.")
    numeric_bounds = []
    for bound in ("minVal", "maxVal"):
        if bound not in tags:
            continue
        if value("kind") != "Number":
            issue(bound, f"{bound} is valid only for Number points.")
        if tags[bound]["kind"] == "Number":
            numeric_bounds.append(bound)
    if len(numeric_bounds) == 2 and value("minVal") > value("maxVal"):
        issue("minVal", "minVal must be less than or equal to maxVal.")
    if "enum" in tags and tags["enum"]["kind"] == "Str":
        names = _enum_names(str(value("enum")))
        if value("kind") not in {"Bool", "Str"}:
            issue("enum", "enum is valid only for Bool or Str points.")
        elif "::" in str(value("enum")):
            issue(
                "enum",
                "External Xeto enum specifications are not verified by this profile.",
                "warning",
            )
        elif not all(names) or len(set(names)) != len(names):
            issue("enum", "Enumeration names must be nonempty and unique.")
        elif value("kind") == "Bool" and len(names) != 2:
            issue("enum", "Bool enums require two names in false,true order.")
    if "precision" in tags and (
        tags["precision"]["kind"] != "Number"
        or not isinstance(value("precision"), int)
        or value("precision") < 0
    ):
        issue("precision", "precision must be a nonnegative integer.")
    status = (
        "red"
        if any(i["severity"] == "error" for i in issues)
        else ("yellow" if issues else "green")
    )
    return {"metadata": tags, "issues": issues, "status": status, "complete": status != "red"}
