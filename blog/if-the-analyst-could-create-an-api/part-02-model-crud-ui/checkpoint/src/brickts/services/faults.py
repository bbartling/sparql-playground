from __future__ import annotations

from dataclasses import dataclass

from open_fdd.rules import RULES
from rdflib import Graph
from rdflib.namespace import OWL, RDFS

from brickts.graph.namespaces import BLDG, BRICK
from brickts.services.points import validate_equipment_id

ROLE_REQUIREMENTS: dict[str, tuple[str, str | None]] = {
    "duct-static-pressure": ("Supply_Air_Static_Pressure_Sensor", None),
    "duct-static-pressure-sp": ("Supply_Air_Static_Pressure_Setpoint", None),
    "fan-cmd": ("Fan_Speed_Command", "Supply_Fan"),
    "fan-status": ("Fan_Status", "Supply_Fan"),
    "return-fan-cmd": ("Fan_Speed_Command", "Return_Fan"),
    "discharge-air-temp": ("Supply_Air_Temperature_Sensor", None),
    "discharge-air-temp-sp": ("Supply_Air_Temperature_Setpoint", None),
    "mixed-air-temp": ("Mixed_Air_Temperature_Sensor", None),
    "return-air-temp": ("Return_Air_Temperature_Sensor", None),
    "outside-air-temp": ("Outside_Air_Temperature_Sensor", None),
    "outside-air-damper": ("Damper_Position_Command", "Outside_Damper"),
    "cooling-valve": ("Valve_Position_Command", "Chilled_Water_Valve"),
    "heating-valve": ("Valve_Position_Command", "Hot_Water_Valve"),
    "occupied": ("Occupancy_Command", None),
    "web-outside-air-temp": ("Outside_Air_Temperature_Sensor", "Weather_Station"),
}

ROLE_ASK_OWNER = """
ASK {
  ?point brick:isPointOf ?owner .
  ?owner (brick:isPartOf|^brick:hasPart)* ?equip .
  ?point a/(rdfs:subClassOf|owl:equivalentClass|^owl:equivalentClass)* ?cls .
  FILTER(?cls = ?targetClass)
  ?owner a/(rdfs:subClassOf|owl:equivalentClass|^owl:equivalentClass)* ?ownerCls .
  FILTER(?ownerCls = ?targetOwnerClass)
}
"""

ROLE_ASK_NO_OWNER = """
ASK {
  ?point (brick:isPointOf|^brick:hasPoint) ?owner .
  ?owner (brick:isPartOf|^brick:hasPart)* ?equip .
  ?point a/(rdfs:subClassOf|owl:equivalentClass|^owl:equivalentClass)* ?cls .
  FILTER(?cls = ?targetClass)
}
"""


@dataclass
class FaultRow:
    rule_id: str
    title: str
    applicable: bool
    generic: bool
    reason: str


def equipment_kind(union: Graph, equipment_id: str) -> str | None:
    equip = BLDG[equipment_id]
    ask = """
    ASK {
      ?equip a/(rdfs:subClassOf|owl:equivalentClass)* brick:Air_Handler_Unit .
    }
    """
    if bool(
        union.query(
            ask,
            initNs={"brick": BRICK, "rdfs": RDFS, "owl": OWL},
            initBindings={"equip": equip},
        )
    ):
        return "ahu"
    return None


def _role_satisfied(
    union: Graph, equipment_id: str, role: str, cache: dict[tuple[str, str], bool]
) -> tuple[bool, str]:
    key = (equipment_id, role)
    if key in cache:
        return cache[key], ""
    req = ROLE_REQUIREMENTS.get(role)
    if req is None:
        cache[key] = False
        return False, "no Brick mapping for role"
    brick_class, owner_class = req
    equip = BLDG[equipment_id]
    target = BRICK[brick_class]
    bindings = {"equip": equip, "targetClass": target}
    if owner_class:
        bindings["targetOwnerClass"] = BRICK[owner_class]
        ok = bool(
            union.query(
                ROLE_ASK_OWNER,
                initNs={"brick": BRICK, "rdfs": RDFS, "owl": OWL},
                initBindings=bindings,
            )
        )
    else:
        ok = bool(
            union.query(
                ROLE_ASK_NO_OWNER,
                initNs={"brick": BRICK, "rdfs": RDFS, "owl": OWL},
                initBindings=bindings,
            )
        )
    cache[key] = ok
    if not ok:
        return False, f"missing role {role}"
    return True, ""


def list_faults(
    union: Graph,
    equipment_id: str,
    *,
    include_generic: bool = True,
) -> list[FaultRow]:
    validate_equipment_id(equipment_id)
    kind = equipment_kind(union, equipment_id)
    if kind is None:
        return []
    cache: dict[tuple[str, str], bool] = {}
    rows: list[FaultRow] = []
    for rule in RULES:
        if kind not in getattr(rule, "equipment_kinds", ()):
            continue
        required = list(getattr(rule, "required_roles", ()) or ())
        if not required:
            rows.append(
                FaultRow(
                    rule_id=rule.id,
                    title=getattr(rule, "title", rule.id),
                    applicable=True,
                    generic=True,
                    reason="no required roles",
                )
            )
            continue
        missing = []
        for role in required:
            ok, reason = _role_satisfied(union, equipment_id, role, cache)
            if not ok:
                missing.append(reason or role)
        applicable = len(missing) == 0
        if applicable or include_generic:
            rows.append(
                FaultRow(
                    rule_id=rule.id,
                    title=getattr(rule, "title", rule.id),
                    applicable=applicable,
                    generic=False,
                    reason="; ".join(missing) if missing else "",
                )
            )
    return rows
