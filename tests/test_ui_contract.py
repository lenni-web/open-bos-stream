from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).parents[1] / "src" / "open_bos_stream"


class IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")

        if element_id:
            self.ids.add(element_id)


def template_ids(name: str) -> set[str]:
    parser = IdCollector()
    parser.feed(
        (
            ROOT / "templates" / "components" / name
        ).read_text(encoding="utf-8")
    )
    return parser.ids


def test_media_controls_remain_available() -> None:
    ids = (
        template_ids("media_library.html")
        | template_ids("media_preview.html")
    )

    assert {
        "media-count",
        "media-search",
        "media-type-filter",
        "media-library",
        "media-title",
        "media-video",
        "media-image",
        "media-placeholder",
    } <= ids


def test_navigation_stops_media_preview() -> None:
    navigation = (
        ROOT / "static" / "js" / "navigation.js"
    ).read_text(encoding="utf-8")
    media = (
        ROOT / "static" / "js" / "media.js"
    ).read_text(encoding="utf-8")

    assert "stopMediaPreview()" in navigation
    assert "function stopMediaPreview()" in media


def test_system_diagnostics_controls_remain_available() -> None:
    ids = template_ids("system_card.html")

    assert {
        "stream-diagnostic-state",
        "stream-diagnostic-mode",
        "stream-diagnostic-input",
        "stream-diagnostic-restarts",
        "stream-diagnostic-error",
        "system-storage-free",
        "system-storage-bar",
        "system-storage-media",
        "system-alerts",
        "stream-probe-fps",
        "stream-probe-timebase",
        "stream-probe-timestamps",
        "stream-probe-bitrate",
        "stream-probe-packet-timing",
        "viewer-connection-state",
        "viewer-network",
        "viewer-dropped-frames",
        "stream-stable-for",
    } <= ids


def test_compact_header_keeps_responsive_system_summary() -> None:
    ids = template_ids("header.html")
    index = (
        ROOT / "templates" / "index.html"
    ).read_text(encoding="utf-8")

    assert "header-system-summary" in ids
    assert "<h1>Übersicht</h1>" in index
    assert "<h1>Livebetrieb</h1>" not in index


def test_stream_output_uses_shared_api_error_handling() -> None:
    api = (
        ROOT / "static" / "js" / "api.js"
    ).read_text(encoding="utf-8")

    assert "Streaming Output konnte nicht gestartet werden." not in api
    assert "/stream-output/${encodeURIComponent(name)}/start" in api


def test_rtmp_input_views_use_available_html_escaping() -> None:
    index = (
        ROOT / "templates" / "index.html"
    ).read_text(encoding="utf-8")
    ui = (
        ROOT / "static" / "js" / "ui.js"
    ).read_text(encoding="utf-8")

    assert "function escapeHTML(value)" in ui
    assert index.index("/static/js/ui.js") < index.index(
        "/static/js/config_rtmp_inputs.js"
    )
    assert index.index("/static/js/ui.js") < index.index(
        "/static/js/multi_source.js"
    )


def test_settings_use_one_equal_source_list() -> None:
    settings = (
        ROOT / "templates" / "components" / "settings_card.html"
    ).read_text(encoding="utf-8")
    source_js = (
        ROOT / "static" / "js" / "config_rtmp_inputs.js"
    ).read_text(encoding="utf-8")

    assert 'id="source-settings"' in settings
    assert 'id="source-add-button"' in settings
    assert "+ Quelle hinzufügen" in settings
    assert "RTMP-Eingang hinzufügen" not in settings
    assert "function renderSources()" in source_js
    assert "data-role=\"publish-url\"" in source_js
    assert "readonly" in source_js
