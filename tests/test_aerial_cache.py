from __future__ import annotations

from pathlib import Path

import pytest

from open_bos_stream.map.basemaps import (
    AERIAL_FAILURE_LIMIT,
    AERIAL_FRESH_SECONDS,
    AERIAL_NOTICE_SECONDS,
    AERIAL_PAUSE_SECONDS,
    BasemapService,
    BasemapUnavailableError,
)
from open_bos_stream.map.tile_cache import TileDiskCache
from tests.test_basemaps import png


ROOT = Path(__file__).resolve().parents[1]
TILE = (16, 34492, 21166)


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


class Upstream:
    def __init__(self) -> None:
        self.calls = 0
        self.down = False

    def __call__(self, url: str):
        self.calls += 1
        if self.down:
            raise BasemapUnavailableError("HTTP 503")
        return png(), "image/png"


def build(tmp_path: Path, clock: Clock, upstream: Upstream, **options) -> BasemapService:
    cache = TileDiskCache(tmp_path / "aerial", 10 ** 7, min_free_bytes=0, clock=clock, **options)
    return BasemapService(fetch=upstream, clock=clock, aerial_cache=cache)


def test_tiles_survive_a_restart_and_are_fresh_for_30_days(tmp_path) -> None:
    clock, upstream = Clock(), Upstream()
    first = build(tmp_path, clock, upstream).aerial_tile(*TILE)

    clock.now += AERIAL_FRESH_SECONDS - 60
    assert build(tmp_path, clock, upstream).aerial_tile(*TILE) == first
    assert upstream.calls == 1

    clock.now += 120
    build(tmp_path, clock, upstream).aerial_tile(*TILE)
    assert upstream.calls == 2


def test_old_tiles_are_served_while_the_service_is_down(tmp_path) -> None:
    clock, upstream = Clock(), Upstream()
    service = build(tmp_path, clock, upstream)
    stored = service.aerial_tile(*TILE)

    clock.now += AERIAL_FRESH_SECONDS * 4
    upstream.down = True
    assert service.aerial_tile(*TILE) == stored


def test_repeated_failures_pause_requests_and_show_a_notice(tmp_path) -> None:
    clock, upstream = Clock(), Upstream()
    upstream.down = True
    service = build(tmp_path, clock, upstream)

    for offset in range(AERIAL_FAILURE_LIMIT - 1):
        with pytest.raises(BasemapUnavailableError):
            service.aerial_tile(16, 34000 + offset, 21166)
    assert service.aerial_available()

    for offset in range(5):
        with pytest.raises(BasemapUnavailableError):
            service.aerial_tile(16, 34100 + offset, 21166)
    assert upstream.calls == AERIAL_FAILURE_LIMIT
    assert not service.aerial_available()
    assert not list((tmp_path / "aerial").rglob("*.webp")), "Fehler nie speichern"

    clock.now += AERIAL_PAUSE_SECONDS
    upstream.down = False
    service.aerial_tile(*TILE)
    assert service.aerial_available()


def test_notice_expires_without_new_requests(tmp_path) -> None:
    clock, upstream = Clock(), Upstream()
    upstream.down = True
    service = build(tmp_path, clock, upstream)
    for offset in range(AERIAL_FAILURE_LIMIT):
        with pytest.raises(BasemapUnavailableError):
            service.aerial_tile(16, 34000 + offset, 21166)

    clock.now += AERIAL_NOTICE_SECONDS
    assert service.aerial_available()


def test_least_recently_used_tiles_are_removed_first(tmp_path) -> None:
    clock = Clock()
    cache = TileDiskCache(tmp_path, 3500, min_free_bytes=0, clock=clock)
    for x in range(3):
        clock.now += 10
        cache.put(16, x, 0, b"k" * 1000)
    clock.now += 10
    assert cache.get(16, 0, 0)

    clock.now += 10
    cache.put(16, 3, 0, b"k" * 1000)

    assert cache.get(16, 1, 0) is None
    assert all(cache.get(16, x, 0) for x in (0, 2, 3))
    assert not list(tmp_path.rglob("*.tmp"))


def test_nothing_is_stored_when_the_disk_is_nearly_full(tmp_path) -> None:
    cache = TileDiskCache(tmp_path, 10 ** 6, min_free_bytes=10 ** 18)
    cache.put(16, 1, 1, b"kachel")
    assert cache.get(16, 1, 1) is None


def test_unwritable_cache_still_delivers_tiles(tmp_path) -> None:
    blocker = tmp_path / "datei"
    blocker.write_text("kein Ordner")
    service = BasemapService(
        fetch=Upstream(),
        aerial_cache=TileDiskCache(blocker / "aerial", 10 ** 6, min_free_bytes=0),
    )
    assert service.aerial_tile(*TILE)[:4] == b"RIFF"


def test_server_scripts_keep_the_cache_folder() -> None:
    deploy = (ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")
    runtime = (ROOT / "scripts" / "initialize-runtime.sh").read_text(encoding="utf-8")
    assert '--exclude "/cache/"' in deploy
    assert '"${TARGET_DIR}/cache"' in runtime


def test_map_leaves_room_for_the_fields_below() -> None:
    static = ROOT / "src" / "open_bos_stream" / "static" / "css"
    css = (static / "weather.css").read_text(encoding="utf-8")
    # Zwischen Karte und Wetterfeld steht der Hinweis, daher "~" statt "+".
    assert ".map-wrapper:has(~ .map-weather-chip:not([hidden]))" in css
    assert ".map-aerial-notice:not([hidden])" in css
