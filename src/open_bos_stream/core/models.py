from pydantic import (
    BaseModel,
    Field,
)
from typing import Literal
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

class SourceConfig(BaseModel):

    #
    # Eindeutige ID der Quelle
    #
    id: str

    #
    # Quelltyp
    #
    type: str

    #
    # Aktiviert?
    #
    enabled: bool = True

    priority: int = 0

    class Config:

        extra = "allow"

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

    type: str = Field(
        default="rtmp",
    )

    name: str

    enabled: bool = True

    url: str

    audio: StreamOutputAudioConfig = Field(
        default_factory=StreamOutputAudioConfig,
    )

    class Config:

        extra = "allow"

class AppConfig(BaseModel):

    capture: CaptureConfig

    input: InputConfig = Field(
        default_factory=InputConfig,
    )

    sources: list[
            SourceConfig
        ] = Field(
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
    temperature: float = 0


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


class SystemInfo(BaseModel):
    application: ApplicationInfo
    hardware: HardwareInfo
    operating_system: OperatingSystemInfo
    runtime: RuntimeInfo
    network: NetworkInfo
