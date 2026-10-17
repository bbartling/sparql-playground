import pytest

from brickts.graph.sparql_guard import SparqlRejected, SparqlSyntaxError, prepare_sparql
from brickts.settings import Settings


def test_allows_select():
    s = Settings()
    prepare_sparql("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1", s)


def test_rejects_update():
    s = Settings()
    with pytest.raises(SparqlRejected):
        prepare_sparql('INSERT DATA { <http://ex/s> <http://ex/p> "x" }', s)


def test_rejects_service():
    s = Settings()
    with pytest.raises(SparqlRejected):
        prepare_sparql(
            "SELECT * WHERE { SERVICE <http://example.org/sparql> { ?s ?p ?o } }",
            s,
        )


def test_rejects_from():
    s = Settings()
    with pytest.raises(SparqlRejected):
        prepare_sparql("SELECT * FROM <http://ex/g> WHERE { ?s ?p ?o }", s)


def test_rejects_long():
    s = Settings(sparql_max_query_chars=10)
    with pytest.raises(SparqlRejected):
        prepare_sparql("SELECT ?s WHERE { ?s ?p ?o }", s)


def test_bad_syntax():
    s = Settings()
    with pytest.raises(SparqlSyntaxError):
        prepare_sparql("SELEC broken", s)
