from open_bos_stream.core.models import StreamAudioConfig

from .alsa import AlsaAudio
from .base import BaseAudio
from .none import NoneAudio


class AudioFactory:

    @staticmethod
    def create(
        config: StreamAudioConfig,
    ) -> BaseAudio:

        match config.source:

            case "none":
                return NoneAudio(config)

            case "alsa":
                return AlsaAudio(config)

            case _:
                raise ValueError(
                    f"Unknown audio source: {config.source}"
                )