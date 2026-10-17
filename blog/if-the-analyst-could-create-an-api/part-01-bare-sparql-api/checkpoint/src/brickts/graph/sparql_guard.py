from __future__ import annotations

from dataclasses import dataclass

from pyparsing.exceptions import ParseException
from rdflib.plugins.sparql.algebra import CompValue
from rdflib.plugins.sparql.parser import parseQuery, parseUpdate
from rdflib.plugins.sparql.processor import translateQuery

from brickts.settings import Settings

ALLOWED = {"SelectQuery", "AskQuery", "ConstructQuery", "DescribeQuery"}


class SparqlRejected(Exception):
    pass


class SparqlSyntaxError(Exception):
    pass


@dataclass(frozen=True)
class PreparedSparql:
    query: object
    algebra: object


def _contains(node: object, name: str) -> bool:
    node_name = getattr(node, "name", None) or type(node).__name__
    if node_name == name or str(node_name).startswith(name):
        return True
    if isinstance(node, dict):
        return any(_contains(v, name) for v in node.values())
    if isinstance(node, (list, tuple)):
        return any(_contains(x, name) for x in node)
    for attr in ("values", "part", "triples"):
        if hasattr(node, attr):
            val = getattr(node, attr)
            if val is not None and _contains(val, name):
                return True
    get = getattr(node, "get", None)
    if callable(get):
        for key in ("part", "where", "graph", "triples"):
            if key in node and _contains(node[key], name):
                return True
    return False


def prepare_sparql(text: str, settings: Settings) -> PreparedSparql:
    if len(text) > settings.sparql_max_query_chars:
        raise SparqlRejected("query too long")
    try:
        parsed = parseQuery(text)
    except ParseException as exc:
        try:
            parseUpdate(text)
            raise SparqlRejected("updates are not allowed") from exc
        except ParseException:
            raise SparqlSyntaxError(str(exc)) from exc
    q = parsed[1]
    if q.name not in ALLOWED:
        raise SparqlRejected(f"{q.name} not allowed")
    if "datasetClause" in q and q["datasetClause"]:
        raise SparqlRejected("FROM / FROM NAMED not allowed")
    if _contains(parsed, "ServiceGraphPattern") or "ServiceGraphPattern" in repr(parsed):
        raise SparqlRejected("SERVICE not allowed")
    query = translateQuery(parsed)
    if query.algebra.name == "SelectQuery":
        query.algebra.p = CompValue(
            "Slice",
            p=query.algebra.p,
            start=0,
            length=settings.sparql_max_rows + 1,
        )
    return PreparedSparql(query=query, algebra=query.algebra)


def run_prepared(graph, prepared: PreparedSparql):
    import rdflib.plugins.sparql as sparql

    sparql.SPARQL_LOAD_GRAPHS = False
    return graph.query(prepared.query)
