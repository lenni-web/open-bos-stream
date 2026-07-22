from open_bos_stream.core.models import (
    StreamOutputAudioConfig,
)

from .base import BaseAudio
from .input import InputAudio
from .none import NoneAudio
from .silence import SilenceAudio


class AudioFactory:

    @staticmethod
    def create(
        config: StreamOutputAudioConfig,
    ) -> BaseAudio:

        match config.source:

            case "none":
                return NoneAudio(config)

            case "silence":
                return SilenceAudio(config)

            case "input":
                return InputAudio(config)

            case _:
                raise ValueError(
                    f"Unknown audio source: {config.source}"
                )