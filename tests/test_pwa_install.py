from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "src" / "open_bos_stream"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_install_entry_and_hint_are_wired_into_the_app() -> None:
    header = read("templates/components/header.html")
    index = read("templates/index.html")
    dialog = read("templates/components/pwa_install.html")

    assert 'id="pwa-menu-entry"' in header
    assert 'onclick="openInstallDialog()"' in header
    assert '{% include "components/pwa_install.html" %}' in index
    assert '/static/js/pwa.js' in index
    # Hinweis steht oben auf der Übersicht, vor den Livebildern.
    assert index.index('id="pwa-install-hint"') < index.index(
        '{% include "components/multi_source_panel.html" %}'
    )
    for platform in ("ios", "android", "desktop"):
        assert f'data-platform="{platform}"' in dialog
    assert "Zum Home-Bildschirm" in dialog


def test_guest_view_has_no_install_hint() -> None:
    guest = read("templates/guest.html")

    assert "pwa" not in guest


def test_hint_only_for_mobile_and_not_installed() -> None:
    script = read("static/js/pwa.js")

    assert '"(display-mode: standalone)"' in script
    assert "navigator.standalone === true" in script
    assert 'detectPlatform() === "desktop"' in script
    assert '"beforeinstallprompt"' in script
    assert "event.preventDefault()" in script
    assert '"appinstalled"' in script
    # Speicherzugriffe sind abgesichert (privater Modus).
    assert script.count("try {") >= 2


def test_manifest_supports_installation() -> None:
    import json

    manifest = json.loads(read("static/manifest.webmanifest"))

    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert {icon["sizes"] for icon in manifest["icons"]} >= {"192x192", "512x512"}
