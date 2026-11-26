"""Niederschlagsradar des Deutschen Wetterdienstes als Kartenebene.

Die Kacheln stammen aus dem öffentlichen DWD-GeoServer (Produkt RV:
Radarkomposit mit Vorhersage, 1 km, alle 5 Minuten) und werden – wie die
Drohnen-Geozonen – über den eigenen Server geladen und kurz
zwischengespeichert. Quelle: Deutscher Wetterdienst.
"""

from __future__ import annotations

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
CACHE_MAX_ENTRIES = 2000
REQUEST_TIMEOUT_SECONDS = 10
MAX_PARALLEL_REQUESTS = 4
# Das Radar hat 1 km Auflösung; höhere Zoomstufen vergrößert MapLibre selbst.
MIN_ZOOM = 4
MAX_ZOOM = 12
TILE_SIZE = 256
STEP_MINUTES = 5


class RadarUnavailableError(RuntimeError):
    """Der DWD-Dienst ist nicht erreichbar oder lieferte einen Fehler."""


def radar_time(offset_minutes: int, now: datetime) -> str | None:
    """WMS-Zeitstempel für eine Vorhersage; None steht für „aktuell“."""

    if offset_minutes == 0:
        return None
    base = now.astimezone(timezone.utc).replace(second=0, microsecond=0)
    base -= timedelta(minutes=base.minute % STEP_MINUTES)
    target = base + timedelta(minutes=offset_minutes)
    return target.strftime("%Y-%m-%dT%H:%M:00.000Z")


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
        time_value = radar_time(offset, self._now())
        if time_value:
            params["TIME"] = time_value
        key = f"{time_value or 'current'}:{z}:{x}:{y}"

        now = self._clock()
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and now - entry[0] < CACHE_SECONDS:
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
