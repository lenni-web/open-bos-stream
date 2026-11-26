"""Niederschlagsradar des Deutschen Wetterdienstes als Kartenebene.

Die Kacheln stammen aus dem öffentlichen DWD-GeoServer (Produkt RV:
Radarkomposit mit Vorhersage, 1 km, alle 5 Minuten) und werden – wie die
Drohnen-Geozonen – über den eigenen Server geladen und kurz
zwischengespeichert. Quelle: Deutscher Wetterdienst.
"""

from __future__ import annotations

import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Callable

from open_bos_stream.map.dipul import tile_bbox


WMS_URL = "https://maps.dwd.de/geoserver/dwd/wms"
LAYER = "dwd:Niederschlagsradar"
ATTRIBUTION = "Niederschlagsradar: Deutscher Wetterdienst"
COPYRIGHT_URL = "https://www.dwd.de/copyright"

# Vorhersage reicht etwa zwei Stunden über die letzte Messung hinaus;
# 90 Minuten liegen sicher innerhalb.
OFFSETS_MINUTES = (0, 15, 30, 60, 90)
CACHE_SECONDS = 4 * 60
CACHE_MAX_ENTRIES = 4000
REQUEST_TIMEOUT_SECONDS = 10
MAX_PARALLEL_REQUESTS = 8
# Das Radar hat 1 km Auflösung; höhere Zoomstufen vergrößert MapLibre selbst.
MIN_ZOOM = 4
MAX_ZOOM = 12
# Zeitleiste: gröbere Kacheln (Zoom 7 ≈ 0,7 km je Pixel in Norddeutschland)
# reichen für die Auflösung des Radars und laden viermal weniger Bilder.
TIMELINE_MAX_ZOOM = 7
TILE_SIZE = 256
STEP_MINUTES = 5

# Zeitleiste der Wetterseite: zwei Stunden Rückblick, 90 Minuten Vorhersage.
TIMELINE_PAST_MINUTES = 120
TIMELINE_FUTURE_MINUTES = 90
TIMELINE_STEP_MINUTES = 10
# Etwas Spielraum, falls Browser und Server-Uhr leicht auseinanderliegen.
TIMELINE_TOLERANCE_MINUTES = 30
# Vergangene Radarbilder ändern sich nicht mehr und dürfen länger im Speicher
# bleiben; aktuelle und vorhergesagte werden alle paar Minuten neu berechnet.
PAST_CACHE_SECONDS = 60 * 60
SETTLED_MINUTES = 15
STAMP_PATTERN = re.compile(r"^\d{12}$")


class RadarUnavailableError(RuntimeError):
    """Der DWD-Dienst ist nicht erreichbar oder lieferte einen Fehler."""


def _base(now: datetime) -> datetime:
    base = now.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return base - timedelta(minutes=base.minute % STEP_MINUTES)


def _wms_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:00.000Z")


def timeline_frames(now: datetime) -> list[dict]:
    """Zeitpunkte der Radar-Zeitleiste (UTC) mit Abstand zu „jetzt“."""

    base = _base(now)
    return [
        {
            "stamp": (base + timedelta(minutes=offset)).strftime("%Y%m%d%H%M"),
            "time": (base + timedelta(minutes=offset)).isoformat().replace(
                "+00:00", "Z"
            ),
            "offset": offset,
        }
        for offset in range(
            -TIMELINE_PAST_MINUTES,
            TIMELINE_FUTURE_MINUTES + 1,
            TIMELINE_STEP_MINUTES,
        )
    ]


def parse_stamp(stamp: str, now: datetime) -> datetime:
    """Zeitstempel JJJJMMTTHHMM prüfen (5-Minuten-Raster, Zeitleiste)."""

    if not STAMP_PATTERN.match(stamp):
        raise ValueError("Ungültiger Radarzeitpunkt.")
    try:
        value = datetime.strptime(stamp, "%Y%m%d%H%M").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ValueError("Ungültiger Radarzeitpunkt.") from exc
    if value.minute % STEP_MINUTES:
        raise ValueError("Radarzeitpunkte liegen im 5-Minuten-Raster.")
    base = _base(now)
    earliest = base - timedelta(
        minutes=TIMELINE_PAST_MINUTES + TIMELINE_TOLERANCE_MINUTES
    )
    latest = base + timedelta(
        minutes=TIMELINE_FUTURE_MINUTES + TIMELINE_TOLERANCE_MINUTES
    )
    if not earliest <= value <= latest:
        raise ValueError("Radarzeitpunkt außerhalb der Zeitleiste.")
    return value


def radar_time(offset_minutes: int, now: datetime) -> str | None:
    """WMS-Zeitstempel für eine Vorhersage; None steht für „aktuell“."""

    if offset_minutes == 0:
        return None
    return _wms_time(_base(now) + timedelta(minutes=offset_minutes))


class RadarService:
    def __init__(
        self,
        *,
        fetch: Callable[[dict[str, str]], bytes] | None = None,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._fetch = fetch or self._http_get
        self._clock = clock
        self._now = now
        self._cache: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(MAX_PARALLEL_REQUESTS)

    @staticmethod
    def layers() -> dict:
        return {
            "offsets": [
                {
                    "minutes": offset,
                    "label": "Jetzt" if offset == 0 else f"+{offset} min",
                }
                for offset in OFFSETS_MINUTES
            ],
            "min_zoom": MIN_ZOOM,
            "max_zoom": MAX_ZOOM,
            "attribution": ATTRIBUTION,
            "copyright_url": COPYRIGHT_URL,
        }

    def tile(self, offset: int, z: int, x: int, y: int) -> bytes:
        if offset not in OFFSETS_MINUTES:
            raise KeyError(offset)
        return self._tile(radar_time(offset, self._now()), z, x, y, CACHE_SECONDS)

    def tile_at(self, stamp: str, z: int, x: int, y: int) -> bytes:
        """Radarkachel für einen festen Zeitpunkt der Zeitleiste."""

        now = self._now()
        value = parse_stamp(stamp, now)
        settled = value <= now - timedelta(minutes=SETTLED_MINUTES)
        return self._tile(
            _wms_time(value),
            z,
            x,
            y,
            PAST_CACHE_SECONDS if settled else CACHE_SECONDS,
        )

    def _tile(
        self,
        time_value: str | None,
        z: int,
        x: int,
        y: int,
        cache_seconds: int,
    ) -> bytes:
        if not MIN_ZOOM <= z <= MAX_ZOOM or not (
            0 <= x < 2 ** z and 0 <= y < 2 ** z
        ):
            raise ValueError("Kachel außerhalb des unterstützten Bereichs.")

        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetMap",
            "LAYERS": LAYER,
            "STYLES": "",
            "CRS": "EPSG:3857",
            "BBOX": ",".join(f"{value:.3f}" for value in tile_bbox(z, x, y)),
            "WIDTH": str(TILE_SIZE),
            "HEIGHT": str(TILE_SIZE),
            "FORMAT": "image/png",
            "TRANSPARENT": "TRUE",
        }
        if time_value:
            params["TIME"] = time_value
        key = f"{time_value or 'current'}:{z}:{x}:{y}"

        now = self._clock()
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and now - entry[0] < cache_seconds:
                self._cache.move_to_end(key)
                return entry[1]

        with self._slots:
            data = self._fetch(params)

        with self._lock:
            self._cache[key] = (now, data)
            self._cache.move_to_end(key)
            while len(self._cache) > CACHE_MAX_ENTRIES:
                self._cache.popitem(last=False)
        return data

    @staticmethod
    def _http_get(params: dict[str, str]) -> bytes:
        url = f"{WMS_URL}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Open-BOS-Stream"},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=REQUEST_TIMEOUT_SECONDS,
            ) as response:
                content_type = response.headers.get("Content-Type", "")
                data = response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RadarUnavailableError(
                f"DWD-Radar ist nicht erreichbar: {exc}"
            ) from exc

        # GeoServer meldet Fehler (z. B. Zeit außerhalb) als XML mit Status 200.
        if not content_type.startswith("image/"):
            raise RadarUnavailableError(
                "DWD-Radar lieferte keine Kachel: "
                + data[:200].decode("utf-8", errors="replace")
            )
        return data
