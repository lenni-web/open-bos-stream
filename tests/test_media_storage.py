from open_bos_stream.media.storage import MediaStorageService


def test_media_storage_reports_counts_and_sizes(tmp_path) -> None:
    recordings = tmp_path / "recordings"
    snapshots = tmp_path / "snapshots"
    recordings.mkdir()
    snapshots.mkdir()
    (recordings / "one.mp4").write_bytes(b"video")
    (snapshots / "one.jpg").write_bytes(b"image")
    (snapshots / "two.jpg").write_bytes(b"other")

    status = MediaStorageService(
        str(recordings),
        str(snapshots),
    ).status()

    assert status["recordings"] == 1
    assert status["snapshots"] == 2
    assert status["media_bytes"] == 15
    assert status["free_bytes"] > 0
    assert 0 <= status["used_percent"] <= 100


import os
from collections import namedtuple
from types import SimpleNamespace

import pytest

from open_bos_stream.core.models import StorageConfig
from open_bos_stream.media.storage import StorageFullError
from open_bos_stream.recording.library import RecordingLibrary
from open_bos_stream.snapshot.library import SnapshotLibrary


Usage = namedtuple("Usage", "total used free")


def media_setup(tmp_path, *, total: int, auto_cleanup: bool):
    """Speicher, dessen Belegung genau den Mediendateien entspricht."""

    recordings = tmp_path / "recordings"
    snapshots = tmp_path / "snapshots"
    recordings.mkdir()
    snapshots.mkdir()

    def disk_usage(_path):
        used = sum(
            item.stat().st_size
            for directory in (recordings, snapshots)
            for item in directory.iterdir()
            if item.is_file()
        )
        return Usage(total, used, total - used)

    config = SimpleNamespace(
        storage=StorageConfig(
            warning_free_percent=20,
            minimum_free_percent=10,
            auto_cleanup=auto_cleanup,
        )
    )
    service = MediaStorageService(
        str(recordings),
        str(snapshots),
        config=config,
        recording_library=RecordingLibrary(str(recordings)),
        snapshot_library=SnapshotLibrary(str(snapshots)),
        disk_usage=disk_usage,
    )
    return service, recordings, snapshots


def write_media(path, size: int, modified: float) -> None:
    path.write_bytes(b"x" * size)
    os.utime(path, (modified, modified))


def test_cleanup_deletes_oldest_unprotected_media_first(tmp_path) -> None:
    service, recordings, snapshots = media_setup(
        tmp_path,
        total=1000,
        auto_cleanup=True,
    )
    write_media(recordings / "alt.mp4", 300, 100)
    write_media(snapshots / "mittel.jpg", 300, 200)
    write_media(recordings / "geschuetzt.mp4", 50, 50)
    write_media(recordings / "neu.mp4", 300, 300)
    service._recording_library.set_protected("geschuetzt.mp4", True)

    # 950 von 1000 Bytes belegt: 5 % frei, Mindestgrenze 10 %.
    assert service.level() == "critical"

    deleted = service.cleanup()

    # Ziel: Mindestgrenze + 2 Prozentpunkte = 12 % frei.
    assert deleted == ["alt.mp4"]
    assert (recordings / "geschuetzt.mp4").exists()
    assert (recordings / "neu.mp4").exists()
    assert service.free_percent() >= 12
    assert service.status()["last_cleanup"]["deleted"] == 1


def test_protected_media_is_never_cleaned_up(tmp_path) -> None:
    service, recordings, _snapshots = media_setup(
        tmp_path,
        total=1000,
        auto_cleanup=True,
    )
    write_media(recordings / "einsatz.mp4", 950, 100)
    service._recording_library.set_protected("einsatz.mp4", True)

    with pytest.raises(StorageFullError) as error:
        service.ensure_capacity()

    assert (recordings / "einsatz.mp4").exists()
    assert "Behalten" in str(error.value)
    assert service.enforce() is False


def test_without_auto_cleanup_new_media_is_blocked(tmp_path) -> None:
    service, recordings, _snapshots = media_setup(
        tmp_path,
        total=1000,
        auto_cleanup=False,
    )
    write_media(recordings / "alt.mp4", 950, 100)

    with pytest.raises(StorageFullError):
        service.ensure_capacity()

    status = service.status()
    assert (recordings / "alt.mp4").exists()
    assert status["blocked"] is True
    assert status["level"] == "critical"
    assert "automatische Bereinigung" in status["blocked_message"]


def test_storage_warning_level_does_not_block(tmp_path) -> None:
    service, recordings, _snapshots = media_setup(
        tmp_path,
        total=1000,
        auto_cleanup=False,
    )
    write_media(recordings / "alt.mp4", 850, 100)

    service.ensure_capacity()

    assert service.status()["level"] == "warning"
    assert service.enforce() is True


def test_protection_marker_is_listed_and_removed_with_file(tmp_path) -> None:
    library = RecordingLibrary(str(tmp_path))
    write_media(tmp_path / "aufnahme.mp4", 10, 100)

    assert library.set_protected("aufnahme.mp4", True)
    assert library.list()[0]["protected"] is True
    assert not library.set_protected("../fremd.mp4", True)

    library.delete("aufnahme.mp4")

    assert list(tmp_path.iterdir()) == []


def test_storage_thresholds_are_validated() -> None:
    with pytest.raises(ValueError):
        StorageConfig(warning_free_percent=5, minimum_free_percent=5)



from open_bos_stream.recording.playback import RecordingPlaybackCache


def cache_setup(tmp_path, *, total: int, auto_cleanup: bool):
    service, recordings, snapshots = media_setup(
        tmp_path,
        total=total,
        auto_cleanup=auto_cleanup,
    )
    cache = RecordingPlaybackCache(recordings)
    cache_dir = recordings / ".playback-cache"
    cache_dir.mkdir()
    service._playback_cache = cache

    original = service._disk_usage

    def disk_usage(path):
        usage = original(path)
        cached = sum(item.stat().st_size for item in cache_dir.iterdir())
        return Usage(total, usage.used + cached, usage.free - cached)

    service._disk_usage = disk_usage
    return service, recordings, cache_dir


def test_playback_cache_is_reported_in_status(tmp_path) -> None:
    service, _recordings, cache_dir = cache_setup(
        tmp_path,
        total=1000,
        auto_cleanup=False,
    )
    write_media(cache_dir / "a-1-1.mp4", 40, 100)

    status = service.status()

    assert status["playback_cache_files"] == 1
    assert status["playback_cache_bytes"] == 40
    assert status["recordings"] == 0


def test_playback_cache_is_cleared_before_blocking_or_deleting_media(
    tmp_path,
) -> None:
    service, recordings, cache_dir = cache_setup(
        tmp_path,
        total=1000,
        auto_cleanup=False,
    )
    write_media(recordings / "einsatz.mp4", 500, 100)
    write_media(cache_dir / "alt-1-1.mp4", 300, 100)
    write_media(cache_dir / "neu-1-1.mp4", 150, 200)

    # 950 von 1000 Bytes belegt; ohne Cache wären 50 % frei.
    service.ensure_capacity()

    assert (recordings / "einsatz.mp4").exists()
    assert not (cache_dir / "alt-1-1.mp4").exists()
    assert service.free_percent() >= 12


def test_unused_playback_copies_expire(tmp_path) -> None:
    service, _recordings, cache_dir = cache_setup(
        tmp_path,
        total=10_000,
        auto_cleanup=False,
    )
    now = __import__("time").time()
    write_media(cache_dir / "alt-1-1.mp4", 10, now - 8 * 24 * 3600)
    write_media(cache_dir / "frisch-1-1.mp4", 10, now - 3600)

    removed = service.prune_playback_cache(force=True)

    assert removed == 1
    assert not (cache_dir / "alt-1-1.mp4").exists()
    assert (cache_dir / "frisch-1-1.mp4").exists()
