"""Online-Grundkarten: basemap.de (BKG) und Luftbild Niedersachsen (LGLN).

Alle Abrufe laufen über den eigenen Server. Browser verbinden sich dadurch
nur mit Open BOS Stream, und wiederholte Abrufe kommen aus dem
Zwischenspeicher. Luftbilder liegen zusätzlich dauerhaft auf der Festplatte,
damit sie Neustarts und Ausfälle des Landesdienstes überstehen.

* basemap.de Web Vektor – amtliche Vektorkarte für Deutschland,
  © basemap.de / BKG, Datenquellen © GeoBasis-DE.
* LGLN DOP20 – digitale Orthophotos (20 cm) für Niedersachsen,
  Lizenz CC BY 4.0, Rechteinhaber LGLN.
"""

from __future__ import annotations

import copy
import gzip
import io
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from datetime import date
from typing import Callable

from open_bos_stream.map.dipul import tile_bbox
from open_bos_stream.map.tile_cache import TileDiskCache


BASEMAP_ROOT = "https://sgx.geodatenzentrum.de/gdz_basemapde_vektor"
STYLE_URLS = {
    "col": f"{BASEMAP_ROOT}/styles/bm_web_col.json",
    "gry": f"{BASEMAP_ROOT}/styles/bm_web_gry.json",
    # Nachtstil (Beta) für die dunkle Darstellung.
    "drk": "https://basemap.de/data/produkte/web_vektor/styles/bm_web_drk.json",
}
TILE_URL = f"{BASEMAP_ROOT}/tiles/v2/bm_web_de_3857/{{z}}/{{x}}/{{y}}.pbf"
FONT_URL = f"{BASEMAP_ROOT}/fonts/v2/{{fontstack}}/{{range}}.pbf"
SPRITE_URL = f"{BASEMAP_ROOT}/sprites/v2/{{filename}}"
BASEMAP_ATTRIBUTION = "© basemap.de / BKG | Datenquellen: © GeoBasis-DE"
BASEMAP_MAX_ZOOM = 15
BASEMAP_BOUNDS = [5.8, 47.2, 15.1, 55.1]

AERIAL_WMS_URL = "https://opendata.lgln.niedersachsen.de/doorman/noauth/dop_wms"
AERIAL_LAYER = "ni_dop20"
AERIAL_MIN_ZOOM = 8
AERIAL_MAX_ZOOM = 19
# Grobe Ausdehnung Niedersachsens; außerhalb liefert der Dienst nichts.
AERIAL_BOUNDS = [6.6, 51.29, 11.6, 53.9]
AERIAL_QUALITY = 78
# Luftbilder werden nur alle paar Jahre neu beflogen.
AERIAL_FRESH_SECONDS = 30 * 24 * 60 * 60
# Nach so vielen Fehlern in Folge gilt der Dienst als ausgefallen. Ein
# einzelner Aussetzer soll nicht alle anderen Kacheln sperren.
AERIAL_FAILURE_LIMIT = 5
AERIAL_PAUSE_SECONDS = 60
# Ohne neue Anfragen verschwindet der Hinweis nach dieser Zeit wieder.
AERIAL_NOTICE_SECONDS = 10 * 60

SPRITE_PATTERN = re.compile(r"^bm_web_(col|gry|drk|top)_sprite(@2x)?\.(json|png)$")
FONTSTACK_PATTERN = re.compile(r"^[A-Za-z0-9 ,_-]{1,120}$")
RANGE_PATTERN = re.compile(r"^\d{1,5}-\d{1,5}$")

STYLE_CACHE_SECONDS = 24 * 60 * 60
TILE_CACHE_SECONDS = 24 * 60 * 60
CACHE_MAX_ENTRIES = 1500
REQUEST_TIMEOUT_SECONDS = 15
MAX_PARALLEL_REQUESTS = 8

# Relative Pfade: Der Browser ergänzt Protokoll und Host selbst. So
# stimmen die Adressen auch hinter einem HTTPS-Proxy.
LOCAL_PREFIX = "/api/map"


def aerial_attribution() -> str:
    return f"Luftbild: © LGLN ({date.today().year}), CC BY 4.0"


class BasemapUnavailableError(RuntimeError):
    """Der Kartendienst ist nicht erreichbar oder lieferte einen Fehler."""


class BasemapNotFoundError(BasemapUnavailableError):
    """Für diese Stelle gibt es keine Kachel (z. B. außerhalb Deutschlands)."""


def _check_tile(z: int, x: int, y: int, min_zoom: int, max_zoom: int) -> None:
    if not min_zoom <= z <= max_zoom or not (
        0 <= x < 2 ** z and 0 <= y < 2 ** z
    ):
        raise ValueError("Kachel außerhalb des unterstützten Bereichs.")


def rewrite_style(style: dict) -> dict:
    """basemap.de-Stil auf die Abrufe über den eigenen Server umstellen."""

    result = copy.deepcopy(style)
    result["glyphs"] = f"{LOCAL_PREFIX}/basemap/fonts/{{fontstack}}/{{range}}.pbf"
    sprite = str(result.get("sprite", ""))
    sprite_name = sprite.rstrip("/").rsplit("/", 1)[-1]
    if sprite_name:
        result["sprite"] = f"{LOCAL_PREFIX}/basemap/sprites/{sprite_name}"
    for source in result.get("sources", {}).values():
        if source.get("type") != "vector":
            continue
        source.pop("url", None)
        source["tiles"] = [f"{LOCAL_PREFIX}/basemap/tiles/{{z}}/{{x}}/{{y}}.pbf"]
        source["minzoom"] = 0
        source["maxzoom"] = BASEMAP_MAX_ZOOM
        source["bounds"] = BASEMAP_BOUNDS
        source["attribution"] = BASEMAP_ATTRIBUTION
    return result


class BasemapService:
    def __init__(
        self,
        *,
        fetch: Callable[[str], tuple[bytes, str]] | None = None,
        clock: Callable[[], float] = time.monotonic,
        aerial_cache: TileDiskCache | None = None,
    ) -> None:
        self._fetch = fetch or self._http_get
        self._clock = clock
        self._cache: OrderedDict[str, tuple[float, bytes, str]] = OrderedDict()
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(MAX_PARALLEL_REQUESTS)
        # Eigene Plätze, damit ein träges Luftbild die Karte nicht bremst.
        self._aerial_slots = threading.BoundedSemaphore(MAX_PARALLEL_REQUESTS)
        self._aerial_cache = aerial_cache
        self._aerial_failures = 0
        self._aerial_failed_at = 0.0

    # ---------------------------------------------------------
    # basemap.de
    # ---------------------------------------------------------

    def style(self, variant: str) -> dict:
        url = STYLE_URLS.get(variant)
        if url is None:
            raise KeyError(variant)
        data, _ = self._cached(f"style:{variant}", url, STYLE_CACHE_SECONDS)
        try:
            style = json.loads(data)
        except ValueError as exc:
            raise BasemapUnavailableError(
                "basemap.de lieferte keinen gültigen Kartenstil."
            ) from exc
        return rewrite_style(style)

    def tile(self, z: int, x: int, y: int) -> bytes:
        """Vektorkachel, gzip-komprimiert für die Auslieferung."""

        _check_tile(z, x, y, 0, BASEMAP_MAX_ZOOM)
        url = TILE_URL.format(z=z, x=x, y=y)
        try:
            data, _ = self._cached(
                f"tile:{z}:{x}:{y}",
                url,
                TILE_CACHE_SECONDS,
                transform=self._gzip,
            )
        except BasemapNotFoundError:
            return b""
        return data

    def font(self, fontstack: str, glyph_range: str) -> bytes:
        if not FONTSTACK_PATTERN.match(fontstack) or not RANGE_PATTERN.match(
            glyph_range
        ):
            raise ValueError("Ungültige Schriftanfrage.")
        url = FONT_URL.format(
            fontstack=urllib.parse.quote(fontstack),
            range=glyph_range,
        )
        data, _ = self._cached(
            f"font:{fontstack}:{glyph_range}",
            url,
            TILE_CACHE_SECONDS,
        )
        return data

    def sprite(self, filename: str) -> tuple[bytes, str]:
        if not SPRITE_PATTERN.match(filename):
            raise KeyError(filename)
        data, content_type = self._cached(
            f"sprite:{filename}",
            SPRITE_URL.format(filename=filename),
            STYLE_CACHE_SECONDS,
        )
        media_type = (
            "application/json" if filename.endswith(".json") else "image/png"
        )
        return data, media_type

    # ---------------------------------------------------------
    # Luftbild Niedersachsen
    # ---------------------------------------------------------

    def aerial_tile(self, z: int, x: int, y: int) -> bytes:
        """Luftbildkachel als WebP; außerhalb Niedersachsens transparent."""

        _check_tile(z, x, y, AERIAL_MIN_ZOOM, AERIAL_MAX_ZOOM)
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetMap",
            "LAYERS": AERIAL_LAYER,
            "STYLES": "",
            "CRS": "EPSG:3857",
            "BBOX": ",".join(f"{value:.3f}" for value in tile_bbox(z, x, y)),
            "WIDTH": "256",
            "HEIGHT": "256",
            # PNG wegen der Transparenz außerhalb des Landes; die Umrechnung
            # in WebP spart rund 90 % der Datenmenge.
            "FORMAT": "image/png",
            "TRANSPARENT": "TRUE",
        }
        url = f"{AERIAL_WMS_URL}?{urllib.parse.urlencode(params)}"
        stored = (
            self._aerial_cache.get(z, x, y) if self._aerial_cache else None
        )
        if stored is not None and stored[1] < AERIAL_FRESH_SECONDS:
            return stored[0]
        try:
            data = self._fetch_aerial(url)
        except BasemapUnavailableError:
            # Eine alte Kachel ist besser als eine Lücke.
            if stored is not None:
                return stored[0]
            raise
        if self._aerial_cache:
            self._aerial_cache.put(z, x, y, data)
        return data

    def aerial_available(self) -> bool:
        with self._lock:
            return (
                self._aerial_failures < AERIAL_FAILURE_LIMIT
                or self._clock() - self._aerial_failed_at >= AERIAL_NOTICE_SECONDS
            )

    def _aerial_paused(self) -> bool:
        with self._lock:
            return (
                self._aerial_failures >= AERIAL_FAILURE_LIMIT
                and self._clock() - self._aerial_failed_at < AERIAL_PAUSE_SECONDS
            )

    def _fetch_aerial(self, url: str) -> bytes:
        with self._aerial_slots:
            # Erst hier prüfen: Wartende Abrufe sehen den Ausfall mit.
            if self._aerial_paused():
                raise BasemapUnavailableError("Der Luftbilddienst ist nicht erreichbar.")
            try:
                data, content_type = self._fetch(url)
                if not content_type.startswith("image/"):
                    raise BasemapUnavailableError(
                        "Der Luftbilddienst lieferte kein Bild: "
                        + data[:200].decode("utf-8", errors="replace")
                    )
                data = self._webp(data)
            except BasemapNotFoundError:
                raise
            except (BasemapUnavailableError, OSError, ValueError) as exc:
                with self._lock:
                    self._aerial_failures += 1
                    self._aerial_failed_at = self._clock()
                if isinstance(exc, BasemapUnavailableError):
                    raise
                raise BasemapUnavailableError(
                    f"Kartendaten konnten nicht verarbeitet werden: {exc}"
                ) from exc
        with self._lock:
            self._aerial_failures = 0
        return data

    # ---------------------------------------------------------
    # Abruf und Zwischenspeicher
    # ---------------------------------------------------------

    @staticmethod
    def _gzip(data: bytes) -> bytes:
        if data[:2] == b"\x1f\x8b":
            return data
        return gzip.compress(data, compresslevel=6)

    @staticmethod
    def _webp(data: bytes) -> bytes:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            image.load()
            output = io.BytesIO()
            image.convert("RGBA").save(
                output,
                format="WEBP",
                quality=AERIAL_QUALITY,
                method=4,
            )
        return output.getvalue()

    def _cached(
        self,
        key: str,
        url: str,
        ttl: float,
        *,
        transform: Callable[[bytes], bytes] | None = None,
    ) -> tuple[bytes, str]:
        now = self._clock()
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and now - entry[0] < ttl:
                self._cache.move_to_end(key)
                return entry[1], entry[2]

        with self._slots:
            data, content_type = self._fetch(url)
        if transform is not None:
            try:
                data = transform(data)
            except (OSError, ValueError) as exc:
                raise BasemapUnavailableError(
                    f"Kartendaten konnten nicht verarbeitet werden: {exc}"
                ) from exc

        with self._lock:
            self._cache[key] = (now, data, content_type)
            self._cache.move_to_end(key)
            while len(self._cache) > CACHE_MAX_ENTRIES:
                self._cache.popitem(last=False)
        return data, content_type

    @staticmethod
    def _http_get(url: str) -> tuple[bytes, str]:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Open-BOS-Stream"},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=REQUEST_TIMEOUT_SECONDS,
            ) as response:
                return (
                    response.read(),
                    response.headers.get("Content-Type", ""),
                )
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise BasemapNotFoundError("Keine Kachel") from exc
            raise BasemapUnavailableError(
                f"Kartendienst antwortete mit HTTP {exc.code}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BasemapUnavailableError(
                "Kartendienst ist nicht erreichbar"
            ) from exc
