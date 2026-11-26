from abc import ABC, abstractmethod

from open_bos_stream.core.models import StreamAudioConfig

from .command import AudioCommand


class BaseAudio(ABC):

    def __init__(
        self,
        config: StreamAudioConfig,
    ) -> None:
        self._config = config

    @abstractmethod
    def build(self) -> AudioCommand:
        ...