from pathlib import Path

import open_bos_stream


def test_runtime_map_resources_are_packaged() -> None:
    package_root = Path(open_bos_stream.__file__).parent

    assert (
        package_root / "map" / "styles" / "basic.json"
    ).is_file()
    assert (
        package_root / "map" / "layers" / "hydranten.geojson"
    ).is_file()
    assert (
        package_root
        / "map"
        / "glyphs"
        / "open-sans-regular"
        / "0-255.pbf"
    ).is_file()
    assert (
        package_root / "static" / "css" / "modern.css"
    ).is_file()
