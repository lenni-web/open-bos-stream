"""Niederschlagsradar des Deutschen Wetterdienstes als Kartenebene.

Die Kacheln stammen aus dem öffentlichen DWD-GeoServer (Produkt RV:
Radarkomposit mit Vorhersage, 1 km, alle 5 Minuten) und werden – wie die
Drohnen-Geozonen – über den eigenen Server geladen und kurz
zwischengespeichert. Quelle: Deutscher Wetterdienst.

Der DWD-Dienst antwortet langsam (mehrere Sekunden je Bild, vor allem bei
vergangenen Zeitpunkten). Deshalb holt der Server jeweils einen Block von
2 × 2 Kacheln in einer Anfrage (512 Pixel) und schneidet ihn selbst, und er
lädt die Zeitleiste rund um den Wetter-Standort im Hintergrund vor.
"""

from __future__ import annotations

import io
import math
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
# Vorladen der Zeitleiste: Kacheln rund um den Standort, höchstens alle
# vier Minuten erneut (nur solange die Wetterseite genutzt wird).
WARM_RADIUS_TILES = 1
WARM_INTERVAL_SECONDS = 4 * 60
# Nicht alle 8 DWD-Verbindungen: Live-Anfragen behalten zwei freie Plätze.
WARM_WORKERS = 6


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
        # Laufende Block-Abrufe: weitere Anfragen derselben Kacheln warten.
        self._inflight: dict[str, threading.Event] = {}
        self._warm_lock = threading.Lock()
        self._warming = False
        self._last_warm: float | None = None

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

    def is_settled(self, stamp: str) -> bool:
        """Liegt der Zeitpunkt so weit zurück, dass sich das Bild nicht mehr ändert?"""

        now = self._now()
        return parse_stamp(stamp, now) <= now - timedelta(minutes=SETTLED_MINUTES)

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

    @staticmethod
    def _key(time_value: str | None, z: int, x: int, y: int) -> str:
        return f"{time_value or 'current'}:{z}:{x}:{y}"

    @staticmethod
    def _params(time_value: str | None, z: int, x: int, y: int, size: int) -> dict[str, str]:
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetMap",
            "LAYERS": LAYER,
            "STYLES": "",
            "CRS": "EPSG:3857",
            "BBOX": ",".join(f"{value:.3f}" for value in tile_bbox(z, x, y)),
            "WIDTH": str(size),
            "HEIGHT": str(size),
            "FORMAT": "image/png",
            "TRANSPARENT": "TRUE",
        }
        if time_value:
            params["TIME"] = time_value
        return params

    def _cached(self, key: str, cache_seconds: int) -> bytes | None:
        now = self._clock()
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and now - entry[0] < cache_seconds:
                self._cache.move_to_end(key)
                return entry[1]
        return None

    def _store(self, items: dict[str, bytes]) -> None:
        now = self._clock()
        with self._lock:
            for key, data in items.items():
                self._cache[key] = (now, data)
                self._cache.move_to_end(key)
            while len(self._cache) > CACHE_MAX_ENTRIES:
                self._cache.popitem(last=False)

    @staticmethod
    def _split_block(data: bytes) -> dict[tuple[int, int], bytes]:
        """512er-Bild in vier 256er-Kacheln (dx, dy) zerlegen."""

        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if image.size != (2 * TILE_SIZE, 2 * TILE_SIZE):
                raise ValueError("Unerwartete Bildgröße.")
            parts = {}
            for dx in (0, 1):
                for dy in (0, 1):
                    part = image.crop((
                        dx * TILE_SIZE, dy * TILE_SIZE,
                        (dx + 1) * TILE_SIZE, (dy + 1) * TILE_SIZE,
                    ))
                    buffer = io.BytesIO()
                    part.save(buffer, format="PNG")
                    parts[(dx, dy)] = buffer.getvalue()
            return parts

    def _fetch_block(self, time_value: str | None, z: int, x: int, y: int) -> None:
        """Übergeordnete Kachel (z-1) mit 512 Pixeln holen und zerlegen.

        Gleichzeitige Anfragen für denselben Block warten auf den ersten
        Abruf, statt den DWD mehrfach zu fragen.
        """

        px, py = x // 2, y // 2
        block_key = self._key(time_value, z - 1, px, py)
        with self._lock:
            event = self._inflight.get(block_key)
            owner = event is None
            if owner:
                event = threading.Event()
                self._inflight[block_key] = event
        if not owner:
            event.wait(REQUEST_TIMEOUT_SECONDS * 3)
            return
        try:
            with self._slots:
                data = self._fetch(self._params(time_value, z - 1, px, py, 2 * TILE_SIZE))
            parts = self._split_block(data)
            self._store({
                self._key(time_value, z, 2 * px + dx, 2 * py + dy): part
                for (dx, dy), part in parts.items()
            })
        except (ValueError, OSError):
            # Kein zerlegbares Bild: der Aufrufer holt die Einzelkachel.
            pass
        finally:
            with self._lock:
                self._inflight.pop(block_key, None)
            event.set()

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

        key = self._key(time_value, z, x, y)
        cached = self._cached(key, cache_seconds)
        if cached is not None:
            return cached

        if z - 1 >= MIN_ZOOM:
            self._fetch_block(time_value, z, x, y)
            cached = self._cached(key, cache_seconds)
            if cached is not None:
                return cached

        with self._slots:
            data = self._fetch(self._params(time_value, z, x, y, TILE_SIZE))
        self._store({key: data})
        return data

    # ------------------------------------------------------------------
    # Vorladen der Zeitleiste
    # ------------------------------------------------------------------

    @staticmethod
    def tile_for(latitude: float, longitude: float, z: int) -> tuple[int, int]:
        n = 2 ** z
        lat = max(-85.0, min(85.0, latitude))
        x = int((longitude + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
        return max(0, min(n - 1, x)), max(0, min(n - 1, y))

    def warm_tiles(self, latitude: float, longitude: float, z: int = TIMELINE_MAX_ZOOM) -> list[tuple[int, int, int]]:
        """Je Block eine Kachel rund um den Standort (lädt den ganzen Block)."""

        cx, cy = self.tile_for(latitude, longitude, z)
        blocks = {}
        for dx in range(-WARM_RADIUS_TILES, WARM_RADIUS_TILES + 1):
            for dy in range(-WARM_RADIUS_TILES, WARM_RADIUS_TILES + 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < 2 ** z and 0 <= y < 2 ** z:
                    blocks.setdefault((x // 2, y // 2), (z, x, y))
        return list(blocks.values())

    def warm(self, latitude: float, longitude: float, frames: list[dict], *, background: bool = True) -> bool:
        """Zeitleiste vorladen (beginnend bei „jetzt“); False, wenn unnötig."""

        now = self._clock()
        with self._warm_lock:
            if self._warming or (
                self._last_warm is not None and now - self._last_warm < WARM_INTERVAL_SECONDS
            ):
                return False
            self._warming = True
            self._last_warm = now
        tiles = self.warm_tiles(latitude, longitude)
        ordered = sorted(frames, key=lambda frame: abs(frame.get("offset", 0)))
        jobs = [(frame["stamp"], tile) for frame in ordered for tile in tiles]

        pending = list(jobs)
        remaining = [WARM_WORKERS]
        queue_lock = threading.Lock()

        def worker() -> None:
            # Eigene Daemon-Threads statt ThreadPoolExecutor: dessen Threads
            # würden das Beenden des Dienstes bis zum Ende des Vorladens aufhalten.
            try:
                while True:
                    with queue_lock:
                        if not pending:
                            return
                        stamp, (z, x, y) = pending.pop(0)
                    try:
                        self.tile_at(stamp, z, x, y)
                    except (ValueError, RadarUnavailableError):
                        pass
            finally:
                with queue_lock:
                    remaining[0] -= 1
                    done = remaining[0] == 0
                if done:
                    with self._warm_lock:
                        self._warming = False

        threads = [
            threading.Thread(target=worker, name=f"open-bos-radar-warm-{index}", daemon=True)
            for index in range(WARM_WORKERS)
        ]
        for thread in threads:
            thread.start()
        if not background:
            for thread in threads:
                thread.join()
        return True

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
