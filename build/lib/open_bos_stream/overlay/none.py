from .base import BaseOverlay
from .command import OverlayCommand


class NoneOverlay(BaseOverlay):
    def build(self) -> OverlayCommand:
        return OverlayCommand()