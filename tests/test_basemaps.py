from __future__ import annotations

import gzip
import io
from pathlib import Path

import pytest

from open_bos_stream.map.basemaps import (
    BasemapNotFoundError,
    BasemapService,
    BasemapUnavailableError,
    rewrite_style,
)


ROOT = Path(__file__).resolve().parents[1] / "src" / "open_bos_stream"

UPSTREAM_STYLE = {
    "version": 8,
    "glyphs": "https://sgx.geodatenzentrum.de/gdz_basemapde_vektor/fonts/v2/{fontstack}/{range}.pbf",
    "sprite": "https://sgx.geodatenzentrum.de/gdz_basemapde_vektor/sprites/v2/bm_web_col_sprite",
    "sources": {
        "smarttiles_de": {
            "type": "vector",
            "url": "https://sgx.geodatenzentrum.de/gdz_basemapde_vektor/tiles/v2/bm_web_de_3857/bm_web_de_3857.json",
        }
    },
    "layers": [{"id": "Hintergrund", "type": "background"}],
}


def png(transparent: bool = False) -> bytes:
    from PIL import Image

    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0) if transparent else (40, 90, 40, 255))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def fake(responses: dict[str, object], calls: list[str]):
    def fetch(url: str):
        calls.append(url)
        for marker, response in responses.items():
            if marker in url:
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(url)

    return fetch


def test_style_is_rewritten_to_relative_server_paths() -> None:
    style = rewrite_style(UPSTREAM_STYLE)

    assert style["glyphs"] == "/api/map/basemap/fonts/{fontstack}/{range}.pbf"
    assert style["sprite"] == "/api/map/basemap/sprites/bm_web_col_sprite"
    source = style["sources"]["smarttiles_de"]
    assert "url" not in source
    assert source["tiles"] == ["/api/map/basemap/tiles/{z}/{x}/{y}.pbf"]
    assert source["maxzoom"] == 15
    assert "basemap.de / BKG" in source["attribution"]
    # Das Original bleibt unverändert (Zwischenspeicher).
    assert "url" in UPSTREAM_STYLE["sources"]["smarttiles_de"]


def test_tiles_are_gzipped_cached_and_missing_ones_empty() -> None:
    calls: list[str] = []
    service = BasemapService(
        fetch=fake(
            {
                "/12/2155/1312.pbf": (b"vector-tile", "application/octet-stream"),
                "/3/0/0.pbf": BasemapNotFoundError("404"),
            },
            calls,
        )
    )

    data = service.tile(12, 2155, 1312)
    assert gzip.decompress(data) == b"vector-tile"
    service.tile(12, 2155, 1312)
    assert len(calls) == 1
    assert service.tile(3, 0, 0) == b""
    with pytest.raises(ValueError):
        service.tile(16, 0, 0)


def test_fonts_and_sprites_are_validated() -> None:
    service = BasemapService(
        fetch=fake(
            {
                "fonts/v2/Roboto%20Regular/0-255.pbf": (b"glyphs", "application/x-protobuf"),
                "bm_web_col_sprite@2x.png": (b"png", "image/png"),
            },
            [],
        )
    )

    assert service.font("Roboto Regular", "0-255") == b"glyphs"
    assert service.sprite("bm_web_col_sprite@2x.png") == (b"png", "image/png")
    with pytest.raises(ValueError):
        service.font("../etc", "0-255")
    with pytest.raises(KeyError):
        service.sprite("../../passwd")


def test_aerial_tiles_become_webp_and_keep_transparency() -> None:
    service = BasemapService(
        fetch=fake(
            {
                "BBOX=1059729": (png(), "image/png"),
                "dop_wms": (png(transparent=True), "image/png"),
            },
            [],
        )
    )
    from PIL import Image

    data = service.aerial_tile(16, 34492, 21166)
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    outside = service.aerial_tile(12, 2200, 1300)
    with Image.open(io.BytesIO(outside)) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((5, 5))[3] == 0
    with pytest.raises(ValueError):
        service.aerial_tile(5, 0, 0)


def test_aerial_service_errors_are_reported() -> None:
    service = BasemapService(
        fetch=fake({"dop_wms": (b"<ServiceException/>", "text/xml")}, [])
    )
    with pytest.raises(BasemapUnavailableError):
        service.aerial_tile(16, 34492, 21166)


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from open_bos_stream.api import map as map_api
    from open_bos_stream.core.container import auth_service, config
    from open_bos_stream.main import app

    monkeypatch.setattr(
        auth_service,
        "verify_token",
        lambda token, *, purpose="session": (
            {"username": token, "role": token} if token == "guest" else None
        ),
    )
    monkeypatch.setattr(type(auth_service), "configured", property(lambda self: True))
    monkeypatch.setattr(
        map_api,
        "basemap_service",
        BasemapService(
            fetch=fake(
                {
                    "bm_web_col.json": (
                        __import__("json").dumps(UPSTREAM_STYLE).encode(),
                        "application/json",
                    ),
                    ".pbf": (b"tile", "application/octet-stream"),
                },
                [],
            )
        ),
    )
    monkeypatch.setattr(config.map, "online", True)
    test_client = TestClient(app)
    test_client.cookies.set(auth_service.COOKIE_NAME, "guest")
    return test_client, config


def test_online_routes_are_not_shadowed_by_offline_tiles(client) -> None:
    test_client, _ = client

    tile = test_client.get("/api/map/basemap/tiles/12/2155/1312.pbf")
    assert tile.status_code == 200
    assert tile.headers["content-encoding"] == "gzip"
    assert tile.content == b"tile"
    style = test_client.get("/api/map/basemap/style/col.json").json()
    assert style["sources"]["smarttiles_de"]["tiles"][0].startswith("/api/map/")


def test_basemaps_offer_online_options_unless_switched_off(client) -> None:
    test_client, config = client

    ids = [option["id"] for option in test_client.get("/api/map/basemaps").json()["options"]]
    assert ids[:2] == ["online", "aerial"]

    config.map.online = False
    body = test_client.get("/api/map/basemaps").json()
    assert "online" not in [option["id"] for option in body["options"]]
    assert test_client.get("/api/map/basemap/style/col.json").status_code == 404


# ----------------------------------------------------------------------
# MapLibre 6 und Oberfläche
# ----------------------------------------------------------------------


def test_maplibre_6_is_loaded_as_module() -> None:
    vendor = ROOT / "static" / "vendor" / "maplibre"
    assert "@license 3-Clause BSD" in (vendor / "maplibre-gl.mjs").read_text(
        encoding="utf-8"
    )[:400]
    assert "v6.19.0" in (vendor / "maplibre-gl.mjs").read_text(encoding="utf-8")[:400]
    assert (vendor / "maplibre-gl-worker.mjs").is_file()
    assert not (vendor / "maplibre-gl.js").exists()
    for template in ("index.html", "guest.html"):
        text = (ROOT / "templates" / template).read_text(encoding="utf-8")
        assert '<script type="module">' in text
        assert "maplibre-gl.mjs" in text
        assert "window.maplibregl = maplibregl" in text
        assert text.index("map-basemap.js") < text.index("/static/js/map.js")


def test_base_map_switch_keeps_own_layers() -> None:
    script = (ROOT / "static" / "js" / "map-basemap.js").read_text(encoding="utf-8")

    assert "transformStyle" in script
    assert "!previousIds.layers.has(layer.id)" in script
    assert 'id !== "offline" && baseMapOption(info, "offline")' in script
    assert "window.location.origin" in script
