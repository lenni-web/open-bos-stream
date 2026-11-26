from __future__ import annotations

from pathlib import Path

from open_bos_stream.core.models import MapConfig
from open_bos_stream.map.service import MapService
from open_bos_stream.map.water_layers import (
    UNKNOWN_TANK_LABEL,
    normalize_feature,
)


ROOT = Path(__file__).resolve().parents[1]


def feature(tags: dict, geometry: dict | None = None, **properties) -> dict:
    return {
        "type": "Feature",
        "properties": {"category": "other", "all_tags": tags, **properties},
        "geometry": geometry or {"type": "Point", "coordinates": [9.0, 53.0]},
    }


def test_tanks_with_other_contents_are_removed() -> None:
    for content in ("slurry", "gas", "sewage", "silage", "fuel", "manure"):
        tank = feature({"man_made": "storage_tank", "content": content})
        assert normalize_feature(tank) is None


def test_unknown_tanks_stay_but_are_marked() -> None:
    tank = normalize_feature(feature({"man_made": "storage_tank"}))
    assert tank["properties"]["type_de"] == UNKNOWN_TANK_LABEL
    water = normalize_feature(
        feature({"man_made": "storage_tank", "content": "water"})
    )
    assert water["properties"]["type_de"] == "Wasserbehälter"


def test_other_categories_keep_their_label() -> None:
    tank = normalize_feature(
        feature(
            {"man_made": "storage_tank"},
            category="tank",
            type_de="Löschwasserbehälter",
        )
    )
    assert tank["properties"]["type_de"] == "Löschwasserbehälter"


def test_outlines_become_one_center_point() -> None:
    ring = [[9.0, 53.0], [9.2, 53.0], [9.2, 53.2], [9.0, 53.2], [9.0, 53.0]]
    for geometry in (
        {"type": "LineString", "coordinates": ring},
        {"type": "Polygon", "coordinates": [ring]},
    ):
        result = normalize_feature(
            feature({"emergency": "water_tank"}, geometry)
        )
        assert result["geometry"] == {
            "type": "Point",
            "coordinates": [9.1, 53.1],
        }
        assert (result["properties"]["lon"], result["properties"]["lat"]) == (
            9.1,
            53.1,
        )


def test_delivered_layers_contain_only_points_and_no_slurry() -> None:
    service = MapService(MapConfig())
    for name in service.layers():
        for item in service.layer(name)["features"]:
            assert item["geometry"]["type"] == "Point", name
            assert item["properties"]["all_tags"].get("content") in (
                None,
                "water",
            ), name


def test_water_layers_share_zoom_and_empty_layers_are_hidden() -> None:
    overlays = (
        ROOT / "src" / "open_bos_stream" / "static" / "js" / "map-overlays.js"
    ).read_text(encoding="utf-8")
    zooms = [
        line.strip()
        for line in overlays.splitlines()
        if line.strip().startswith("minzoom:")
    ]
    assert zooms == ["minzoom: 14,"] + ["minzoom: 13,"] * 5
    assert "if (!data.features?.length)" in overlays
