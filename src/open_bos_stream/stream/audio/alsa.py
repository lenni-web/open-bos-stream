from open_bos_stream.stream.exceptions import ConfigurationError

from .base import BaseAudio
from .command import AudioCommand


class AlsaAudio(BaseAudio):
    """Audio input from an ALSA capture device."""

    def build(self) -> AudioCommand:
        if not self._config.device:
            raise ConfigurationError(
                "Audio source 'alsa' requires a device."
            )

        return AudioCommand(
            inputs=[
                "-thread_queue_size",
                "512",
                "-f",
                "alsa",
                "-i",
                self._config.device,
            ],
            options=[
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "48000",
                "-ac",
                "2",
            ],
        )