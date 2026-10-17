from __future__ import annotations

from functools import lru_cache

import brickschema
from rdflib import Graph


@lru_cache(maxsize=1)
def load_brick_ontology() -> Graph:
    g = brickschema.Graph(load_brick=True)
    return g
