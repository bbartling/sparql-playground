"""Every lesson day has a pandas script and a SQL script; they must compute the same answers.

The scripts only print (the student compares by eye). Each one also ends with a small RESULTS dict;
this test runs both scripts of a day from the repo root (the scripts use paths like
"data/BUILDING_50/AHU_1/history_wide.csv") and checks every key they share: same rows, same
values, row order and bool-vs-0/1 ignored, NaN == NULL. That's the pattern Open-FDD's parity tests
use (pandas oracle == SQL rule pack).

Run:  uv run pytest -q -m lessons        (CI's `lessons` job; a few minutes)

Weeks 1-4 need only the CSVs in data/ (var/lessons.sqlite is built here if it's missing). Week 5
(data modeling) also needs the API's database and RDF model
(`uv run bldgts model build && uv run bldgts bootstrap`); those days are skipped without them.

Weeks 6-9 (RDF and ontologies by hand, days 26-45) have one script per day, `dayNN_rdf.py`, that
reads small hand-written Turtle files next to it. There is no second script to compare with, so each
day's RESULTS are checked against the expected answers in RDF_EXPECTED below, and each day's burger
"mini challenge" answer is checked too.
"""

from __future__ import annotations

import contextlib
import io
import math
import os
import runpy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from rdflib import Graph, Namespace

ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "lessons"
sys.path.insert(0, str(LESSONS))

import setup_db  # noqa: E402

pytestmark = pytest.mark.lessons
NEEDS_API_DB = ("timeseries.sqlite", "TestClient")


def days() -> list[int]:
    return sorted(int(p.stem[3:5]) for p in LESSONS.glob("unit*/day*_sql.py"))


@pytest.fixture(scope="session")
def lessons_db():
    if not setup_db.db_path().exists():
        with contextlib.redirect_stdout(io.StringIO()):
            setup_db.build()
    old_cwd = os.getcwd()
    os.chdir(ROOT)  # the scripts use paths relative to the repo root
    yield
    os.chdir(old_cwd)


@pytest.fixture
def repo_root():
    """The RDF days (26-45) need no database, only the repo root as the working directory."""
    old_cwd = os.getcwd()
    os.chdir(ROOT)
    yield
    os.chdir(old_cwd)


def run_script(path: Path) -> dict:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ns = runpy.run_path(str(path), run_name="__main__")
    assert out.getvalue().strip(), f"{path.name} printed nothing"
    results = ns.get("RESULTS")
    assert isinstance(results, dict) and results, f"{path.name} has no RESULTS dict"
    return results


# ---------------------------------------------------------------- comparing results
def _frame(x) -> pd.DataFrame:
    if isinstance(x, pd.Series):
        x = x.to_frame()
    # a named index (e.g. after groupby) is data; an unnamed one (after a filter or sort) isn't
    unnamed = all(name is None for name in x.index.names)
    out = x.reset_index(drop=unnamed).copy()
    for col in out.columns:
        if out[col].dtype == bool:
            out[col] = out[col].astype(int)
    return out


def assert_parity(pandas_df, sql_df, *, label: str = "", atol: float = 1e-9) -> None:
    """Same columns, same rows (any order), same values; numbers within atol; NaN == NULL."""
    a, b = _frame(pandas_df), _frame(sql_df)
    assert set(a.columns) == set(b.columns), (
        f"{label} columns differ: {list(a.columns)} vs {list(b.columns)}"
    )
    b = b[list(a.columns)]
    assert len(a) == len(b), f"{label} row counts differ: pandas {len(a)} vs SQL {len(b)}"
    keys = list(a.columns)
    a = a.sort_values(keys, kind="mergesort").reset_index(drop=True)
    b = b.sort_values(keys, kind="mergesort").reset_index(drop=True)
    for col in a.columns:
        x, y = a[col], b[col]
        xn, yn = pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")
        numeric = xn.notna().sum() == x.notna().sum() and yn.notna().sum() == y.notna().sum()
        if numeric:
            ok = np.isclose(
                xn.astype(float), yn.astype(float), atol=atol, rtol=1e-9, equal_nan=True
            )
        else:
            both_null = (x.isna() & y.isna()).to_numpy()
            ok = both_null | (x.astype(str) == y.astype(str)).to_numpy()
        if not ok.all():
            i = int(np.argmin(ok))
            raise AssertionError(
                f"{label} column {col!r} differs at row {i}: "
                f"pandas {x.iloc[i]!r} vs SQL {y.iloc[i]!r}"
            )


def same(a, b, label: str) -> None:
    if isinstance(a, pd.DataFrame | pd.Series) or isinstance(b, pd.DataFrame | pd.Series):
        assert_parity(a, b, label=label)
    elif isinstance(a, int | float | np.number) and isinstance(b, int | float | np.number):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), (label, a, b)
    else:
        assert str(a) == str(b), (label, a, b)


def test_parity_helper_ignores_row_order_and_bool_vs_int():
    a = pd.DataFrame({"k": ["b", "a"], "flag": [True, False], "v": [2.0, float("nan")]})
    b = pd.DataFrame({"v": [None, 2.0 + 1e-12], "k": ["a", "b"], "flag": [0, 1]})
    assert_parity(a, b)
    with pytest.raises(AssertionError, match="column 'v' differs"):
        assert_parity(a, a.assign(v=[1.0, 2.5]))


@pytest.mark.parametrize("day", days())
def test_pandas_and_sql_agree(day: int, lessons_db):
    pd_path = next(LESSONS.glob(f"unit*/day{day:02d}_pandas.py"))
    sql_path = next(LESSONS.glob(f"unit*/day{day:02d}_sql.py"))
    text = pd_path.read_text(encoding="utf-8") + sql_path.read_text(encoding="utf-8")
    if any(s in text for s in NEEDS_API_DB) and not (ROOT / "var" / "timeseries.sqlite").exists():
        pytest.skip("needs the API database: uv run bldgts model build && uv run bldgts bootstrap")
    a, b = run_script(pd_path), run_script(sql_path)
    shared = sorted(set(a) & set(b))
    assert shared, f"day {day}: the two scripts share no RESULTS keys ({sorted(a)} vs {sorted(b)})"
    for key in shared:
        same(a[key], b[key], f"day {day} {key}")


# ---------------------------------------------------------------- weeks 6-9: one script a day
# The answers a student should see, per day (only the keys listed are checked).
RDF_EXPECTED = {
    26: {
        "triple_count": 6,
        "predicate_counts": {"contains": 3, "contians": 1, "hasPoint": 2},
        "kitchen_contents": ["Fryer_1", "WalkInCooler"],
    },
    27: {
        "typed_things": 14,
        "unlabeled": ["IceMachine_1"],
        "blank_labels": ["WalkInCooler_1"],
    },
    28: {
        "specialty": [("fries", "en"), ("frites", "fr")],
        "hot_fryers": ["Fryer_2"],
        "text_setpoints": ["Fryer_2"],
    },
    29: {
        "equipment_with_temp": [
            ("Fryer_1", "Fryer_1_OilTemp"),
            ("Grill_1", "Grill_1_SurfaceTemp"),
            ("WalkInCooler_1", "Cooler_AirTemp"),
        ],
        "per_room": [("DiningRoom", 1), ("MainKitchen", 5)],
    },
    30: {
        "fryers_without_temp": ["Fryer_2"],
        "missing_labels": ["IceMachine_1"],
        "blank_labels": ["WalkInCooler_1"],
    },
    31: {
        "fryer_chain": ["Fryer", "CookingEquipment", "Equipment", "Thing"],
        "new_types": [("Mixer_1", "Equipment"), ("Mixer_1_Speed", "Point")],
        "exact": [],
        "with_path": [
            "Fryer_1",
            "Fryer_2",
            "Grill_1",
            "IceMachine_1",
            "SodaFountain_1",
            "WalkInCooler_1",
        ],
    },
    32: {
        "types": {
            "TransitiveProperty": ["contains", "partOf"],
            "SymmetricProperty": ["adjacentTo", "sharesFryerWith"],
            "FunctionalProperty": ["hasCalories", "serialNumber"],
        },
        "two_calories": [],
    },
    33: {
        "fryer_types": ["CookingEquipment", "Equipment", "Fryer", "Thing"],
        "errors": [],
        "mistake_errors": 1,
        "shacl_fryer_2": [
            "A fryer needs a temperature point.",
            "Oil setpoint must be one decimal number.",
        ],
    },
    34: {
        "items_on_fryer": [
            ("BarnCombo", "Fryer_1"),
            ("ChickenSandwich", "Fryer_1"),
            ("Fries", "Fryer_1"),
            ("OnionRings", "Fryer_2"),
        ],
        "off_menu_without_fryer_2": ["OnionRings"],
    },
    35: {
        "restaurant_ok": False,
        "restaurant_problems": [
            ("Fryer_2", "Violation", "A fryer needs a temperature point."),
            ("Fryer_2", "Violation", "Oil setpoint must be one decimal number."),
            ("Grill_1", "Violation", "Serial number must look like BB-ABC-1234."),
            ("IceMachine_1", "Warning", "Missing label."),
            ("WalkInCooler_1", "Warning", "Blank label."),
        ],
        "building_ok": False,
        "building_problems": [("VAV_2", "Violation", "A VAV needs a temperature point.")],
        "building_equipment_with_temp": [("AHU_1", "AHU_1_SAT"), ("VAV_1", "VAV_1_ZoneTemp")],
        "downstream_of_ahu_1": ["VAV_1", "VAV_2", "Zone_1", "Zone_2"],
    },
    36: {
        "questions": 5,
        "reuse": {
            "Equipment": "brick:Equipment",
            "Fryer": None,
            "Kitchen": None,
            "MenuItem": None,
            "TemperatureSensor": "brick:Temperature_Sensor",
            "cookedOn": None,
            "hasCalories": None,
            "hasIngredient": None,
            "hasLocation": "brick:hasLocation",
            "hasPoint": "brick:hasPoint",
            "oilSetpoint": None,
        },
    },
    37: {"missing_terms": [], "no_label": [], "no_definition": []},
    38: {
        "restrictions": [
            ("Fryer", "hasPoint", "some TemperatureSensor"),
            ("MenuItem", "hasCalories", "exactly 1"),
        ],
        "undefined_classes": [],
        "cook_methods": [
            ("CookMethod.fried", "fried", 0),
            ("CookMethod.grilled", "grilled", 1),
            ("CookMethod.none", "none", 2),
        ],
        "text_not_iri": ["Shake"],
        "coded_labels": ["15-Fried pickles"],
        "code_7_alone": ["Moo melt", "Spicy stack"],
        "receipts": {"Receipt_1": "Moo melt", "Receipt_2": "Spicy stack"},
    },
    39: {
        "unanswered": [],
        "conforms": True,
        "shape_results": {
            "separate file": [
                (
                    "FriedPickles",
                    "Warning",
                    "Keep labels clean: start with a letter, no codes like '15-' in front.",
                ),
                (
                    "Shake",
                    "Violation",
                    "A menu item needs exactly one cook method, one of the CookMethod values.",
                ),
            ],
            "class is shape": [
                (
                    "CrispyChicken",
                    "Violation",
                    "A fried menu item has exactly one cook method: CookMethod.fried.",
                ),
            ],
        },
    },
    40: {
        "answers": {
            "brick:Equipment": {
                "no_reasoner": [
                    "AHU_1",
                    "Cooler_1",
                    "Fryer_1",
                    "Fryer_2",
                    "Grill_1",
                    "VAV_1",
                    "VAV_2",
                ],
                "reasoner": [
                    "AHU_1",
                    "Cooler_1",
                    "Fryer_1",
                    "Fryer_2",
                    "Grill_1",
                    "VAV_1",
                    "VAV_2",
                ],
            },
            "brick:Temperature_Sensor": {
                "no_reasoner": ["AHU_1_SAT", "VAV_1_ZoneTemp"],
                "reasoner": [
                    "AHU_1_SAT",
                    "Fryer_1_OilTemp",
                    "Fryer_2_OilTemp",
                    "Grill_1_SurfaceTemp",
                    "VAV_1_ZoneTemp",
                ],
            },
            "brick:hasPoint": {
                "no_reasoner": ["AHU_1", "Fryer_1", "Fryer_2", "Grill_1", "VAV_1", "VAV_2"],
                "reasoner": ["AHU_1", "Fryer_1", "Fryer_2", "Grill_1", "VAV_1", "VAV_2"],
            },
            "brick:Building": {"no_reasoner": ["Building_1"], "reasoner": ["Building_1"]},
        },
    },
    41: {
        "anatomy": {
            "scheme": "https",
            "host": "example.org",
            "path": "/burger",
            "local name": "Fryer",
        },
    },
    42: {
        "redirects": {
            "a browser": "https://example.github.io/burger/index.html",
            "rdflib or a triple store": "https://example.github.io/burger/burger.ttl",
            "a JSON-LD tool": "https://example.github.io/burger/burger.jsonld",
            "curl with no header": "https://example.github.io/burger/index.html",
        },
        "fryer_triples": 9,
    },
    43: {
        "version": "1.1.0",
        "version_ok": True,
        "deprecated": {"Cooler": "WalkInCooler"},
        "after": [],
        "coolers": ["Cooler_A", "Cooler_B"],
    },
    44: {
        "report": {
            "standard": ["type", "label", "Temperature_Sensor"],
            "custom": [
                "Fryer",
                "Grill",
                "Kitchen",
                "TemperatureSensor",
                "hasLocation",
                "hasPoint",
                "oilSetpoint",
            ],
            "deprecated": ["Cooler"],
            "unknown": ["https://example.org/burger#Fryr", "https://example.org/burger#hasPiont"],
        },
        "violations": [("Fryer_1", "A fryer needs a temperature point.")],
        "ci_passes": False,
    },
    45: {"version": "1.1.0", "ready": True},
}


def rdf_days() -> list[int]:
    return sorted(int(p.stem[3:5]) for p in LESSONS.glob("unit*/day*_rdf.py"))


def test_every_rdf_day_is_checked():
    assert rdf_days() == list(range(26, 46))


@pytest.mark.parametrize("ttl", sorted(LESSONS.glob("unit*/*.ttl")), ids=lambda p: p.name)
def test_hand_written_turtle_parses(ttl: Path):
    assert len(Graph().parse(ttl)) > 0


@pytest.mark.parametrize("day", rdf_days())
def test_rdf_day_answers(day: int, repo_root):
    results = run_script(next(LESSONS.glob(f"unit*/day{day:02d}_rdf.py")))
    for key, expected in RDF_EXPECTED.get(day, {}).items():
        assert results[key] == expected, (day, key, results[key])


def test_inference_matches_the_property_paths(repo_root):
    """Day 32: for every question, owlrl's answer equals the no-reasoner property path's."""
    results = run_script(next(LESSONS.glob("unit*/day32_rdf.py")))
    assert results["triples_after"] > results["triples_before"]
    assert len(results["answers"]) == 6
    for name, result in results["answers"].items():
        assert result["after"] == result["path"], name
        assert result["after"], name


# ---------------------------------------------------------------- weeks 6-7: mini challenges
# Each day's lesson ends with a burger mini challenge. These are the answers given in the
# lesson's "Try it" section, checked against the same hand-written files.
RDF_DIR = LESSONS / "unit4-rdf-by-hand"
BB = Namespace("https://example.org/burger-barn#")
DATA = ["burger_barn.ttl"]
WITH_ONTOLOGY = ["burger_barn.ttl", "burger_barn_ontology.ttl"]
WITH_MENU = [*WITH_ONTOLOGY, "burger_barn_menu.ttl"]

# day: (files to load, the answer's SPARQL query, expected rows as short names)
MINI_CHALLENGE_QUERIES = {
    27: (
        DATA,
        "SELECT ?sensor WHERE { ?sensor a bb:TemperatureSensor }",
        [("Cooler_AirTemp",), ("Fryer_1_OilTemp",), ("Grill_1_SurfaceTemp",)],
    ),
    29: (
        DATA,
        "SELECT ?point ?unit WHERE { ?point a bb:TemperatureSensor ; bb:unit ?unit }",
        [("Cooler_AirTemp", "degC"), ("Fryer_1_OilTemp", "degC"), ("Grill_1_SurfaceTemp", "degC")],
    ),
    30: (
        DATA,
        "SELECT ?point WHERE { ?equipment bb:hasPoint|bb:hasAlarm ?point . "
        "FILTER NOT EXISTS { ?point bb:unit ?unit } }",
        [("Cooler_DoorAlarm",)],
    ),
    32: (
        WITH_ONTOLOGY,
        "SELECT ?part WHERE { ?part bb:partOf+ bb:NorthRegion }",
        [("BurgerBarn",), ("DiningRoom",), ("MainKitchen",)],
    ),
    34: (
        WITH_MENU,
        "SELECT (SUM(?calories) AS ?total) WHERE { "
        "bb:BarnCombo bb:includes ?item . ?item bb:hasCalories ?calories }",
        [("1010",)],
    ),
}


def _load(files: list[str]) -> Graph:
    g = Graph()
    for name in files:
        g.parse(RDF_DIR / name)
    return g


def _short(term) -> str:
    return term.fragment if hasattr(term, "fragment") else str(term)


@pytest.mark.parametrize("day", sorted(MINI_CHALLENGE_QUERIES))
def test_mini_challenge_queries(day: int):
    files, query, expected = MINI_CHALLENGE_QUERIES[day]
    rows = sorted(tuple(_short(term) for term in row) for row in _load(files).query(query))
    assert rows == expected


def test_mini_challenge_day26_fix_the_typo():
    fixed = (RDF_DIR / "day26_first_triples.ttl").read_text().replace("contians", "contains")
    g = Graph().parse(data=fixed, format="turtle")
    assert len(list(g.objects(BB.Kitchen, BB.contains))) == 3


def test_mini_challenge_day28_fry_time_in_seconds():
    fry_time = _load(DATA).value(BB.Fryer_1, BB.fryTime)
    assert fry_time.toPython().total_seconds() == 180


def test_mini_challenge_day31_untyped_shake():
    import owlrl
    from rdflib import Literal

    g = _load(WITH_ONTOLOGY)
    g.add((BB.Shake_1, BB.hasCalories, Literal(600)))
    owlrl.DeductiveClosure(owlrl.RDFS_Semantics).expand(g)
    rows = g.query(
        "SELECT ?type WHERE { bb:Shake_1 a ?type . FILTER(STRSTARTS(STR(?type), STR(bb:))) }"
    )
    assert [_short(row.type) for row in rows] == ["MenuItem"]


def test_mini_challenge_day33_disjoint_without_a_reasoner():
    from rdflib import RDF

    g = _load(WITH_ONTOLOGY)
    assert len(g.query(DISJOINT_QUERY)) == 0
    g.add((BB.IceMachine_1, RDF.type, BB.Grill))
    rows = [tuple(_short(term) for term in row) for row in g.query(DISJOINT_QUERY)]
    assert rows == [("IceMachine_1", "CookingEquipment", "Refrigeration")]


DISJOINT_QUERY = """
SELECT ?thing ?class1 ?class2 WHERE {
  ?class1 owl:disjointWith ?class2 .
  ?thing a/rdfs:subClassOf* ?class1 .
  ?thing a/rdfs:subClassOf* ?class2 .
}
"""


def test_mini_challenge_day35_serial_number_rule():
    from pyshacl import validate

    rule = """
    @prefix bb: <https://example.org/burger-barn#> .
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    bb:SerialShape a sh:NodeShape ;
        sh:targetClass bb:Fryer ;
        sh:property [ sh:path bb:serialNumber ; sh:minCount 1 ;
                      sh:message "A fryer needs a serial number." ] .
    """
    conforms, report, _text = validate(
        _load(WITH_ONTOLOGY), shacl_graph=Graph().parse(data=rule, format="turtle")
    )
    focus = report.query("SELECT ?node WHERE { ?r <http://www.w3.org/ns/shacl#focusNode> ?node }")
    assert conforms is False
    assert [_short(row.node) for row in focus] == ["Fryer_2"]


# ---------------------------------------------------------------- weeks 8-9: mini challenges
BURGER = Namespace("https://example.org/burger#")
BURGER_SITE = ["burger.ttl", "burger_site.ttl"]

MINI_CHALLENGE_QUERIES.update(
    {
        36: (
            BURGER_SITE,
            "SELECT ?fryer WHERE { site:OnionRings burger:cookedOn ?fryer }",
            [("Fryer_2",)],
        ),
        38: (
            BURGER_SITE,
            "SELECT ?item WHERE { site:Restaurant_1 burger:servesItem ?item . "
            "?item a burger:MenuItem }",
            [("ClassicBurger",), ("Cola",), ("Fries",), ("OnionRings",)],
        ),
        41: (
            ["burger.ttl"],
            "SELECT (COUNT(DISTINCT ?term) AS ?n) WHERE { "
            "{ ?term ?p ?o } UNION { ?s ?term ?o } UNION { ?s ?p ?term } "
            "FILTER(isIRI(?term) && STRSTARTS(STR(?term), STR(burger:))) }",
            [("21",)],
        ),
    }
)


def test_mini_challenge_day37_add_ice_machine():
    from rdflib import OWL, RDF, RDFS, SKOS

    g = _load(["burger.ttl"])
    g.parse(
        data="""
        @prefix burger: <https://example.org/burger#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
        burger:IceMachine a owl:Class ; rdfs:subClassOf burger:Equipment ;
            rdfs:label "Ice machine" ; skos:definition "A machine that makes ice." .
        """,
        format="turtle",
    )
    classes = set(g.subjects(RDF.type, OWL.Class))
    assert len(classes) == 14
    assert all(g.value(c, RDFS.label) and g.value(c, SKOS.definition) for c in classes)


COOK_FILES = ["burger.ttl", "burger_cook_methods.ttl", "burger_cook_data.ttl"]
COOK_METHOD_RULE = """
@prefix burger: <https://example.org/burger#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
burger:MenuItemCookShape a sh:NodeShape ; sh:targetClass burger:MenuItem ;
    sh:property [ sh:path burger:cookMethod ;
        sh:in ( burger:CookMethod.fried burger:CookMethod.grilled burger:CookMethod.none ) ;
        sh:minCount 1 ; sh:maxCount 1 ] .
"""


def test_mini_challenge_day38_cook_method_as_text_fails():
    from pyshacl import validate

    rule = Graph().parse(data=COOK_METHOD_RULE, format="turtle")
    clean = _load(COOK_FILES)
    assert validate(clean, shacl_graph=rule)[0] is True

    with_mistakes = _load([*COOK_FILES, "burger_cook_mistakes.ttl"])
    conforms, report, _text = validate(with_mistakes, shacl_graph=rule)
    rows = report.query("SELECT ?n WHERE { ?r <http://www.w3.org/ns/shacl#focusNode> ?n }")
    assert conforms is False
    assert [_short(row.n) for row in rows] == ["Shake"]


def test_day38_named_cook_method_fixes_the_shake():
    from pyshacl import validate
    from rdflib import Literal, URIRef

    g = _load([*COOK_FILES, "burger_cook_mistakes.ttl"])
    shake = URIRef("https://example.org/burger-site#Shake")
    g.remove((shake, BURGER.cookMethod, Literal("fried")))
    g.add((shake, BURGER.cookMethod, URIRef(str(BURGER) + "CookMethod.fried")))
    rule = Graph().parse(data=COOK_METHOD_RULE, format="turtle")
    assert validate(g, shacl_graph=rule)[0] is True


def test_day39_a_shape_that_is_not_a_class_has_no_target():
    from pyshacl import validate
    from rdflib import OWL, RDF, RDFS

    data = _load([*COOK_FILES, "burger_cook_mistakes.ttl"])
    shapes = _load(["burger_cook_methods.ttl"])
    assert validate(data, shacl_graph=shapes)[0] is False  # CrispyChicken is "grilled"
    shapes.remove((BURGER.FriedMenuItem, RDF.type, OWL.Class))
    shapes.remove((BURGER.FriedMenuItem, RDF.type, RDFS.Class))
    assert validate(data, shacl_graph=shapes)[0] is True


def test_mini_challenge_day39_cooler_shape():
    from pyshacl import validate

    rule = """
    @prefix burger: <https://example.org/burger#> .
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    burger:CoolerShape a sh:NodeShape ; sh:targetClass burger:WalkInCooler ;
        sh:property [ sh:path burger:hasPoint ; sh:minCount 1 ] .
    """
    conforms, report, _text = validate(
        _load(BURGER_SITE), shacl_graph=Graph().parse(data=rule, format="turtle")
    )
    rows = report.query("SELECT ?n WHERE { ?r <http://www.w3.org/ns/shacl#focusNode> ?n }")
    assert conforms is False
    assert [_short(row.n) for row in rows] == ["Cooler_1"]


def test_mini_challenge_day40_without_equivalent_class():
    import owlrl
    from rdflib import OWL

    g = _load(["tiny_building.ttl", *BURGER_SITE, "burger_alignment.ttl"])
    g.remove((None, OWL.equivalentClass, None))
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
    rows = g.query("SELECT DISTINCT ?x WHERE { ?x a brick:Temperature_Sensor }")
    assert sorted(_short(row.x) for row in rows) == ["AHU_1_SAT", "VAV_1_ZoneTemp"]


def test_mini_challenge_day42_first_matching_rule_wins():
    rules = [("text/turtle", "burger.ttl"), ("application/ld+json", "burger.jsonld")]
    accept = "application/ld+json, text/turtle;q=0.5"
    chosen = next(target for pattern, target in rules if pattern in accept)
    assert chosen == "burger.ttl"


def test_mini_challenge_day43_bump_to_1_2_0():
    from rdflib import OWL, URIRef

    text = (RDF_DIR / "burger.ttl").read_text()
    text = text.replace("burger/1.0.0", "burger/OLD").replace("1.1.0", "1.2.0")
    text = text.replace("burger/OLD", "burger/1.1.0")
    g = Graph().parse(data=text, format="turtle")
    ontology = URIRef("https://example.org/burger")
    assert str(g.value(ontology, OWL.versionInfo)) == "1.2.0"
    assert str(g.value(ontology, OWL.versionIRI)).endswith("/1.2.0")
    assert str(g.value(ontology, OWL.priorVersion)).endswith("/1.1.0")


def test_mini_challenge_day44_fixing_typos_exposes_fryer_2():
    from pyshacl import validate

    text = (RDF_DIR / "burger_ci_data.ttl").read_text()
    text = text.replace("hasPiont", "hasPoint").replace("burger:Fryr", "burger:Fryer")
    text = text.replace("burger:Cooler ;", "burger:WalkInCooler ;")
    data = Graph().parse(data=text, format="turtle") + _load(["burger.ttl"])
    shapes = _load(["burger_shapes.ttl"])
    conforms, report, _text = validate(data, shacl_graph=shapes)
    rows = report.query("SELECT DISTINCT ?n WHERE { ?r <http://www.w3.org/ns/shacl#focusNode> ?n }")
    assert conforms is False
    assert sorted(_short(row.n) for row in rows) == ["Fryer_2"]


def test_mini_challenge_day45_missing_definition_fails_the_checklist():
    from rdflib import RDF, SKOS

    g = _load(["burger.ttl"])
    ours = {t for t in g.subjects(RDF.type, None) if str(t).startswith(str(BURGER))}
    assert all(g.value(t, SKOS.definition) for t in ours)
    g.remove((BURGER.Grill, SKOS.definition, None))
    assert [t.fragment for t in ours if not g.value(t, SKOS.definition)] == ["Grill"]
