"""
FFmpeg command builder.

Erzeugt den FFmpeg-Befehl aus der Projektkonfiguration.
Diese Klasse startet keine Prozesse.
"""

from __future__ import annotations

from open_bos_stream.core.models import (
    AppConfig,
    SourceConfig,

)

from open_bos_stream.overlay.factory import OverlayFactory
from open_bos_stream.overlay.command import OverlayCommand
from open_bos_stream.stream.audio.factory import AudioFactory

from open_bos_stream.stream.input_factory import (
    InputFactory,
)

from open_bos_stream.stream.encoder.factory import (
    EncoderFactory,
)
from .filter_graph import FilterGraphBuilder

class FFmpegCommandBuilder:
    """Erzeugt einen FFmpeg-Aufruf aus der App-Konfiguration."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def _build_input(
        self,
        source: SourceConfig,
    ) -> list[str]:

        builder = InputFactory.create(
            source,
        )

        builder.validate(
            source,
        )

        return builder.build(
            source,
        )

    def build(
        self,
        recording_file: str | None = None,
        source_override: SourceConfig | None = None,
    ) -> list[str]:

        if source_override is None:
            source = SourceConfig(
                id="legacy",
                name="Legacy-Quelle",
                profile=(
                    "copy_repair"
                    if self._config.input.mode == "copy_repair"
                    else (
                        "direct"
                        if self._config.encoder.codec == "copy"
                        else "transcode"
                    )
                ),
                **self._config.input.model_dump(),
            )
            # Im Kompatibilitätsmodus muss die bisher konfigurierte URL
            # erhalten bleiben; RTMP-IDs werden nur im neuen Quellenmodell
            # automatisch auf den lokalen Empfangspfad abgebildet.
            if self._config.input.type == "rtmp":
                source.url = self._config.input.url
        else:
            source = source_override

        if source is None:
            raise RuntimeError(
                "No active source configured."
            )

        encoder = self._config.encoder.model_copy(deep=True)
        stream = self._config.stream.model_copy(deep=True)

        if source_override is not None:
            if source.profile in {"direct", "copy_repair"}:
                encoder.codec = "copy"
            elif source.codec:
                encoder.codec = source.codec

            stream.name = source.viewer_path
            stream.rtsp_url = (
                f"rtsp://127.0.0.1:8554/{source.viewer_path}"
            )

        print("========================================")
        print("Open BOS Stream")
        print(f"Input Type : {source.type}")

        if source.type == "v4l2":
            print(f"Device     : {source.device}")
        else:
            print("URL        : konfiguriert")

        print(f"Codec      : {encoder.codec}")
        print(f"Output     : {stream.rtsp_url}")
        print("========================================")

        audio = AudioFactory.create(
            self._config.stream.audio,
        )

        audio_command = audio.build()

        if encoder.codec == "copy":
            overlay_command = OverlayCommand()
        else:
            overlay = OverlayFactory.create(
                self._config.stream.overlay,
            )
            overlay_command = overlay.build()
        overlay_video_stream: str | None = None
        audio_stream: str | None = None

        command: list[str] = [
            "ffmpeg",
        ]

        #
        # Video input
        #
        command.extend(
            self._build_input(
                source,
            )
        )

        #
        # Audio inputs
        #
        command.extend(
            audio_command.inputs,
        )

        #
        # Overlay inputs
        #
        if audio_command.inputs:
            audio_stream = "1:a"

        if overlay_command.inputs:
            overlay_input_index = command.count("-i")

            overlay_video_stream = (
                f"{overlay_input_index}:v"
            )

            command.extend(
                overlay_command.inputs,
            )

        encoder_builder = EncoderFactory.create(encoder)

        #
        # Encoder arguments
        #
        command.extend(
            encoder_builder.build_args(),
        )

        if encoder.codec == "copy":
            command.extend([
                "-map",
                "0:v:0",
            ])
            if getattr(source, "audio_mode", "copy") != "none":
                command.extend([
                    "-map", "0:a:0?",
                    "-c:a", (
                        "copy"
                        if source.audio_mode == "copy"
                        else "aac"
                    ),
                ])

        if getattr(source, "profile", None) == "copy_repair":
            command.extend([
                "-fps_mode",
                "passthrough",
                "-avoid_negative_ts",
                "make_zero",
                "-max_interleave_delta",
                "100000",
                "-flush_packets",
                "1",
                "-muxdelay",
                "0",
            ])

        #
        # Video filters and overlay
        #
        graph_builder = FilterGraphBuilder()

        if encoder.codec != "copy":
            command.extend(
                graph_builder.build(
                    encoder_filters=encoder_builder.build_filters(),
                    overlay_command=overlay_command,
                    overlay_video_stream=overlay_video_stream,
                    audio_stream=audio_stream,
                )
            )

            if getattr(source, "audio_mode", "copy") != "none":
                command.extend([
                    "-map", "0:a:0?",
                    "-c:a", (
                        "copy"
                        if source.audio_mode == "copy"
                        else "aac"
                    ),
                ])

        #
        # Audio options
        #
        command.extend(
            audio_command.options,
        )

        #
        # RTSP output
        #
        command.extend(
            [
                "-rtsp_transport",
                "tcp",
                "-f",
                "rtsp",
                stream.rtsp_url,
            ]
        )

        #
        # Optional recording
        #
        if recording_file:
            command.extend(
                [
                    "-f",
                    "mp4",
                    recording_file,
                ]
            )

        return command

    def build_source(self, source: SourceConfig) -> list[str]:
        """Erzeugt den unabhängigen FFmpeg-Befehl einer Quelle."""

        runtime_source = source.model_copy(deep=True)
        runtime_source.mode = (
            "copy_repair"
            if source.profile == "copy_repair"
            else "copy"
        )
        return self.build(source_override=runtime_source)
