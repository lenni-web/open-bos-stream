from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.map import MapService
from open_bos_stream.map.dipul import (
    ATTRIBUTION as DIPUL_ATTRIBUTION,
    LICENSE_URL as DIPUL_LICENSE_URL,
    MAP_TOOL_URL as DIPUL_MAP_TOOL_URL,
    DipulService,
    DipulUnavailableError,
)
from open_bos_stream.map.mbtiles import MBTilesError

router = APIRouter(
    prefix="/api/map",
    tags=["map"],
)

dipul_service = DipulService()


def _service() -> MapService:
    config = ConfigLoader().load()

    return MapService(
        config.map,
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

    data["center"] = (
        9.52972,
        53.56389,
        14,
    )

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
