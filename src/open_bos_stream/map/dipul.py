"""Drohnen-Geozonen der Digitalen Plattform Unbemannte Luftfahrt (dipul).

Die Kartenbilder des öffentlichen dipul-WMS werden über den eigenen Server
abgerufen, damit Browser keine Verbindung zu externen Diensten aufbauen und
wiederholte Abrufe aus einem Zwischenspeicher bedient werden. Die Daten stehen
unter CC BY-ND 4.0 und werden unverändert ausgeliefert.
"""

from __future__ import annotations

import logging
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass


logger = logging.getLogger(__name__)

WMS_URL = "https://uas-betrieb.de/geoservices/dipul/wms"
MAP_TOOL_URL = "https://maptool-dipul.dfs.de/"
ATTRIBUTION = "© dipul (DFS), Lizenz CC BY-ND 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-nd/4.0/deed.de"

CACHE_SECONDS = 60 * 60
CACHE_MAX_ENTRIES = 3000
REQUEST_TIMEOUT_SECONDS = 10
MAX_PARALLEL_REQUESTS = 4
MIN_ZOOM = 6
MAX_ZOOM = 19
TILE_SIZE = 256
WEB_MERCATOR_EXTENT = 20037508.342789244


@dataclass(frozen=True)
class LayerGroup:
    id: str
    title: str
    layers: tuple[str, ...]
    visible: bool


LAYER_GROUPS: tuple[LayerGroup, ...] = (
    LayerGroup(
        "luftraum",
        "Luftraum",
        (
            "kontrollzonen",
            "flughaefen",
            "flugplaetze",
            "flugbeschraenkungsgebiete",
        ),
        True,
    ),
    LayerGroup(
        "temporaer",
        "Temporäre Einschränkungen",
        ("temporaere_betriebseinschraenkungen",),
        True,
    ),
    LayerGroup(
        "schutzgebiete",
        "Schutzgebiete",
        (
            "naturschutzgebiete",
            "nationalparks",
            "ffh-gebiete",
            "vogelschutzgebiete",
        ),
        True,
    ),
    LayerGroup(
        "infrastruktur",
        "Infrastruktur",
        (
            "industrieanlagen",
            "kraftwerke",
            "umspannwerke",
            "stromleitungen",
            "windkraftanlagen",
        ),
        True,
    ),
    LayerGroup(
        "verkehr",
        "Verkehrswege",
        (
            "bundesautobahnen",
            "bundesstrassen",
            "bahnanlagen",
            "binnenwasserstrassen",
            "seewasserstrassen",
            "schifffahrtsanlagen",
        ),
        False,
    ),
    LayerGroup(
        "einrichtungen",
        "Einrichtungen",
        (
            "krankenhaeuser",
            "polizei",
            "sicherheitsbehoerden",
            "behoerden",
            "justizvollzugsanstalten",
            "militaerische_anlagen",
            "diplomatische_vertretungen",
            "internationale_organisationen",
            "labore",
        ),
        False,
    ),
    LayerGroup(
        "sonstiges",
        "Sonstiges",
        (
            "wohngrundstuecke",
            "freibaeder",
            "modellflugplaetze",
            "haengegleiter",
        ),
        False,
    ),
)

GROUPS_BY_ID = {group.id: group for group in LAYER_GROUPS}

# Lesbare Art einer Zone je dipul-Ebene. Die Typkürzel der Daten selbst
# (z. B. "U_NFZ") sind nicht einheitlich und eignen sich nicht zur Anzeige.
LAYER_LABELS = {
    "bahnanlagen": "Bahnanlage",
    "behoerden": "Bundes- oder Landesbehörde",
    "binnenwasserstrassen": "Binnenwasserstraße",
    "bundesautobahnen": "Bundesautobahn",
    "bundesstrassen": "Bundesstraße",
    "diplomatische_vertretungen": "Diplomatische Vertretung",
    "ffh-gebiete": "FFH-Gebiet",
    "flugbeschraenkungsgebiete": "Flugbeschränkungsgebiet",
    "flughaefen": "Flughafen",
    "flugplaetze": "Flugplatz",
    "freibaeder": "Freibad oder Badestrand",
    "haengegleiter": "Hängegleitergelände",
    "industrieanlagen": "Industrieanlage",
    "internationale_organisationen": "Internationale Organisation",
    "justizvollzugsanstalten": "JVA oder Maßregelvollzug",
    "kontrollzonen": "Kontrollzone",
    "kraftwerke": "Kraftwerk",
    "krankenhaeuser": "Krankenhaus",
    "labore": "Einrichtung BSL-4",
    "militaerische_anlagen": "Militärische Anlage",
    "modellflugplaetze": "Modellflugplatz",
    "nationalparks": "Nationalpark",
    "naturschutzgebiete": "Naturschutzgebiet",
    "polizei": "Liegenschaft der Polizei",
    "schifffahrtsanlagen": "Schifffahrtsanlage",
    "seewasserstrassen": "Seewasserstraße",
    "sicherheitsbehoerden": "Sicherheitsbehörde",
    "stromleitungen": "Stromleitung",
    "temporaere_betriebseinschraenkungen": "Temporäre Betriebseinschränkung",
    "umspannwerke": "Umspannwerk",
    "vogelschutzgebiete": "Vogelschutzgebiet",
    "windkraftanlagen": "Windkraftanlage",
    "wohngrundstuecke": "Wohngrundstück",
}


class DipulUnavailableError(RuntimeError):
    """Der dipul-Dienst ist nicht erreichbar oder lieferte einen Fehler."""


def tile_bbox(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Web-Mercator-Ausdehnung (EPSG:3857) einer XYZ-Kachel."""

    size = 2 * WEB_MERCATOR_EXTENT / (2 ** z)
    min_x = -WEB_MERCATOR_EXTENT + x * size
    max_y = WEB_MERCATOR_EXTENT - y * size
    return (min_x, max_y - size, min_x + size, max_y)


def parse_feature_info(text: str) -> list[dict]:
    """GeoServer-Textausgabe von GetFeatureInfo in Zonen übersetzen."""

    zones: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("Results for FeatureType"):
            layer = line.split("'")[1] if "'" in line else ""
            current = {"layer": layer.rsplit(":", 1)[-1]}
            zones.append(current)
            continue
        if current is None or " = " not in line:
            continue
        key, value = line.split(" = ", 1)
        if key == "geom":
            continue
        current[key.strip()] = value.strip()

    result = []
    for zone in zones:
        label = LAYER_LABELS.get(zone["layer"], zone["layer"])
        name = (
            zone.get("generated_name_DE")
            or zone.get("name")
            or label
        )
        result.append(
            {
                "layer": zone["layer"],
                "name": name,
                "type": label,
                "lower_limit": _limit(zone, "lower"),
                "upper_limit": _limit(zone, "upper"),
                "legal_ref": zone.get("legal_ref") or None,
            }
        )
    return result


def _limit(zone: dict, prefix: str) -> str | None:
    altitude = zone.get(f"{prefix}_limit_altitude")
    if altitude in (None, ""):
        return None
    try:
        value = float(altitude)
    except ValueError:
        return None
    unit = zone.get(f"{prefix}_limit_unit", "").lower()
    reference = zone.get(f"{prefix}_limit_alt_ref", "")
    number = f"{value:.0f}" if value.is_integer() or value > 10 else f"{value:g}"
    return " ".join(part for part in (number, unit, reference) if part)


class DipulService:
    def __init__(
        self,
        *,
        fetch=None,
        clock=time.monotonic,
        cache_seconds: int = CACHE_SECONDS,
        max_entries: int = CACHE_MAX_ENTRIES,
    ) -> None:
        self._fetch = fetch or self._http_get
        self._clock = clock
        self._cache_seconds = cache_seconds
        self._max_entries = max_entries
        self._cache: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(MAX_PARALLEL_REQUESTS)

    @staticmethod
    def groups() -> list[dict]:
        return [
            {
                "id": group.id,
                "title": group.title,
                "visible": group.visible,
                "layers": list(group.layers),
            }
            for group in LAYER_GROUPS
        ]

    def tile(self, group_id: str, z: int, x: int, y: int) -> bytes:
        group = GROUPS_BY_ID.get(group_id)
        if group is None:
            raise KeyError(group_id)
        if not MIN_ZOOM <= z <= MAX_ZOOM or not (
            0 <= x < 2 ** z and 0 <= y < 2 ** z
        ):
            raise ValueError("Kachel außerhalb des unterstützten Bereichs.")

        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetMap",
            "LAYERS": ",".join(group.layers),
            "STYLES": "",
            "CRS": "EPSG:3857",
            "BBOX": ",".join(f"{value:.3f}" for value in tile_bbox(z, x, y)),
            "WIDTH": str(TILE_SIZE),
            "HEIGHT": str(TILE_SIZE),
            "FORMAT": "image/png",
            "TRANSPARENT": "TRUE",
        }
        return self._cached(f"tile:{group.id}:{z}:{x}:{y}", params)

    def feature_info(
        self,
        lng: float,
        lat: float,
        zoom: float,
        group_ids: list[str],
    ) -> list[dict]:
        layers = [
            layer
            for group_id in group_ids
            if group_id in GROUPS_BY_ID
            for layer in GROUPS_BY_ID[group_id].layers
        ]
        if not layers:
            return []
        if not (-180 <= lng <= 180 and -85 <= lat <= 85):
            raise ValueError("Ungültige Koordinate.")

        # Ein Abfragefenster von etwa 10 Bildschirmpixeln um den Klickpunkt.
        zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
        degrees_per_pixel = 360 / (TILE_SIZE * 2 ** zoom)
        half_lng = 5 * degrees_per_pixel
        half_lat = half_lng * math.cos(math.radians(lat))
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetFeatureInfo",
            "LAYERS": ",".join(layers),
            "QUERY_LAYERS": ",".join(layers),
            "STYLES": "",
            "CRS": "EPSG:4326",
            # WMS 1.3.0 mit EPSG:4326 erwartet Breite vor Länge.
            "BBOX": (
                f"{lat - half_lat:.6f},{lng - half_lng:.6f},"
                f"{lat + half_lat:.6f},{lng + half_lng:.6f}"
            ),
            "WIDTH": "11",
            "HEIGHT": "11",
            "I": "5",
            "J": "5",
            "INFO_FORMAT": "text/plain",
            "FEATURE_COUNT": "20",
        }
        key = (
            f"info:{','.join(layers)}:{round(lng, 4)}:{round(lat, 4)}:"
            f"{round(zoom)}"
        )
        text = self._cached(key, params).decode("utf-8", errors="replace")
        return parse_feature_info(text)

    def _cached(self, key: str, params: dict[str, str]) -> bytes:
        now = self._clock()
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and now - entry[0] < self._cache_seconds:
                self._cache.move_to_end(key)
                return entry[1]

        with self._slots:
            data = self._fetch(params)

        with self._lock:
            self._cache[key] = (now, data)
            self._cache.move_to_end(key)
            while len(self._cache) > self._max_entries:
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
            raise DipulUnavailableError(
                f"dipul ist nicht erreichbar: {exc}"
            ) from exc

        # GeoServer meldet Fehler als XML mit Status 200.
        if "xml" in content_type:
            raise DipulUnavailableError(
                "dipul lieferte einen Fehler: "
                + data[:300].decode("utf-8", errors="replace")
            )
        return data
