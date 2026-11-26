from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from open_bos_stream.core.container import config as runtime_config
from open_bos_stream.map import MapService
from open_bos_stream.map.service import DEFAULT_CENTER
from open_bos_stream.map.dipul import (
    ATTRIBUTION as DIPUL_ATTRIBUTION,
    LICENSE_URL as DIPUL_LICENSE_URL,
    MAP_TOOL_URL as DIPUL_MAP_TOOL_URL,
    DipulService,
    DipulUnavailableError,
)
from open_bos_stream.map.mbtiles import MBTilesError
from open_bos_stream.map.basemaps import (
    AERIAL_BOUNDS,
    AERIAL_MAX_ZOOM,
    AERIAL_MIN_ZOOM,
    BASEMAP_ATTRIBUTION,
    BasemapService,
    BasemapUnavailableError,
    aerial_attribution,
)
from open_bos_stream.auth.roles import GUEST

router = APIRouter(
    dependencies=[GUEST],
    prefix="/api/map",
    tags=["map"],
)

dipul_service = DipulService()
basemap_service = BasemapService()

ONLINE_CACHE_HEADERS = {"Cache-Control": "public, max-age=86400"}


def _service() -> MapService:
    # Laufzeitkonfiguration statt bei jeder Kachelanfrage die YAML-Datei
    # neu zu lesen; gespeicherte Änderungen übernimmt ConfigApplyService.
    return MapService(
        runtime_config.map,
    )

def _default_map(service: MapService) -> tuple[str, object]:
    default = service.default_map()

    if default is None:
        raise HTTPException(
            status_code=404,
            detail="No default map configured.",
        )

    try:
        metadata = service.metadata(default)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Default map not found.",
        ) from exc
    except MBTilesError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return default, metadata

@router.get("/maps")
def list_maps() -> dict:
    service = _service()

    return {
        "maps": service.list_maps(),
        "default": service.default_map(),
        "path": str(service.map_directory),
    }


@router.get("/config")
def map_config() -> dict:
    service = _service()
    default, metadata = _default_map(service)

    data = asdict(metadata)

    data["center"] = DEFAULT_CENTER

    return {
        "map": default,
        "metadata": data,
    }

@router.get("/styles")
def map_styles() -> list[str]:
    return _service().styles()

@router.get("/style")
def map_style(
    request: Request,
    style: str = "basic",
) -> dict:
    service = _service()

    default = service.default_map()

    if default is None:
        raise HTTPException(
            status_code=404,
            detail="No default map configured.",
        )

    if style not in service.styles():
        raise HTTPException(
            status_code=404,
            detail=f"Map style not found: {style}",
        )

    # Keep the URL absolute. Some mobile MapLibre versions do not
    # request vector tiles when a style object contains a relative
    # tile template. url_for() uses the Host header of the current
    # browser request, so remote clients receive the Pi address while
    # local clients receive 127.0.0.1.
    tile_url = str(
        request.url_for(
            "map_tile",
            name=default,
            z="{z}",
            x="{x}",
            y="{y}",
        )
    )

    try:
        return service.style(
            tile_url=tile_url,
            name=default,
            style_name=style,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Map style not found: {style}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except MBTilesError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

@router.get(
    "/glyphs/{fontstack}/{glyph_range}.pbf",
    name="map_glyph",
)
def map_glyph(
    fontstack: str,
    glyph_range: str,
) -> Response:
    service = _service()

    try:
        data = service.glyph(
            fontstack=fontstack,
            glyph_range=f"{glyph_range}.pbf",
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Glyph not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return Response(
        content=data,
        media_type="application/x-protobuf",
        headers={
            "Cache-Control": "public, max-age=86400",
        },
    )

@router.get("/{name}/config")
def map_metadata(
    name: str,
) -> dict:
    service = _service()

    try:
        metadata = service.metadata(name)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Map not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except MBTilesError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return asdict(metadata)


@router.get(
    "/{name}/tiles/{z}/{x}/{y}",
    name="map_tile",
)
def map_tile(
    name: str,
    z: int,
    x: int,
    y: int,
) -> Response:

    if z < 0 or x < 0 or y < 0:
        raise HTTPException(
            status_code=400,
            detail="Tile coordinates must not be negative.",
        )

    service = _service()

    try:
        tile = service.tile(
            name,
            z,
            x,
            y,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Map not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except MBTilesError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    if tile is None:
        raise HTTPException(
            status_code=404,
            detail="Tile not found.",
        )

    headers = {
        "Cache-Control": "public, max-age=86400",
    }

    if tile.data.startswith(b"\x1f\x8b"):
        headers["Content-Encoding"] = "gzip"

    return Response(
        content=tile.data,
        media_type=tile.media_type,
        headers=headers,
    )

@router.get("/layers")
def map_layers() -> list[str]:
    return _service().layers()

@router.get("/layers/{name}")
def map_layer(name: str) -> dict:
    service = _service()

    if name not in service.layers():
        raise HTTPException(
            status_code=404,
            detail=f"Map layer not found: {name}",
        )

    try:
        return service.layer(name)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# Drohnen-Geozonen (dipul)
# ---------------------------------------------------------

@router.get("/dipul/layers")
def dipul_layers() -> dict:
    return {
        "groups": dipul_service.groups(),
        "attribution": DIPUL_ATTRIBUTION,
        "license_url": DIPUL_LICENSE_URL,
        "map_tool_url": DIPUL_MAP_TOOL_URL,
    }


@router.get("/dipul/tiles/{group}/{z}/{x}/{y}.png")
async def dipul_tile(group: str, z: int, x: int, y: int) -> Response:
    try:
        data = await run_in_threadpool(dipul_service.tile, group, z, x, y)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Unbekannte Geozonen-Gruppe.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DipulUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/dipul/info")
async def dipul_info(
    lng: float,
    lat: float,
    zoom: float = 12,
    groups: str = Query(default=""),
) -> dict:
    group_ids = [item for item in groups.split(",") if item]
    try:
        zones = await run_in_threadpool(
            dipul_service.feature_info,
            lng,
            lat,
            zoom,
            group_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DipulUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"zones": zones}


# ---------------------------------------------------------
# Grundkarten: online (basemap.de, Luftbild) und offline (MBTiles)
#
# Eigener Router, der vor `router` eingebunden wird: Die allgemeine Route
# /{name}/tiles/... der Offline-Karten würde /basemap/tiles/... sonst
# abfangen.
# ---------------------------------------------------------

online_router = APIRouter(
    dependencies=[GUEST],
    prefix="/api/map",
    tags=["map"],
)

@online_router.get("/basemaps")
def basemaps() -> dict:
    """Verfügbare Grundkarten und die Voreinstellung des Servers."""

    settings = runtime_config.map
    service = _service()
    options = []
    if settings.online:
        options.append(
            {
                "id": "online",
                "label": "Karte (basemap.de)",
                "attribution": BASEMAP_ATTRIBUTION,
            }
        )
        options.append(
            {
                "id": "aerial",
                "label": "Luftbild (Niedersachsen)",
                "attribution": aerial_attribution(),
                "min_zoom": AERIAL_MIN_ZOOM,
                "max_zoom": AERIAL_MAX_ZOOM,
                "bounds": AERIAL_BOUNDS,
            }
        )
    default_map = service.default_map()
    if default_map is not None:
        try:
            metadata = service.metadata(default_map)
        except (FileNotFoundError, MBTilesError):
            metadata = None
        if metadata is not None:
            options.append(
                {
                    "id": "offline",
                    "label": "Offline-Karte",
                    "min_zoom": metadata.min_zoom,
                    "max_zoom": metadata.max_zoom,
                }
            )
    ids = [option["id"] for option in options]
    default = settings.base_map if settings.base_map in ids else (
        ids[0] if ids else None
    )
    return {
        "options": options,
        "default": default,
        "center": DEFAULT_CENTER,
        "offline_path": str(service.map_directory),
    }


def _require_online() -> None:
    if not runtime_config.map.online:
        raise HTTPException(
            status_code=404,
            detail="Online-Karten sind ausgeschaltet.",
        )


@online_router.get("/basemap/style/{variant}.json")
async def basemap_style(variant: str) -> dict:
    _require_online()
    try:
        return await run_in_threadpool(basemap_service.style, variant)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unbekannter Kartenstil.") from exc
    except BasemapUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@online_router.get("/basemap/tiles/{z}/{x}/{y}.pbf")
async def basemap_tile(z: int, x: int, y: int) -> Response:
    _require_online()
    try:
        data = await run_in_threadpool(basemap_service.tile, z, x, y)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BasemapUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not data:
        return Response(status_code=204, headers=ONLINE_CACHE_HEADERS)
    return Response(
        content=data,
        media_type="application/x-protobuf",
        headers={**ONLINE_CACHE_HEADERS, "Content-Encoding": "gzip"},
    )


@online_router.get("/basemap/fonts/{fontstack}/{glyph_range}.pbf")
async def basemap_font(fontstack: str, glyph_range: str) -> Response:
    _require_online()
    try:
        data = await run_in_threadpool(
            basemap_service.font,
            fontstack,
            glyph_range,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BasemapUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=data,
        media_type="application/x-protobuf",
        headers=ONLINE_CACHE_HEADERS,
    )


@online_router.get("/basemap/sprites/{filename}")
async def basemap_sprite(filename: str) -> Response:
    _require_online()
    try:
        data, media_type = await run_in_threadpool(
            basemap_service.sprite,
            filename,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unbekannte Datei.") from exc
    except BasemapUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=data,
        media_type=media_type,
        headers=ONLINE_CACHE_HEADERS,
    )


@online_router.get("/aerial/tiles/{z}/{x}/{y}.webp")
async def aerial_tile(z: int, x: int, y: int) -> Response:
    _require_online()
    try:
        data = await run_in_threadpool(basemap_service.aerial_tile, z, x, y)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BasemapUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=data,
        media_type="image/webp",
        headers=ONLINE_CACHE_HEADERS,
    )
