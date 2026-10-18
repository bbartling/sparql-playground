"""Haystack-native site structure for BUILDING_50 (no Brick classes).

Flat topology: site → AHUs only. No floors, zones, or equipment parts —
points attach directly via equipRef to their AHU.
"""

from __future__ import annotations

from rdflib import Graph, Literal
from rdflib.namespace import RDFS

from bldgts.graph.namespaces import BLDG, BTS, RDF, REF
from bldgts.haystack.rdf import add_markers, add_tag, declare_entity

SITE_ID = "Building_50"
SITE_TZ = "America/Chicago"

AHUS: list[tuple[str, str]] = [
    ("AHU_1", "AHU_1"),
    ("AHU_2", "AHU_2"),
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

    for ahu_id, ahu_label in AHUS:
        ahu = BLDG[ahu_id]
        declare_entity(g, ahu)
        g.add((ahu, RDFS.label, Literal(ahu_label)))
        add_markers(g, ahu, ["equip", "ahu"])
        add_tag(g, ahu, "siteRef", "Ref", SITE_ID)

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
