import asyncio

import pytest
from fastapi import HTTPException

from open_bos_stream.api import map as map_api
from open_bos_stream.map.dipul import (
    CACHE_SECONDS,
    LAYER_GROUPS,
    DipulService,
    DipulUnavailableError,
    parse_feature_info,
    tile_bbox,
)


FEATURE_INFO = """Results for FeatureType 'de.dfs.dipul:kontrollzonen':
--------------------------------------------
geom = [GEOMETRY (Polygon) with 261 points]
upper_limit_alt_ref = MSL
upper_limit_altitude = 2500.0
lower_limit_altitude = 381.233608
lower_limit_alt_ref = MSL
legal_ref = NfL 2026-1-3960
name = Hamburg (EDDH) Zone 4
upper_limit_unit = ft
generated_name_DE = Hamburg (EDDH) Zone 4
lower_limit_unit = ft
type_code = KONTROLLZONE
--------------------------------------------
Results for FeatureType 'de.dfs.dipul:industrieanlagen':
--------------------------------------------
geom = [GEOMETRY (Polygon) with 77 points]
legal_ref = § 21h, Abs. 3 (3.) LuftVO
name = Industrieanlage
generated_name_DE = Industrieanlage
lower_limit_altitude = 0.0
lower_limit_alt_ref = AGL
lower_limit_unit = M
type_code = U_NFZ
--------------------------------------------
"""


class RecordingFetch:
    def __init__(self, data: bytes = b"\x89PNG-tile") -> None:
        self.data = data
        self.calls: list[dict] = []

    def __call__(self, params: dict) -> bytes:
        self.calls.append(params)
        return self.data


def test_all_wms_layers_except_inactive_restrictions_are_grouped() -> None:
    layers = [layer for group in LAYER_GROUPS for layer in group.layers]

    assert len(layers) == 33
    assert len(set(layers)) == 33
    assert "inaktive_temporaere_betriebseinschraenkungen" not in layers
    assert all(group.visible for group in LAYER_GROUPS)


def test_tile_bbox_covers_web_mercator_world() -> None:
    min_x, min_y, max_x, max_y = tile_bbox(0, 0, 0)

    assert min_x == pytest.approx(-20037508.342789244)
    assert max_y == pytest.approx(20037508.342789244)
    assert max_x - min_x == pytest.approx(max_y - min_y)


def test_tiles_are_requested_unchanged_and_cached_for_an_hour() -> None:
    now = [1000.0]
    fetch = RecordingFetch()
    service = DipulService(fetch=fetch, clock=lambda: now[0])

    first = service.tile("luftraum", 10, 538, 328)
    second = service.tile("luftraum", 10, 538, 328)

    assert first == second == b"\x89PNG-tile"
    assert len(fetch.calls) == 1
    params = fetch.calls[0]
    assert params["REQUEST"] == "GetMap"
    assert params["CRS"] == "EPSG:3857"
    assert params["TRANSPARENT"] == "TRUE"
    assert params["LAYERS"].split(",") == list(LAYER_GROUPS[0].layers)
    assert CACHE_SECONDS == 3600

    now[0] += CACHE_SECONDS - 1
    service.tile("luftraum", 10, 538, 328)
    assert len(fetch.calls) == 1

    now[0] += 2
    service.tile("luftraum", 10, 538, 328)
    assert len(fetch.calls) == 2


def test_cache_is_bounded() -> None:
    fetch = RecordingFetch()
    service = DipulService(fetch=fetch, max_entries=2)

    for x in range(3):
        service.tile("luftraum", 10, x, 0)
    service.tile("luftraum", 10, 0, 0)

    assert len(fetch.calls) == 4


def test_invalid_tiles_and_groups_are_rejected() -> None:
    service = DipulService(fetch=RecordingFetch())

    with pytest.raises(KeyError):
        service.tile("beliebig", 10, 0, 0)
    with pytest.raises(ValueError):
        service.tile("luftraum", 3, 0, 0)
    with pytest.raises(ValueError):
        service.tile("luftraum", 10, 1024, 0)


def test_feature_info_queries_only_visible_groups() -> None:
    fetch = RecordingFetch(FEATURE_INFO.encode())
    service = DipulService(fetch=fetch)

    zones = service.feature_info(9.67, 53.47, 12, ["luftraum", "fremd"])

    params = fetch.calls[0]
    assert params["REQUEST"] == "GetFeatureInfo"
    assert params["QUERY_LAYERS"] == params["LAYERS"]
    assert params["LAYERS"].split(",") == list(LAYER_GROUPS[0].layers)
    lat_min, lng_min, lat_max, lng_max = map(
        float,
        params["BBOX"].split(","),
    )
    assert lat_min < 53.47 < lat_max
    assert lng_min < 9.67 < lng_max
    assert zones[0]["name"] == "Hamburg (EDDH) Zone 4"
    assert service.feature_info(9.67, 53.47, 12, []) == []


def test_feature_info_is_translated_into_readable_zones() -> None:
    zones = parse_feature_info(FEATURE_INFO)

    assert zones == [
        {
            "layer": "kontrollzonen",
            "name": "Hamburg (EDDH) Zone 4",
            "type": "Kontrollzone",
            "lower_limit": "381 ft MSL",
            "upper_limit": "2500 ft MSL",
            "legal_ref": "NfL 2026-1-3960",
        },
        {
            "layer": "industrieanlagen",
            "name": "Industrieanlage",
            "type": "Industrieanlage",
            "lower_limit": "0 m AGL",
            "upper_limit": None,
            "legal_ref": "§ 21h, Abs. 3 (3.) LuftVO",
        },
    ]
    assert parse_feature_info("no features were found") == []


def test_unavailable_dipul_returns_503(monkeypatch) -> None:
    def unavailable(*_args):
        raise DipulUnavailableError("offline")

    monkeypatch.setattr(map_api.dipul_service, "tile", unavailable)

    with pytest.raises(HTTPException) as error:
        asyncio.run(map_api.dipul_tile("luftraum", 10, 0, 0))

    assert error.value.status_code == 503


def test_dipul_layers_endpoint_includes_attribution() -> None:
    result = map_api.dipul_layers()

    assert "CC BY-ND 4.0" in result["attribution"]
    assert result["map_tool_url"].startswith("https://")
    assert [group["id"] for group in result["groups"]][:2] == [
        "luftraum",
        "temporaer",
    ]
