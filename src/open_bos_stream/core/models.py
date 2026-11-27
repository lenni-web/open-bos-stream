from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
import re
import secrets
from typing import Literal
from open_bos_stream.display.config import DisplayConfig
from open_bos_stream.web_access.config import WebAccessConfig

PUBLISH_TOKEN_LENGTH = 12
PUBLISH_TOKEN_ALPHABET = (
    "ABCDEFGHJKLMNPQRSTUVWXYZ"
    "abcdefghijkmnopqrstuvwxyz"
    "23456789"
)
# ---------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------

#
# Legacy
# Wird künftig durch SourceConfig ersetzt.
#
class CaptureConfig(BaseModel):
    device: str
    width: int
    height: int
    fps: int
    format: str

class InputConfig(BaseModel):
    type: str = "v4l2"
    
    mode: str = "transcode"
    
    device: str | None = "/dev/video0"
    url: str | None = None
    width: int = 1280
    height: int = 720
    fps: int = 25
    format: str = "v4l2"

SOURCE_URL_SCHEMES = {
    "rtsp": ("rtsp://", "rtsps://"),
    "srt": ("srt://",),
    "udp": ("udp://", "rtp://"),
    "http": ("http://", "https://"),
    "hls": ("http://", "https://"),
}

class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str = "Drohne"
    drone_type: str = Field(default="", max_length=100)
    type: str
    profile: Literal[
        "direct",
        "copy_repair",
        "copy_repair_low_latency",
        "preview_transcode",
        "preview_transcode_economy",
        "transcode",
        "transcode_low_latency",
    ] = "direct"
    enabled: bool = True
    priority: int = 0
    url: str | None = None
    preview_url: str | None = None
    device: str | None = "/dev/video0"
    width: int = 1280
    height: int = 720
    fps: int = 30
    format: str = "mjpeg"
    transport: Literal["tcp", "udp"] = "tcp"
    codec: str | None = None
    bitrate: str | None = None
    pixel_format: str | None = None
    gop: int | None = None
    preset: str | None = None
    tune: str | None = None
    audio_mode: Literal["none", "copy", "aac"] = "none"
    # Wehr, der die Quelle gehört (Organisation in der Datenbank). Ohne
    # Zuordnung ist die Quelle für alle angemeldeten Konten sichtbar.
    organization_id: int | None = None
    # Empfangsprotokoll für Quellen, die an den Server senden (type "rtmp"):
    # RTMP für Drohnen-Apps, SRT für geringe Latenz über Mobilfunk.
    ingest_protocol: Literal["rtmp", "srt"] = "rtmp"
    publish_token: str | None = Field(
        default=None,
        min_length=PUBLISH_TOKEN_LENGTH,
        max_length=PUBLISH_TOKEN_LENGTH,
        pattern=r"^[A-Za-z0-9_-]{12}$",
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", value):
            raise ValueError(
                "ID muss aus Kleinbuchstaben, Zahlen, '-' oder '_' bestehen."
            )
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Drohnenname darf nicht leer sein.")
        return value

    @field_validator("drone_type")
    @classmethod
    def normalize_drone_type(cls, value: str) -> str:
        return value.strip()

    @field_validator("preview_url", mode="before")
    @classmethod
    def normalize_preview_url(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("publish_token", mode="before")
    @classmethod
    def normalize_publish_token(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        # Migration der bisher längeren Tokens: Das Präfix bleibt erhalten,
        # damit die Umstellung vorhersehbar und einmalig ist.
        return normalized[:PUBLISH_TOKEN_LENGTH]

    @model_validator(mode="after")
    def validate_source(self) -> "SourceConfig":
        if self.type in {
            "rtsp",
            "srt",
            "udp",
            "http",
            "hls",
        }:
            if not self.url:
                raise ValueError(
                    f"Für die {self.type.upper()}-Quelle fehlt die URL."
                )
            # Nur Netzwerkprotokolle des jeweiligen Typs: FFmpeg würde sonst
            # auch file:, concat:, pipe: o. ä. öffnen (lokale Dateien).
            allowed = SOURCE_URL_SCHEMES[self.type]
            if not self.url.strip().lower().startswith(allowed):
                raise ValueError(
                    f"Die URL einer {self.type.upper()}-Quelle muss mit "
                    + " oder ".join(allowed)
                    + " beginnen."
                )
        if self.preview_url:
            if self.type != "rtsp":
                raise ValueError(
                    "Eine separate Vorschau-URL wird derzeit nur für "
                    "den RTSP-Abruf unterstützt."
                )
            if not self.preview_url.startswith("rtsp://"):
                raise ValueError(
                    "Die Vorschau-URL einer RTSP-Drohne muss mit "
                    "rtsp:// beginnen."
                )
        if self.type != "rtmp":
            self.ingest_protocol = "rtmp"
        if self.type == "rtmp":
            # Lokale RTMP-Publisher verwenden immer die unveränderliche ID.
            # Auch per SRT empfangene Streams liest der Server intern über
            # diesen Pfad; MediaMTX stellt jeden Pfad per RTMP bereit.
            self.url = f"rtmp://127.0.0.1:1935/{self.id}"
            if not self.publish_token:
                self.publish_token = "".join(
                    secrets.choice(PUBLISH_TOKEN_ALPHABET)
                    for _ in range(PUBLISH_TOKEN_LENGTH)
                )
        if self.is_preview_transcode and self.type != "rtmp":
            raise ValueError(
                "Das Übersichts-Vorschauprofil ist nur für "
                "den RTMP-Empfang verfügbar."
            )
        if self.type == "v4l2" and not self.device:
            raise ValueError("Für die Capture Card fehlt das Gerät.")
        return self

    @property
    def publish_path(self) -> str:
        return self.id

    @property
    def effective_url(self) -> str | None:
        """Für die Browserausgabe bevorzugte, ressourcenschonende URL."""

        return self.preview_url or self.url

    @property
    def viewer_path(self) -> str:
        if self.type == "rtmp" and self.profile == "direct":
            return self.id
        return f"{self.id}-view"

    @property
    def is_preview_transcode(self) -> bool:
        return self.profile in {
            "preview_transcode",
            "preview_transcode_economy",
        }

    @property
    def fullscreen_viewer_path(self) -> str:
        """Separater Hauptstream-Pfad bei konfigurierter RTSP-Vorschau."""

        if self.type == "rtmp" and self.is_preview_transcode:
            return self.publish_path
        if self.type == "rtsp" and self.preview_url:
            return f"{self.id}-main"
        return self.viewer_path

    @property
    def is_low_latency_transcode(self) -> bool:
        return self.profile == "transcode_low_latency"

    @property
    def requires_process(self) -> bool:
        return not (
            self.type == "rtmp"
            and self.profile == "direct"
        )

class RTMPInputConfig(BaseModel):
    """Ein individuell adressierbarer RTMP-Empfangs-Slot."""

    id: str
    name: str
    path: str
    viewer_path: str | None = None
    enabled: bool = True

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", value):
            raise ValueError(
                "ID muss aus Kleinbuchstaben, Zahlen, '-' oder '_' bestehen."
            )
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Drohnenname darf nicht leer sein.")
        return value

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        value = value.strip().strip("/")
        if not value or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_./-]{0,127}",
            value,
        ):
            raise ValueError(
                "RTMP-Pfad enthält ungültige Zeichen."
            )
        if ".." in value.split("/"):
            raise ValueError("RTMP-Pfad darf '..' nicht enthalten.")
        return value

    @field_validator("viewer_path")
    @classmethod
    def validate_viewer_path(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None or not value.strip():
            return None
        return cls.validate_path(value)

class OverlayConfig(BaseModel):
    source: str = "none"
    font: str = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    size: int = 24
    color: str = "white"
    x: str = "w-tw-20"
    y: str = "20"

class MapConfig(BaseModel):
    source: Literal[
        "mbtiles",
    ] = "mbtiles"

    path: str = (
        "/home/streampi/open-bos-stream/"
        "mapdata"
    )

    default: str | None = None

    # Online-Grundkarten (basemap.de, Luftbild Niedersachsen) über den
    # Server. Ohne Internetzugang, z. B. auf einem Pi vor Ort, ausschalten.
    online: bool = True

    # Grundkarte beim ersten Öffnen; jeder Browser merkt sich seine Wahl.
    base_map: Literal["online", "aerial", "offline"] = "online"

    # Dauerhafter Zwischenspeicher für Luftbilder; 0 schaltet ihn ab.
    aerial_cache_gb: float = Field(default=2.0, ge=0, le=500)
    aerial_cache_path: str = "cache/aerial"

class EncoderConfig(BaseModel):
    codec: str
    bitrate: str
    pixel_format: str
    gop: int = 30
    preset: str = "ultrafast"
    tune: str = "zerolatency"

class StreamAudioConfig(BaseModel):
    source: str = "none"
    device: str | None = None

class ViewerConfig(BaseModel):

    protocol: Literal[
        "webrtc",
        "hls",
    ] = "webrtc"

class StreamConfig(BaseModel):
    name: str
    rtsp_url: str
    passthrough: bool = False

    viewer: ViewerConfig = Field(
        default_factory=ViewerConfig,
    )

    audio: StreamAudioConfig = Field(
        default_factory=StreamAudioConfig,
    )

    overlay: OverlayConfig = Field(
        default_factory=OverlayConfig,
    )

class StreamOutputAudioConfig(BaseModel):

    source: Literal[
        "none",
        "silence",
        "input",
    ] = "none"

class StreamOutputConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["rtmp", "srt", "rtsp"] = "rtmp"

    name: str = Field(min_length=1, max_length=64)

    enabled: bool = True

    source_id: str | None = None

    url: str

    audio: StreamOutputAudioConfig = Field(
        default_factory=StreamOutputAudioConfig,
    )


class MediaCaptureConfig(BaseModel):
    """Superadmin-Auswahl für Snapshots und Aufzeichnungen.

    ``source_id`` ist die Medienquelle für Snapshot und manuelle Aufnahme.
    ``automatic_source_ids`` sind die Drohnen, die bei Eingangssignal
    selbstständig aufnehmen (ohne feste Obergrenze; die Serverlast wird
    überwacht).
    ``recording_mode`` stammt aus Versionen bis 0.18 und wird nur noch zur
    Übernahme älterer Konfigurationen ausgewertet.
    """

    source_id: str | None = None

    recording_mode: Literal["manual", "automatic"] = "manual"

    automatic_source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize_automatic_sources(self) -> "MediaCaptureConfig":
        ids = list(dict.fromkeys(
            item for item in self.automatic_source_ids if item
        ))
        if (
            not ids
            and self.recording_mode == "automatic"
            and self.source_id
        ):
            # Bis 0.18: Automatik galt für die gewählte Medienquelle.
            ids = [self.source_id]
        legacy_without_source = (
            not ids
            and self.recording_mode == "automatic"
            and not self.source_id
        )
        self.automatic_source_ids = ids
        # Ohne gewählte Quelle übernimmt AppConfig die Migration.
        self.recording_mode = (
            "automatic" if ids or legacy_without_source else "manual"
        )
        return self


class StorageConfig(BaseModel):
    """Schwellwerte für Speicherwarnung und automatische Bereinigung."""

    warning_free_percent: int = Field(default=15, ge=2, le=50)

    minimum_free_percent: int = Field(default=5, ge=1, le=40)

    auto_cleanup: bool = False

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.minimum_free_percent >= self.warning_free_percent:
            raise ValueError(
                "Die Mindestgrenze muss unter der Warnschwelle liegen."
            )
        return self


EMAIL_ADDRESS_PATTERN = re.compile(r"^[^@\s<>,;\"']+@[^@\s<>,;\"']+\.[^@\s<>,;\"']+$")


class NotificationEventsConfig(BaseModel):
    """Welche Störungen per E-Mail gemeldet werden."""

    source_offline: bool = True
    mediamtx_offline: bool = True
    storage_low: bool = True
    recording_problem: bool = True
    output_failed: bool = True
    server_load: bool = True
    server_started: bool = True


class NotificationConfig(BaseModel):
    """E-Mail-Benachrichtigung bei Störungen (Passwort separat gespeichert)."""

    enabled: bool = False
    smtp_host: str = Field(default="", max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    security: Literal["starttls", "ssl", "none"] = "starttls"
    username: str = Field(default="", max_length=255)
    sender: str = Field(default="", max_length=255)
    recipients: list[str] = Field(default_factory=list, max_length=10)
    events: NotificationEventsConfig = Field(
        default_factory=NotificationEventsConfig,
    )

    @field_validator("smtp_host", "username", "sender", mode="before")
    @classmethod
    def _strip_single_line(cls, value):
        text = str(value or "").strip()
        # Zeilenumbrüche würden zusätzliche Mail-Header einschleusen.
        if "\r" in text or "\n" in text:
            raise ValueError("Zeilenumbrüche sind nicht erlaubt.")
        return text

    @field_validator("recipients", mode="before")
    @classmethod
    def _normalize_recipients(cls, value):
        if isinstance(value, str):
            value = re.split(r"[,;\s]+", value)
        recipients = []
        for item in value or []:
            address = str(item).strip()
            if address and address not in recipients:
                recipients.append(address)
        return recipients

    @model_validator(mode="after")
    def _validate_addresses(self) -> "NotificationConfig":
        for address in [*self.recipients, *([self.sender] if self.sender else [])]:
            if not EMAIL_ADDRESS_PATTERN.match(address):
                raise ValueError(f"Ungültige E-Mail-Adresse: {address}")
        if self.enabled:
            if not self.smtp_host:
                raise ValueError("Für E-Mail-Benachrichtigungen fehlt der SMTP-Server.")
            if not self.sender:
                raise ValueError("Für E-Mail-Benachrichtigungen fehlt der Absender.")
            if not self.recipients:
                raise ValueError("Mindestens ein Empfänger ist erforderlich.")
        return self


class WeatherConfig(BaseModel):
    """Wetter, DWD-Warnungen und Grenzwerte für Drohnenflüge.

    Ohne eigenen Standort wird die Kartenmitte verwendet. Die Grenzwerte
    sind Vorgaben für die Ampel und ersetzen keine Herstellerangaben.
    """

    enabled: bool = True
    location_name: str = Field(default="", max_length=80)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    # Dauerwind in Flughöhe und Böen in m/s (z. B. Mavic 3T/M4T: 12 m/s).
    wind_limit_ms: float = Field(default=10.0, ge=2, le=30)
    gust_limit_ms: float = Field(default=12.0, ge=2, le=35)
    min_temperature_c: float = Field(default=-10.0, ge=-40, le=20)
    max_temperature_c: float = Field(default=40.0, ge=10, le=60)
    # Ab dieser Niederschlagsmenge rot; jeder Niederschlag darunter gelb.
    rain_limit_mm_h: float = Field(default=1.0, ge=0.1, le=50)
    visibility_min_m: int = Field(default=1000, ge=100, le=20000)

    @field_validator("location_name")
    @classmethod
    def normalize_location_name(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_weather(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(
                "Für den Standort Breite und Länge angeben oder beide leer lassen."
            )
        if self.min_temperature_c >= self.max_temperature_c:
            raise ValueError(
                "Die Mindesttemperatur muss unter der Höchsttemperatur liegen."
            )
        return self


class AppConfig(BaseModel):

    source_profile: Literal[
        "capture_card",
        "rtmp_passthrough",
        "rtmp_repair",
        "custom",
    ] | None = None

    display: DisplayConfig = Field(
        default_factory=DisplayConfig,
    )

    web_access: WebAccessConfig = Field(
        default_factory=WebAccessConfig,
    )

    media_capture: MediaCaptureConfig = Field(
        default_factory=MediaCaptureConfig,
    )

    storage: StorageConfig = Field(
        default_factory=StorageConfig,
    )

    notifications: NotificationConfig = Field(
        default_factory=NotificationConfig,
    )

    weather: WeatherConfig = Field(
        default_factory=WeatherConfig,
    )

    capture: CaptureConfig

    input: InputConfig = Field(
        default_factory=InputConfig,
    )

    # Keine feste Obergrenze: Die Serverlast wird stattdessen überwacht
    # (system/load.py) und bei hoher Auslastung ein Hinweis angezeigt.
    sources: list[SourceConfig] = Field(
        default_factory=list,
    )

    rtmp_inputs: list[RTMPInputConfig] = Field(
        default_factory=list,
    )

    encoder: EncoderConfig

    stream: StreamConfig

    map: MapConfig = Field(
        default_factory=MapConfig,
    )

    stream_outputs: list[
        StreamOutputConfig
    ] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def migrate_automatic_recording(self) -> "AppConfig":
        """Ältere Automatik ohne gewählte Quelle auf die erste Quelle legen."""

        capture = self.media_capture
        if (
            capture.recording_mode == "automatic"
            and not capture.automatic_source_ids
        ):
            first = next(
                (item.id for item in self.sources if item.enabled),
                None,
            )
            capture.automatic_source_ids = [first] if first else []
            capture.recording_mode = "automatic" if first else "manual"
        return self

    @model_validator(mode="after")
    def normalize_capture_card_mode(self) -> "AppConfig":
        """Bekannte Profile konsistent halten."""

        if self.source_profile is None:
            if self.input.type == "v4l2":
                self.source_profile = "capture_card"
            elif (
                self.input.type == "rtmp"
                and self.stream.passthrough
            ):
                self.source_profile = "rtmp_passthrough"
            elif (
                self.input.type == "rtmp"
                and self.input.mode == "copy_repair"
            ):
                self.source_profile = "rtmp_repair"
            else:
                self.source_profile = "custom"

        if (
            self.source_profile == "capture_card"
            or (
                self.source_profile == "custom"
                and self.input.type == "v4l2"
            )
        ):
            self.input.type = "v4l2"
            self.input.mode = "transcode"
            self.stream.passthrough = False

            if self.encoder.codec == "copy":
                self.encoder.codec = "h264_v4l2m2m"

            stream_name = (
                self.stream.name.rstrip("/").split("/")[-1]
                or "drohne"
            )
            self.stream.name = stream_name
            self.stream.rtsp_url = (
                f"rtsp://127.0.0.1:8554/{stream_name}"
            )

        elif self.source_profile == "rtmp_passthrough":
            self.input.type = "rtmp"
            self.input.mode = "copy"
            self.encoder.codec = "copy"
            self.stream.passthrough = True

            stream_name = self.stream.name.strip("/") or "live/drohne"
            if "/" not in stream_name:
                stream_name = f"live/{stream_name}"

            self.stream.name = stream_name
            self.input.url = (
                f"rtmp://127.0.0.1:1935/{stream_name}"
            )
            self.stream.rtsp_url = (
                f"rtsp://127.0.0.1:8554/{stream_name}"
            )

        elif self.source_profile == "rtmp_repair":
            self.input.type = "rtmp"
            self.input.mode = "copy_repair"
            self.encoder.codec = "copy"
            self.stream.passthrough = False
            self.stream.audio.source = "none"
            self.stream.audio.device = None
            self.stream.overlay.source = "none"

            output_name = (
                self.stream.name.rstrip("/").split("/")[-1]
                or "drohne"
            )
            self.stream.name = output_name
            self.stream.rtsp_url = (
                f"rtsp://127.0.0.1:8554/{output_name}"
            )

        return self

    @model_validator(mode="after")
    def validate_rtmp_inputs(self) -> "AppConfig":
        source_ids = [item.id for item in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Drohnen-IDs müssen eindeutig sein.")
        viewer_paths = [item.viewer_path for item in self.sources]
        if len(viewer_paths) != len(set(viewer_paths)):
            raise ValueError(
                "Wiedergabepfade der Drohnen müssen eindeutig sein."
            )

        # Übergangsweise folgen Einzelstream-Verbraucher wie Diagnose,
        # Snapshot und Streaming-Ausgänge der ersten aktivierten Quelle.
        if self.sources:
            primary = next(
                (
                    source
                    for source in self.sources
                    if source.enabled
                ),
                self.sources[0],
            )
            self.input.type = primary.type
            self.input.mode = (
                primary.profile
                if primary.profile in {
                    "copy_repair",
                    "copy_repair_low_latency",
                }
                else (
                    "transcode"
                    if primary.profile in {
                        "transcode",
                        "transcode_low_latency",
                    }
                    else "copy"
                )
            )
            self.input.url = primary.url
            self.input.device = primary.device
            self.input.width = primary.width
            self.input.height = primary.height
            self.input.fps = primary.fps
            self.input.format = primary.format
            self.stream.name = primary.viewer_path
            self.stream.rtsp_url = (
                f"rtsp://127.0.0.1:8554/{primary.viewer_path}"
            )
            self.stream.passthrough = not primary.requires_process

            source_ids_set = set(source_ids)
            for output in self.stream_outputs:
                # Rückwärtskompatibilität: Vor 0.11.12 verwendeten alle
                # Ausgänge implizit die erste aktivierte Quelle.
                if output.source_id is None:
                    output.source_id = primary.id
                elif output.source_id not in source_ids_set:
                    # Wird eine bislang gewählte Quelle entfernt, bleibt die
                    # Gesamtkonfiguration speicherbar und der Ausgang fällt
                    # nachvollziehbar auf die neue Primärquelle zurück.
                    output.source_id = primary.id

        ids = [item.id for item in self.rtmp_inputs]
        paths = [item.path for item in self.rtmp_inputs]
        if len(ids) != len(set(ids)):
            raise ValueError("RTMP-Eingangs-IDs müssen eindeutig sein.")
        if len(paths) != len(set(paths)):
            raise ValueError("RTMP-Eingangspfade müssen eindeutig sein.")
        viewer_paths = [
            item.viewer_path or item.path
            for item in self.rtmp_inputs
        ]
        if len(viewer_paths) != len(set(viewer_paths)):
            raise ValueError(
                "RTMP-Wiedergabepfade müssen eindeutig sein."
            )
        return self

    def stream_output_source(
        self,
        output: StreamOutputConfig,
    ) -> SourceConfig | None:
        """Die explizit für einen Streaming-Ausgang gewählte Quelle."""

        return next(
            (
                source
                for source in self.sources
                if source.id == output.source_id
            ),
            None,
        )

    @property
    def passthrough_active(self) -> bool:
        """True, wenn MediaMTX ohne internen FFmpeg-Relay genutzt wird."""

        source_type = self.input.type

        for source in self.sources:
            if source.enabled:
                source_type = source.type
                break

        return (
            self.stream.passthrough
            and self.encoder.codec == "copy"
            and source_type in {
                "rtmp",
                "rtsp",
                "srt",
                "udp",
                "http",
                "hls",
            }
        )
# ---------------------------------------------------------
# Statusmodelle
# ---------------------------------------------------------

class ComponentStatus(BaseModel):
    name: str
    online: bool


class StreamStatus(BaseModel):
    running: bool
    pid: int | None = None


class SystemStatus(BaseModel):
    cpu: float = 0
    ram: float = 0
    temperature: float | None = None


class MediaMTXStatus(BaseModel):
    online: bool
    publisher: bool

    path: str | None = None

    readers: int = 0

    ready: bool = False

    source: str | None = None

    tracks: int = 0

    codec: str | None = None

    width: int = 0

    height: int = 0

    bytes_received: int = 0

    bytes_sent: int = 0

    online_time: str | None = None

# ---------------------------------------------------------
# Streaminformationen
# ---------------------------------------------------------

class StreamInfo(BaseModel):
    online: bool
    protocol: str = "offline"
    viewers: int = 0
    recording: bool = False


class HealthStatus(BaseModel):
    capture: ComponentStatus
    ffmpeg: ComponentStatus
    mediamtx: MediaMTXStatus
    stream: StreamStatus
    system: SystemStatus

# ---------------------------------------------------------
# System Info
# ---------------------------------------------------------

class NetworkInfo(BaseModel):
    hostname: str
    interface: str
    ipv4: str
    mac: str

class ApplicationInfo(BaseModel):
    name: str
    version: str


class HardwareInfo(BaseModel):
    model: str
    architecture: str


class OperatingSystemInfo(BaseModel):
    system: str
    distribution: str
    kernel: str

class RuntimeInfo(BaseModel):
    python: str
    ffmpeg: str
    mediamtx: str = "Unknown"


class SystemInfo(BaseModel):
    application: ApplicationInfo
    hardware: HardwareInfo
    operating_system: OperatingSystemInfo
    runtime: RuntimeInfo
    network: NetworkInfo
