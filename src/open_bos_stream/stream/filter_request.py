from dataclasses import dataclass

from open_bos_stream.overlay.command import OverlayCommand


@dataclass(slots=True)
class FilterGraphRequest:
    encoder_filters: list[str]
    overlay: OverlayCommand

    overlay_video_stream: str | None = None
    audio_stream: str | None = None