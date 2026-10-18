import json

import pytest
from bldgts.haystack.defs import catalog_for_level, is_subtype, load_defs_index
from bldgts.haystack.suggest import guess_marker_bundle, suggest_markers

# Common BAS labels carry useful context, but they do not establish historian
# support, engineering units, timezone, or (for a bare quantity) point function.
BAS_POINT_CASES: list[tuple[str, set[str]]] = [
    ("AHU RF-C", {"return", "fan", "cmd"}),
    ("AHU_1 Return Fan Command", {"return", "fan", "cmd"}),
    ("AHU SF-C", {"discharge", "fan", "cmd"}),
    ("Supply Fan Cmd", {"discharge", "fan", "cmd"}),
    ("Exhaust Fan Status", {"exhaust", "fan", "run", "sensor"}),
    ("AHU_1 Discharge Air Temp", {"discharge", "air", "temp"}),
    ("SA-T", {"discharge", "air", "temp"}),
    ("RAT", {"return", "air", "temp"}),
    ("OAT", {"outside", "air", "temp"}),
    ("MAT", {"mixed", "air", "temp"}),
    ("Zone Temp Setpoint", {"zone", "temp", "sp"}),
    ("ZAT-SP", {"zone", "air", "temp", "sp"}),
    ("Duct Static Pressure", {"duct", "pressure"}),
    ("SA Static SP", {"discharge", "air", "pressure", "sp"}),
    ("OA Damper Position", {"outside", "air", "damper"}),
    ("CHW Valve Cmd", {"chilled", "water", "valve", "cmd"}),
    ("HW Valve", {"hot", "water", "valve"}),
    ("Fan Speed VFD", {"fan", "speed"}),
    ("SF-VFD", {"discharge", "fan", "speed"}),
    ("Zone CO2", {"zone", "co2"}),
    ("ZN-OCC", {"zone", "occupancy"}),
    ("RA Humidity", {"return", "air", "humidity"}),
    ("CHW Entering Water Temp Sensor", {"chilled", "water", "entering", "temp", "sensor"}),
    ("Computed Energy", {"synthetic", "computed", "energy"}),
    ("Machine Learning Temp", {"synthetic", "ml", "temp"}),
    ("Simulation Temp", {"synthetic", "sim", "temp"}),
    ("wetBulb Sensor", {"wetBulb", "sensor"}),
    ("Voltage Sensor", {"volt", "sensor"}),
]

BAS_EQUIP_CASES: list[tuple[str, set[str]]] = [
    ("AHU_1", {"equip", "ahu"}),
    ("Air Handler Unit 2", {"equip", "ahu"}),
    ("VAV-3-12", {"equip", "vav"}),
    ("Supply Fan", {"equip", "fan", "discharge"}),
    ("Chilled Water Pump", {"equip", "chilled", "water", "pump"}),
    ("Cooling Tower 2", {"equip", "coolingTower"}),
]


def test_defs_index_resolves_inherited_marker_kinds():
    index = load_defs_index()
    assert len(index) > 100
    for symbol in ("site", "ahu", "sensor", "temp", "water", "computed"):
        assert index[symbol]["kind"] == "marker"
    assert index["kind"]["kind"] == "str"
    assert index["siteRef"]["kind"] == "ref"
    assert is_subtype("computed", "pointFunction")
    assert is_subtype("computed", "synthetic")
    assert not is_subtype("sensor", "synthetic")


def test_catalog_is_level_filtered_and_uses_real_marker_definitions():
    index = load_defs_index()
    for level in ("site", "building", "floor", "equip", "part", "point"):
        catalog = catalog_for_level(level)
        assert all(name in index and index[name]["kind"] == "marker" for name in catalog)
        assert (
            not {
                "kind",
                "unit",
                "tz",
                "siteRef",
                "equipRef",
                "status",
                "coolTower",
                "voltage",
                "position",
            }
            & catalog.keys()
        )
        assert all("-" not in name and ":" not in name for name in catalog)
    assert "sensor" not in catalog_for_level("site")
    assert "site" not in catalog_for_level("point")
    assert "level" not in catalog_for_level("floor")
    assert "building" not in catalog_for_level("building")
    assert {"sensor", "synthetic", "computed", "cur", "writable"} <= catalog_for_level(
        "point"
    ).keys()
    assert "coolingTower" in catalog_for_level("equip")


def test_custom_pack_never_fabricates_missing_seed_symbols(tmp_path):
    path = tmp_path / "defs.json"
    path.write_text(
        json.dumps(
            {
                "rows": [
                    {"def": "marker"},
                    {"def": "point", "is": "marker"},
                    {"def": "sensor", "is": "marker"},
                    # A familiar symbol with a scalar kind is not a legal marker.
                    {"def": "temp", "is": "str"},
                    {"def": "str"},
                ]
            }
        )
    )
    index = load_defs_index(str(path))
    assert "his" not in index
    assert set(catalog_for_level("point", path=str(path))) == {"point", "sensor"}
    bundle = guess_marker_bundle("temp his sensor", path=str(path))
    assert set(bundle["markers"]) == {"point", "sensor"}


def test_cyclic_def_pack_fails_clearly(tmp_path):
    path = tmp_path / "cyclic.json"
    path.write_text(
        json.dumps(
            {
                "rows": [
                    {"def": "a", "is": "b"},
                    {"def": "b", "is": "a"},
                ]
            }
        )
    )
    with pytest.raises(ValueError, match="cyclic Haystack"):
        load_defs_index(str(path))


def test_suggest_finds_sensorish_names():
    hits = suggest_markers("discharge air temp sensor", "point", n=8)
    assert {"sensor", "temp", "discharge", "air"} <= {h["symbol"] for h in hits}
    assert suggest_markers("temp", "point", n=0) == []


def test_suggest_equip_ahu():
    hits = suggest_markers("AHU_1 air handler", "equip", n=5)
    assert "ahu" in {h["symbol"] for h in hits}


def test_bare_quantity_does_not_invent_sensor_history_or_scalar_values():
    bundle = guess_marker_bundle("AHU_1 Discharge Air Temp", "point")
    assert set(bundle["markers"]) == {"point", "temp", "air", "discharge"}
    assert bundle["by_role"]["function"] is None
    assert bundle["needs_review"]
    assert any("ambiguous" in warning for warning in bundle["warnings"])
    assert not {"kind", "unit", "tz", "hisMode"} & bundle.keys()


@pytest.mark.parametrize("name", ["space42", "SP123", "C01", "RF-C01", "unknown", ""])
def test_identifiers_do_not_imply_short_function_or_capability_markers(name):
    bundle = guess_marker_bundle(name)
    assert not {"sensor", "sp", "cmd", "his", "cur", "writable"} & set(bundle["markers"])


def test_explicit_capabilities_are_separate_from_function():
    bundle = guess_marker_bundle("Supply fan cmd historized cur writable")
    assert {"cmd", "his", "cur", "writable"} <= set(bundle["markers"])
    assert bundle["evidence"]["his"]["matches"] == ["historized"]
    assert "writable" not in guess_marker_bundle("Supply fan command")["markers"]
    assert "his" not in guess_marker_bundle("AHU RF-C")["markers"]


def test_ambiguous_air_abbreviations_do_not_invent_a_quantity():
    for name in ("SAS", "RAS", "SA-SP"):
        bundle = guess_marker_bundle(name)
        assert not {"temp", "pressure"} & set(bundle["markers"])
        assert any("abbreviations are ambiguous" in warning for warning in bundle["warnings"])


def test_position_is_context_and_voltage_uses_actual_standard_marker():
    position = guess_marker_bundle("OA Damper Position")
    assert "position" not in position["markers"]
    assert any("not a standard marker" in warning for warning in position["warnings"])
    assert "volt" in guess_marker_bundle("Voltage sensor")["markers"]


def test_conflicting_functions_require_review_instead_of_arbitrary_pick():
    bundle = guess_marker_bundle("Temp sensor command")
    assert not {"sensor", "sp", "cmd", "synthetic"} & set(bundle["markers"])
    assert any("Conflicting" in warning for warning in bundle["warnings"])


def test_synthetic_refinement_does_not_conflict_with_its_parent():
    bundle = guess_marker_bundle("Synthetic computed energy")
    assert {"synthetic", "computed"} <= set(bundle["markers"])
    assert not any("Conflicting" in warning for warning in bundle["warnings"])
    assert "sensor" not in bundle["markers"]


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        ("site", {"site"}),
        ("building", {"site"}),
        ("floor", {"space", "floor"}),
        ("part", {"equip"}),
    ],
)
def test_tree_levels_seed_only_supported_entity_tags(level, expected):
    assert set(guess_marker_bundle("Unknown", level)["markers"]) == expected


def test_unknown_level_is_rejected():
    with pytest.raises(ValueError, match="unknown level"):
        guess_marker_bundle("Temp", "nonsense")


@pytest.mark.parametrize(("name", "required"), BAS_POINT_CASES)
def test_bas_point_names_guess_required_markers(name: str, required: set[str]):
    bundle = guess_marker_bundle(name, "point")
    assert required <= set(bundle["markers"]), bundle
    assert set(bundle["evidence"]) == set(bundle["markers"])
    assert set(bundle["markers"]) <= catalog_for_level("point").keys()


@pytest.mark.parametrize(("name", "required"), BAS_EQUIP_CASES)
def test_bas_equip_names_guess_required_markers(name: str, required: set[str]):
    bundle = guess_marker_bundle(name, "equip")
    assert required <= set(bundle["markers"]), bundle
    assert set(bundle["markers"]) <= catalog_for_level("equip").keys()
