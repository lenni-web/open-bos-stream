from abc import ABC, abstractmethod

from open_bos_stream.core.models import OverlayConfig

from .command import OverlayCommand


class BaseOverlay(ABC):
    def __init__(self, config: OverlayConfig):
        self._config = config

    @abstractmethod
    def build(self) -> OverlayCommand:
        pass