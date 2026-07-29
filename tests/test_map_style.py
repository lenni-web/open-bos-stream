from pathlib import Path

from open_bos_stream.map.service import MapService


class _Metadata:
    min_zoom = 0
    max_zoom = 14
    name = "Test map"
    attribution = None
    bounds = None
    center = None


def test_style_keeps_absolute_tile_url() -> None:
    service = object.__new__(MapService)
    service.metadata = lambda _name: _Metadata()

    style_path = (
        Path(__file__).parents[1]
        / "src"
        / "open_bos_stream"
        / "map"
        / "styles"
        / "basic.json"
    )
    # The service reads its packaged style; only metadata access needs
    # isolation from an actual MBTiles database for this regression test.
    assert style_path.is_file()
    style = service.style(
        tile_url=(
            "http://192.168.1.10:8000/"
            "api/map/niedersachsen/tiles/{z}/{x}/{y}"
        ),
        name="niedersachsen",
    )

    assert style["sources"]["openbos"]["tiles"] == [
        (
            "http://192.168.1.10:8000/"
            "api/map/niedersachsen/tiles/{z}/{x}/{y}"
        ),
    ]
