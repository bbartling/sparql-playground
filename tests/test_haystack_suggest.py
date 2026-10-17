from bldgts.haystack.defs import catalog_for_level, load_defs_index
from bldgts.haystack.suggest import guess_marker_bundle, suggest_markers


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
    assert "sensor" in markers  # default function when quantity matches
