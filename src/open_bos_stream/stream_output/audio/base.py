from abc import ABC, abstractmethod

from open_bos_stream.core.models import (
    StreamOutputAudioConfig,
)

from .command import AudioCommand


class BaseAudio(ABC):
    """Base class for all stream output audio plugins."""

    def __init__(
        self,
        config: StreamOutputAudioConfig,
    ) -> None:

        self._config = config

    @abstractmethod
    def build(self) -> AudioCommand:
        """Build the FFmpeg command fragments."""
        ...