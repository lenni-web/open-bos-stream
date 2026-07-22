from .base import BaseOverlay
from .canvas import OverlayCanvas
from .command import OverlayCommand


class RendererOverlay(BaseOverlay):

    def build(self) -> OverlayCommand:

        canvas = OverlayCanvas()

        canvas.render()

        return OverlayCommand(
            inputs=[
                "-loop",
                "1",
                "-framerate",
                "4",
                "-f",
                "image2",
                "-i",
                str(canvas.path),
            ],
            overlay_filter="overlay=x=0:y=0",
        )