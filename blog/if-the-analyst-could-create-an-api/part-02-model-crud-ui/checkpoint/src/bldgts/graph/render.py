"""Render the Haystack application model + opaque timeseries references."""

from __future__ import annotations

import csv
from pathlib import Path

from bldgts.graph.namespaces import BLDG, REF
from bldgts.haystack.rdf import add_markers, add_tag, declare_entity
from bldgts.haystack.site_seed import SITE_ID, SITE_TZ, build_site_graph
from rdflib import BNode, Graph, Literal
from rdflib.namespace import RDF, RDFS

# CSV still carries a legacy semantic_class column name `brick_class` for stable
# diffs; values are mapped to Haystack markers only — never emitted as Brick RDF.
_UNIT_MAP = {
    "DEG_F": "°F",
    "IN_H2O": "inH₂O",
    "PERCENT": "%",
}

_CLASS_MARKERS: dict[str, tuple[str, ...]] = {
    "Alarm": ("point", "sensor"),
    "Building_Air_Static_Pressure_Sensor": ("point", "sensor", "pressure", "air"),
    "Building_Air_Static_Pressure_Setpoint": ("point", "sp", "pressure", "air"),
    "Valve_Position_Command": ("point", "cmd", "valve"),
    "Supply_Air_Static_Pressure_Sensor": ("point", "sensor", "discharge", "air", "pressure"),
    "Supply_Air_Static_Pressure_Setpoint": ("point", "sp", "discharge", "air", "pressure"),
    "Supply_Air_Temperature_Setpoint": ("point", "sp", "discharge", "air", "temp"),
    "Outside_Air_Temperature_Low_Reset_Setpoint": ("point", "sp", "outside", "air", "temp"),
    "Outside_Air_Temperature_High_Reset_Setpoint": ("point", "sp", "outside", "air", "temp"),
    "Supply_Air_Temperature_High_Reset_Setpoint": ("point", "sp", "discharge", "air", "temp"),
    "Supply_Air_Temperature_Low_Reset_Setpoint": ("point", "sp", "discharge", "air", "temp"),
    "Supply_Air_Temperature_Sensor": ("point", "sensor", "discharge", "air", "temp"),
    "Supply_Air_Temperature_Alarm": ("point", "sensor"),
    "Damper_Position_Setpoint": ("point", "sp", "damper"),
    "Status": ("point", "sensor"),
    "Pressure_Alarm": ("point", "sensor"),
    "Damper_Position_Command": ("point", "cmd", "damper"),
    "Mixed_Air_Temperature_Sensor": ("point", "sensor", "mixed", "air", "temp"),
    "Min_Position_Setpoint_Limit": ("point", "sp", "damper"),
    "Occupancy_Command": ("point", "cmd"),
    "Outside_Air_Temperature_Sensor": ("point", "sensor", "outside", "air", "temp"),
    "Return_Air_Temperature_Sensor": ("point", "sensor", "return", "air", "temp"),
    "Fan_Speed_Command": ("point", "cmd", "speed", "fan"),
    "Fan_Status": ("point", "sensor", "fan"),
    "Start_Stop_Status": ("point", "sensor"),
    "Fan_On_Off_Status": ("point", "sensor", "fan"),
    "Start_Stop_Command": ("point", "cmd"),
    "Thermostat_Status": ("point", "sensor"),
    "Unoccupied_Air_Temperature_Cooling_Setpoint": ("point", "sp", "air", "temp", "cool"),
    "Zone_Air_Temperature_Sensor": ("point", "sensor", "zone", "air", "temp"),
}


def _function_kind(markers: tuple[str, ...], unit: str) -> tuple[str, str]:
    """Return (haystack kind, preferred function already in markers)."""
    if "sp" in markers or "cmd" in markers:
        # Commands/setpoints with engineering units are Number; bare cmds may be Bool.
        if unit:
            return "Number", "Number"
        if "cmd" in markers and not unit:
            return "Bool", "Bool"
        return "Number", "Number"
    if unit:
        return "Number", "Number"
    return "Bool", "Bool"


def _point_markers(brick_class: str, point_id: str) -> list[str]:
    markers = list(_CLASS_MARKERS.get(brick_class, ("point", "sensor")))
    if "point" not in markers:
        markers.insert(0, "point")
    # Historized tutorial points always carry history.
    if "his" not in markers:
        markers.append("his")
    # Name-based refinements when class map is coarse.
    pid = point_id.upper()
    if (
        ("_SP" in pid or pid.endswith("_SP") or "SETPOINT" in pid or "SETPT" in pid)
        and "sp" not in markers
        and "cmd" not in markers
    ):
        markers = [m for m in markers if m != "sensor"]
        markers.append("sp")
    if (
        (pid.endswith("_CMD") or "_CMD" in pid or pid.endswith("_C") or pid.endswith("-C"))
        and "cmd" not in markers
        and "sp" not in markers
    ):
        markers = [m for m in markers if m != "sensor"]
        markers.append("cmd")
    # Exactly one function marker.
    functions = [m for m in ("sensor", "cmd", "sp", "synthetic") if m in markers]
    if len(functions) > 1:
        keep = functions[0]
        markers = [m for m in markers if m not in {"sensor", "cmd", "sp", "synthetic"} or m == keep]
    elif not functions:
        markers.append("sensor")
    return markers


def _serving_ahu(owner_id: str, point_id: str) -> str:
    """Collapse CSV part/zone owners onto the parent AHU (flat tree)."""
    if owner_id.startswith("AHU_1") or point_id.startswith("AHU_1"):
        return "AHU_1"
    if owner_id.startswith("AHU_2") or point_id.startswith("AHU_2"):
        return "AHU_2"
    if "2D" in owner_id or "2D" in point_id:
        return "AHU_2"
    if owner_id.startswith("Zone_AHU_2"):
        return "AHU_2"
    return "AHU_1"


def _add_points_csv(g: Graph, points_csv: Path, db_iri) -> None:
    with points_csv.open(newline="") as f:
        for row in csv.DictReader(f):
            point_id = row["point_id"]
            owner_id = row["owner_id"]
            point_iri = BLDG[point_id]
            declare_entity(g, point_iri)
            g.set((point_iri, RDFS.label, Literal(row["label"])))
            markers = _point_markers(row.get("brick_class") or "", point_id)
            add_markers(g, point_iri, markers)
            unit_raw = (row.get("unit") or "").strip()
            kind, _ = _function_kind(tuple(markers), unit_raw)
            add_tag(g, point_iri, "kind", "Str", kind)
            add_tag(g, point_iri, "siteRef", "Ref", SITE_ID)
            add_tag(g, point_iri, "tz", "Str", SITE_TZ)
            add_tag(g, point_iri, "hisMode", "Str", "sampled")
            if unit_raw and kind == "Number":
                add_tag(g, point_iri, "unit", "Str", _UNIT_MAP.get(unit_raw, unit_raw))
            # Flat ownership: every point equipRefs its AHU (no parts / spaceRef).
            add_tag(g, point_iri, "equipRef", "Ref", _serving_ahu(owner_id, point_id))
            role = (row.get("openfdd_role") or "").strip()
            if role:
                add_tag(g, point_iri, "ofddRole", "Str", role)

            ref = BNode()
            g.add((point_iri, REF.hasExternalReference, ref))
            g.add((ref, RDF.type, REF.TimeseriesReference))
            g.add((ref, REF.hasTimeseriesId, Literal(row["timeseries_id"])))
            g.add((ref, REF.storedAt, db_iri))

def render_model(
    site_path: Path | None,
    points_csv: Path | list[Path],
    db_node: str = "timeseries_db",
) -> Graph:
    """Build the Haystack site + points graph.

    ``site_path`` is accepted for CLI compatibility; the live seed is the
    Haystack site module (Brick site TTL is no longer read).
    """
    del site_path
    g = build_site_graph()
    db_iri = BLDG[db_node]
    paths = [points_csv] if isinstance(points_csv, Path) else list(points_csv)
    for path in paths:
        _add_points_csv(g, path, db_iri)
    return g


def write_turtle(graph: Graph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(graph.serialize(format="turtle"))
