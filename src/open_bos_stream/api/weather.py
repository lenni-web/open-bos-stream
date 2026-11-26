from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from open_bos_stream.auth.roles import ADMIN, GUEST
from open_bos_stream.core.container import (
    config as runtime_config,
    config_apply_service,
    server_event_log,
)
from open_bos_stream.core.models import WeatherConfig
from open_bos_stream.map.service import DEFAULT_CENTER
from datetime import datetime, timezone

from open_bos_stream.weather.radar import (
    RadarService,
    RadarUnavailableError,
    TIMELINE_MAX_ZOOM,
    TIMELINE_STEP_MINUTES,
    timeline_frames,
)
from open_bos_stream.weather.service import WeatherService

router = APIRouter(
    prefix="/api/weather",
    tags=["weather"],
)

weather_service = WeatherService()
radar_service = RadarService()


def _settings() -> WeatherConfig:
    return runtime_config.weather


def _require_enabled() -> WeatherConfig:
    settings = _settings()
    if not settings.enabled:
        raise HTTPException(
            status_code=404,
            detail="Das Wettermodul ist ausgeschaltet.",
        )
    return settings


def default_location(settings: WeatherConfig) -> dict:
    if settings.latitude is not None and settings.longitude is not None:
        return {
            "latitude": settings.latitude,
            "longitude": settings.longitude,
            "name": settings.location_name or "Eingestellter Standort",
            "origin": "configured",
        }
    longitude, latitude, _zoom = DEFAULT_CENTER
    return {
        "latitude": latitude,
        "longitude": longitude,
        "name": settings.location_name or "Kartenmitte",
        "origin": "map",
    }


@router.get("", dependencies=[GUEST])
async def weather(
    lat: float | None = None,
    lon: float | None = None,
) -> dict:
    settings = _require_enabled()
    if (lat is None) != (lon is None):
        raise HTTPException(
            status_code=400,
            detail="Breite und Länge gemeinsam angeben.",
        )
    if lat is not None:
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise HTTPException(status_code=400, detail="Ungültige Koordinate.")
        location = {
            "latitude": lat,
            "longitude": lon,
            "name": "Kartenausschnitt",
            "origin": "query",
        }
    else:
        location = default_location(settings)

    report = await run_in_threadpool(
        weather_service.report,
        settings,
        location["latitude"],
        location["longitude"],
    )
    report["location"] = location
    report["limits"] = settings.model_dump(
        include={
            "wind_limit_ms",
            "gust_limit_ms",
            "min_temperature_c",
            "max_temperature_c",
            "rain_limit_mm_h",
            "visibility_min_m",
        }
    )
    return report


@router.get("/radar", dependencies=[GUEST])
def radar_layers() -> dict:
    settings = _settings()
    return {"enabled": settings.enabled, **radar_service.layers()}


@router.get(
    "/radar/tiles/{offset}/{z}/{x}/{y}.png",
    dependencies=[GUEST],
)
async def radar_tile(offset: int, z: int, x: int, y: int) -> Response:
    _require_enabled()
    try:
        data = await run_in_threadpool(radar_service.tile, offset, z, x, y)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Unbekannter Radarzeitpunkt.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RadarUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=240"},
    )


@router.get("/radar/frames", dependencies=[GUEST])
def radar_frames() -> dict:
    settings = _require_enabled()
    return {
        "frames": timeline_frames(datetime.now(timezone.utc)),
        "step_minutes": TIMELINE_STEP_MINUTES,
        "location": default_location(settings),
        **radar_service.layers(),
        "max_zoom": TIMELINE_MAX_ZOOM,
    }


@router.get(
    "/radar/time/{stamp}/{z}/{x}/{y}.png",
    dependencies=[GUEST],
)
async def radar_tile_at(stamp: str, z: int, x: int, y: int) -> Response:
    _require_enabled()
    try:
        data = await run_in_threadpool(radar_service.tile_at, stamp, z, x, y)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RadarUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=240"},
    )


@router.get("/settings", dependencies=[ADMIN])
def weather_settings() -> dict:
    return {"weather": _settings()}


@router.put("/settings", dependencies=[ADMIN])
async def save_weather_settings(
    weather: WeatherConfig,
    request: Request,
) -> dict:
    saved = await run_in_threadpool(
        config_apply_service.update_weather,
        weather,
    )
    user = getattr(request.state, "user", None) or {}
    server_event_log.record(
        "info",
        "🌦 Wettereinstellungen gespeichert",
        actor=user.get("username"),
    )
    return {
        "success": True,
        "message": "Wettereinstellungen wurden gespeichert.",
        "weather": saved,
    }
