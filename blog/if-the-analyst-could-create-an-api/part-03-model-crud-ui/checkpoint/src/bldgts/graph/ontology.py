"""Ontology handle for the live app.

The live model is Haystack-marker based. No Brick ontology is loaded. Callers that
still accept an ``ontology`` argument receive an empty graph for compatibility.
"""

from __future__ import annotations

from functools import lru_cache

from rdflib import Graph


@lru_cache(maxsize=1)
def load_ontology() -> Graph:
    return Graph()


# Back-compat alias for older imports during the cutover.
def load_brick_ontology() -> Graph:
    return load_ontology()
