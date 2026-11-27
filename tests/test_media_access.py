from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from open_bos_stream.auth.media_access import (
    media_access,
    media_source_id,
    require_media_access,
    visible_media,
)
from tests.test_organizations import auth, build, session, source  # noqa: F401


def item(name: str) -> dict:
    return {"type": "recording" if name.endswith(".mp4") else "snapshot",
            "name": name, "size": 1, "modified": 0, "protected": False}


@pytest.fixture
def setup(auth):  # noqa: F811
    ids = build(auth)
    config = SimpleNamespace(sources=[source("drohne-b", ids["b"]), source("drohne-a", ids["a"])])
    return SimpleNamespace(auth=auth, ids=ids, config=config)


def test_source_id_is_read_from_the_filename() -> None:
    assert media_source_id("recording_drohne-b_20261127_101500.mp4") == "drohne-b"
    assert media_source_id("snapshot_quelle_1_20261127_101500.jpg") == "quelle_1"
    assert media_source_id("irgendwas.mp4") is None


def test_wehr_sees_only_its_own_recordings(setup) -> None:
    files = [
        item("recording_drohne-b_20261127_101500.mp4"),
        item("snapshot_drohne-a_20261127_101600.jpg"),
        item("recording_entfernt_20261127_101700.mp4"),
    ]
    team_b = session(setup.auth, "b-team")
    visible = visible_media(team_b, files, setup.config)
    assert [entry["name"] for entry in visible] == ["recording_drohne-b_20261127_101500.mp4"]
    assert visible[0]["source_name"] == "Drohne drohne-b" and visible[0]["can_delete"] is False

    # Zuschauer haben keinen Zugriff auf das Archiv.
    assert media_access(session(setup.auth, "b-zuschauer"), files[0]["name"], setup.config) is None
    # Wehr-Admin (übergeordnet) darf löschen.
    assert media_access(session(setup.auth, "sg-admin"), files[1]["name"], setup.config) == "admin"
    # Kreis-Admin sieht alles, auch Dateien entfernter Quellen.
    assert len(visible_media(session(setup.auth, "kreis"), files, setup.config)) == 3


def test_require_media_access_levels(setup) -> None:
    team_b = session(setup.auth, "b-team")
    name = "recording_drohne-b_20261127_101500.mp4"
    require_media_access(team_b, name, setup.config)
    with pytest.raises(HTTPException) as denied:
        require_media_access(team_b, name, setup.config, level="admin")
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as hidden:
        require_media_access(team_b, "recording_drohne-a_20261127_101500.mp4", setup.config)
    assert hidden.value.status_code == 404


def test_unassigned_sources_are_visible_but_only_server_admins_operate(setup) -> None:  # noqa: F811
    from open_bos_stream.auth.guest_access import can_operate_source, can_see_source

    unassigned = source("ohne-wehr", None)
    team = session(setup.auth, "b-team")
    assert can_see_source(team, unassigned)
    assert not can_operate_source(team, unassigned)
    assert media_access(team, "recording_ohne-wehr_20261127_101500.mp4", setup.config) is None
    assert can_operate_source(session(setup.auth, "kreis"), unassigned)


def test_media_buttons_carry_names_as_data_not_code() -> None:
    from pathlib import Path

    root = Path(__file__).parents[1] / "src" / "open_bos_stream" / "static" / "js"
    for name in ("media.js", "media_library.js", "library.js", "snapshot_library.js"):
        script = (root / name).read_text(encoding="utf-8")
        assert "('${file.name}')" not in script, name
        assert "onclick=\"${" not in script, name
    assert 'data-media-name="${escapeHTML(file.name)}"' in (root / "media.js").read_text(encoding="utf-8")
