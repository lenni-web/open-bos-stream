from .base import BaseOverlay
from .command import OverlayCommand


class ClockOverlay(BaseOverlay):
    def build(
        self,
    ) -> OverlayCommand:

        drawtext = (
            "drawtext="
            f"fontfile={self._config.font}:"
            "text='%{localtime\\:%Y-%m-%d %H\\\\\\:%M\\\\\\:%S}':"
            f"fontsize={self._config.size}:"
            f"fontcolor={self._config.color}:"
            f"x={self._config.x}:"
            f"y={self._config.y}"
        )

        return OverlayCommand(
            filters=[
                drawtext,
            ]
        )