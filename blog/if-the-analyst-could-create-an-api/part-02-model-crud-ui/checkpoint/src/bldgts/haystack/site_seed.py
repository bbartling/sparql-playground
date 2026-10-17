"""Haystack-native site structure for BUILDING_50 (no Brick classes)."""

from __future__ import annotations

from rdflib import Graph, Literal
from rdflib.namespace import RDFS

from bldgts.graph.namespaces import BLDG, BTS, RDF, REF
from bldgts.haystack.rdf import add_markers, add_tag, declare_entity

SITE_ID = "Building_50"
SITE_TZ = "America/Chicago"

# (zone_id, label, floor_id, serving_ahu)
ZONES: list[tuple[str, str, str, str]] = [
    ("Zone_AHU_1", "Zone AHU 1", "Floor_1", "AHU_1"),
    ("Zone_VAVFC_125", "Zone VAVFC 125", "Floor_1", "AHU_1"),
    ("Zone_VAVHM_110", "Zone VAVHM 110", "Floor_1", "AHU_1"),
    ("Zone_VAVH_102", "Zone VAVH 102", "Floor_1", "AHU_1"),
    ("Zone_VAVH_122", "Zone VAVH 122", "Floor_1", "AHU_1"),
    ("Zone_VAVM_123", "Zone VAVM 123", "Floor_1", "AHU_1"),
    ("Zone_VAV_100", "Zone VAV 100", "Floor_1", "AHU_1"),
    ("Zone_VAV_104", "Zone VAV 104", "Floor_1", "AHU_1"),
    ("Zone_VAV_105", "Zone VAV 105", "Floor_1", "AHU_1"),
    ("Zone_VAV_107", "Zone VAV 107", "Floor_1", "AHU_1"),
    ("Zone_VAV_111", "Zone VAV 111", "Floor_1", "AHU_1"),
    ("Zone_VAV_116", "Zone VAV 116", "Floor_1", "AHU_1"),
    ("Zone_VAV_120", "Zone VAV 120", "Floor_1", "AHU_1"),
    ("Zone_VAV_121", "Zone VAV 121", "Floor_1", "AHU_1"),
    ("Zone_VAV_124", "Zone VAV 124", "Floor_1", "AHU_1"),
    ("Zone_AHU_2", "Zone AHU 2", "Floor_2", "AHU_2"),
    ("Zone_VAVH_2D302", "Zone VAVH 2D302", "Floor_3", "AHU_2"),
    ("Zone_VAVH_2D306", "Zone VAVH 2D306", "Floor_3", "AHU_2"),
    ("Zone_VAVH_2D311", "Zone VAVH 2D311", "Floor_3", "AHU_2"),
    ("Zone_VAVH_2D313", "Zone VAVH 2D313", "Floor_3", "AHU_2"),
    ("Zone_VAVH_2D316", "Zone VAVH 2D316", "Floor_3", "AHU_2"),
    ("Zone_VAVH_2D319", "Zone VAVH 2D319", "Floor_3", "AHU_2"),
    ("Zone_VAVH_2D324", "Zone VAVH 2D324", "Floor_3", "AHU_2"),
    ("Zone_VAVH_2D325", "Zone VAVH 2D325", "Floor_3", "AHU_2"),
    ("Zone_VAVH_2D326", "Zone VAVH 2D326", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D301", "Zone VAV 2D301", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D303", "Zone VAV 2D303", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D304", "Zone VAV 2D304", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D305", "Zone VAV 2D305", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D307", "Zone VAV 2D307", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D308", "Zone VAV 2D308", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D309", "Zone VAV 2D309", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D310", "Zone VAV 2D310", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D312", "Zone VAV 2D312", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D314", "Zone VAV 2D314", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D315", "Zone VAV 2D315", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D317", "Zone VAV 2D317", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D318", "Zone VAV 2D318", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D320", "Zone VAV 2D320", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D321", "Zone VAV 2D321", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D322", "Zone VAV 2D322", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D323", "Zone VAV 2D323", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D327", "Zone VAV 2D327", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D328", "Zone VAV 2D328", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D329", "Zone VAV 2D329", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D330", "Zone VAV 2D330", "Floor_3", "AHU_2"),
    ("Zone_VAV_2D331", "Zone VAV 2D331", "Floor_3", "AHU_2"),
]

# (part_id, label, markers…)
AHU_PARTS: list[tuple[str, str, tuple[str, ...]]] = [
    ("Supply_Fan", "Supply Fan", ("equip", "fan")),
    ("Return_Fan", "Return Fan", ("equip", "fan")),
    ("OA_Damper", "Outside Air Damper", ("equip", "damper")),
    ("EA_Damper", "Exhaust Air Damper", ("equip", "damper")),
    ("CHW_Valve", "CHW Valve", ("equip", "valve")),
]


def build_site_graph() -> Graph:
    g = Graph()
    g.bind("bldg", BLDG)
    g.bind("bts", BTS)
    g.bind("ref", REF)
    g.bind("rdfs", RDFS)

    site = BLDG[SITE_ID]
    declare_entity(g, site)
    g.add((site, RDFS.label, Literal("BUILDING_50")))
    add_markers(g, site, ["site"])
    add_tag(g, site, "tz", "Str", SITE_TZ)

    floors = {
        "Floor_1": "First Floor",
        "Floor_2": "Second Floor",
        "Floor_3": "Third Floor",
    }
    for fid, label in floors.items():
        floor = BLDG[fid]
        declare_entity(g, floor)
        g.add((floor, RDFS.label, Literal(label)))
        add_markers(g, floor, ["space", "floor"])
        add_tag(g, floor, "siteRef", "Ref", SITE_ID)

    for ahu_id, ahu_label in (("AHU_1", "AHU_1"), ("AHU_2", "AHU_2")):
        ahu = BLDG[ahu_id]
        declare_entity(g, ahu)
        g.add((ahu, RDFS.label, Literal(ahu_label)))
        add_markers(g, ahu, ["equip", "ahu"])
        add_tag(g, ahu, "siteRef", "Ref", SITE_ID)
        for part_suffix, part_label, part_markers in AHU_PARTS:
            part_id = f"{ahu_id}_{part_suffix}"
            part = BLDG[part_id]
            declare_entity(g, part)
            g.add((part, RDFS.label, Literal(part_label)))
            add_markers(g, part, list(part_markers))
            add_tag(g, part, "siteRef", "Ref", SITE_ID)
            add_tag(g, part, "equipRef", "Ref", ahu_id)

    for zone_id, label, floor_id, _ahu_id in ZONES:
        zone = BLDG[zone_id]
        declare_entity(g, zone)
        g.add((zone, RDFS.label, Literal(label)))
        add_markers(g, zone, ["space"])
        add_tag(g, zone, "siteRef", "Ref", SITE_ID)
        add_tag(g, zone, "spaceRef", "Ref", floor_id)

    db = BLDG.timeseries_db
    g.add((db, RDF.type, REF.Database))
    g.add((db, RDFS.label, Literal("SQLite timeseries store (tutorial stand-in for a TSDB)")))
    g.add((db, BTS.backend, Literal("sqlite")))
    g.add((db, BTS.connectionEnv, Literal("BLDGTS_DB_PATH")))
    g.add(
        (
            db,
            BTS.schemaDescription,
            Literal("samples(timeseries_id TEXT, ts INTEGER epoch-s UTC, value REAL)"),
        )
    )
    return g
