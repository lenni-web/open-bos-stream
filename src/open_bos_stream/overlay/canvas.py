from pathlib import Path

from PIL import Image


class OverlayCanvas:

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        path: str = "/run/open-bos-stream/overlay.png",
    ) -> None:

        self._width = width
        self._height = height
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def ensure_directory(self) -> None:
        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def render(self) -> None:

        self.ensure_directory()

        image = Image.new(
            "RGBA",
            (
                self._width,
                self._height,
            ),
            (0, 0, 0, 0),
        )

        image.save(self._path)