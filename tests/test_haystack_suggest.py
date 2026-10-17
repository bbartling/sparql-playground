import pytest
from bldgts.haystack.defs import catalog_for_level, load_defs_index
from bldgts.haystack.suggest import guess_marker_bundle, suggest_markers

# Generic BAS / BMS point names → required Haystack markers that must appear.
# Keep these ontology-agnostic tutorial fixtures: common abbrevs humans type in Niagara/FinStack.
BAS_POINT_CASES: list[tuple[str, set[str]]] = [
    ("AHU RF-C", {"return", "fan", "cmd"}),
    ("AHU_1 Return Fan Command", {"return", "fan", "cmd"}),
    ("AHU SF-C", {"discharge", "fan", "cmd"}),
    ("Supply Fan Cmd", {"discharge", "fan", "cmd"}),
    ("Exhaust Fan Status", {"exhaust", "fan", "status"}),
    ("AHU_1 Discharge Air Temp", {"discharge", "air", "temp", "sensor"}),
    ("SA-T", {"discharge", "air", "temp"}),
    ("RAT", {"return", "air", "temp"}),
    ("OAT", {"outside", "air", "temp"}),
    ("MAT", {"mixed", "air", "temp"}),
    ("Zone Temp Setpoint", {"zone", "temp", "sp"}),
    ("ZAT-SP", {"zone", "air", "temp", "sp"}),
    ("Duct Static Pressure", {"duct", "pressure"}),
    ("SA Static SP", {"discharge", "air", "pressure", "sp"}),
    ("OA Damper Position", {"outside", "air", "damper", "position"}),
    ("CHW Valve Cmd", {"chilled", "water", "valve", "cmd"}),
    ("HW Valve", {"hot", "water", "valve"}),
    ("Fan Speed VFD", {"fan", "speed"}),
    ("SF-VFD", {"discharge", "fan", "speed"}),
    ("Zone CO2", {"zone", "co2"}),
    ("ZN-OCC", {"zone", "occupancy"}),
    ("RA Humidity", {"return", "air", "humidity"}),
]

BAS_EQUIP_CASES: list[tuple[str, set[str]]] = [
    ("AHU_1", {"ahu"}),
    ("Air Handler Unit 2", {"ahu"}),
    ("VAV-3-12", {"vav"}),
    ("Supply Fan", {"fan"}),
    ("Chilled Water Pump", {"pump"}),
]


def test_defs_index_loads_vendored_pack():
    index = load_defs_index()
    assert "site" in index
    assert "ahu" in index
    assert "sensor" in index
    assert len(index) > 100


def test_catalog_is_level_filtered():
    site = catalog_for_level("site")
    point = catalog_for_level("point")
    assert "site" in site
    assert "sensor" not in site
    assert "sensor" in point
    assert "site" not in point


def test_suggest_finds_sensorish_names():
    hits = suggest_markers("discharge air temp sensor", "point", n=8)
    symbols = [h["symbol"] for h in hits]
    assert hits
    assert any(s in symbols for s in ("sensor", "temp", "discharge", "air", "point"))


def test_suggest_equip_ahu():
    hits = suggest_markers("AHU_1 air handler", "equip", n=5)
    symbols = [h["symbol"] for h in hits]
    assert "ahu" in symbols or "equip" in symbols


def test_guess_bundle_one_shot_dat():
    bundle = guess_marker_bundle("AHU_1 Discharge Air Temp", "point")
    markers = set(bundle["markers"])
    assert "point" in markers
    assert "his" in markers
    assert "temp" in markers
    assert "air" in markers or "discharge" in markers
    assert "sensor" in markers


def test_guess_ahu_rf_c_return_fan_command():
    bundle = guess_marker_bundle("AHU RF-C", "point")
    markers = set(bundle["markers"])
    assert {"return", "fan", "cmd"} <= markers
    assert "point" in markers and "his" in markers


@pytest.mark.parametrize(("name", "required"), BAS_POINT_CASES)
def test_bas_point_names_guess_required_markers(name: str, required: set[str]):
    bundle = guess_marker_bundle(name, "point")
    markers = set(bundle["markers"])
    missing = required - markers
    assert not missing, (
        f"{name!r} missing {missing}; got {sorted(markers)}; tokens={bundle.get('tokens')}"
    )


@pytest.mark.parametrize(("name", "required"), BAS_EQUIP_CASES)
def test_bas_equip_names_guess_required_markers(name: str, required: set[str]):
    bundle = guess_marker_bundle(name, "equip")
    markers = set(bundle["markers"])
    missing = required - markers
    assert not missing, f"{name!r} missing {missing}; got {sorted(markers)}"
