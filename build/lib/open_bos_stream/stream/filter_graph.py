from open_bos_stream.overlay.command import OverlayCommand


class FilterGraphBuilder:
    """Builds FFmpeg filter arguments."""

    def build(
        self,
        encoder_filters: list[str],
        overlay_command: OverlayCommand,
        overlay_video_stream: str | None = None,
        audio_stream: str | None = None,
    ) -> list[str]:

        if overlay_command.inputs:
            return self._build_complex(
                encoder_filters=encoder_filters,
                overlay_command=overlay_command,
                overlay_video_stream=overlay_video_stream,
                audio_stream=audio_stream,
            )

        return self._build_simple(
            encoder_filters=encoder_filters,
            overlay_command=overlay_command,
        )

    def _build_simple(
        self,
        encoder_filters: list[str],
        overlay_command: OverlayCommand,
    ) -> list[str]:

        filters = [
            *encoder_filters,
            *overlay_command.filters,
        ]

        if not filters:
            return []

        return [
            "-vf",
            ",".join(filters),
        ]

    def _build_complex(
        self,
        encoder_filters: list[str],
        overlay_command: OverlayCommand,
        overlay_video_stream: str | None,
        audio_stream: str | None,
    ) -> list[str]:

        if overlay_video_stream is None:
            raise RuntimeError(
                "Overlay video stream not specified."
            )

        video = "[0:v]"

        if encoder_filters:
            graph = ",".join(encoder_filters)
            video = "[base]"

            filter_graph = [
                f"[0:v]{graph}{video}"
            ]
        else:
            filter_graph = []

        filter_graph.append(
            f"{video}[{overlay_video_stream}]"
            f"{overlay_command.overlay_filter}[v]"
        )

        command = [
            "-filter_complex",
            ";".join(filter_graph),
            "-map",
            "[v]",
        ]

        if audio_stream is not None:
            command.extend(
                [
                    "-map",
                    audio_stream,
                ]
            )

        return command