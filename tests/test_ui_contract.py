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


def test_missing_map_shows_stade_download_and_target_path() -> None:
    map_template = (
        ROOT / "templates" / "components" / "map.html"
    ).read_text(encoding="utf-8")
    map_js = (
        ROOT / "static" / "js" / "map.js"
    ).read_text(encoding="utf-8")

    assert "map-empty-state" in map_template
    assert (
        "https://nextcloud.lenni-web.de/index.php/s/"
        "YXpLgCPG5Twm8MP"
    ) in map_template
    assert "/opt/open-bos-stream/mapdata/stade.mbtiles" in map_template
    assert '"/api/map/maps"' in map_js
    assert "showMissingMap(maps.path)" in map_js


def test_dashboard_uses_only_unified_source_players() -> None:
    index = (
        ROOT / "templates" / "index.html"
    ).read_text(encoding="utf-8")
    source_js = (
        ROOT / "static" / "js" / "config_rtmp_inputs.js"
    ).read_text(encoding="utf-8")
    events = (
        ROOT / "static" / "js" / "dashboard_events.js"
    ).read_text(encoding="utf-8")
    player = (
        ROOT / "static" / "js" / "live_player.js"
    ).read_text(encoding="utf-8")

    assert 'components/video_panel.html' not in index
    assert 'components/status_card.html' not in index
    assert 'components/stream_card.html' not in index
    assert "function moveSource(index, direction)" in source_js
    assert "function checkSourceEvents(sources = [])" in events
    assert "Signal verfügbar" in events
    assert "Signal verloren" in events
    assert "defaultLiveVideo" in player


def test_multi_source_audio_starts_muted() -> None:
    source_js = (
        ROOT / "static" / "js" / "multi_source.js"
    ).read_text(encoding="utf-8")
    player_js = (
        ROOT / "static" / "js" / "live_player.js"
    ).read_text(encoding="utf-8")

    assert "video.muted = true" in source_js
    assert "video.defaultMuted = true" in source_js
    assert "multi-source-audio" not in source_js
    assert "this.video.muted = true" in player_js


def test_each_source_player_has_fullscreen_control() -> None:
    source_js = (
        ROOT / "static" / "js" / "multi_source.js"
    ).read_text(encoding="utf-8")

    assert "multi-source-fullscreen" in source_js
    assert "card.requestFullscreen()" in source_js
    assert "video.webkitEnterFullscreen()" in source_js
    assert "deferUnavailableStop(4000)" in source_js


def test_source_settings_are_compact_and_urls_can_be_revealed() -> None:
    source_js = (
        ROOT / "static" / "js" / "config_rtmp_inputs.js"
    ).read_text(encoding="utf-8")

    assert 'document.createElement("details")' in source_js
    assert "URL anzeigen und bearbeiten" in source_js
    assert 'input.type = visible ? "password" : "text"' in source_js
    assert 'audio_mode: "none"' in source_js
    assert 'data-field="publish_token"' in source_js
    assert 'data-role="toggle-publish-url"' in source_js
    assert "?token=${encodeURIComponent(source.publish_token)}" in source_js


def test_offline_sources_and_role_ui_are_present() -> None:
    panel = (
        ROOT / "templates" / "components" / "multi_source_panel.html"
    ).read_text(encoding="utf-8")
    index = (
        ROOT / "templates" / "index.html"
    ).read_text(encoding="utf-8")
    settings = (
        ROOT / "templates" / "components" / "settings_card.html"
    ).read_text(encoding="utf-8")
    source_js = (
        ROOT / "static" / "js" / "multi_source.js"
    ).read_text(encoding="utf-8")

    assert "offline-source-grid" in panel
    assert "offlineOrder" in source_js
    assert "window.currentUser" in index
    assert 'user.role == "superadmin"' in settings
    assert "Benutzer und Rollen" in settings


def test_media_page_is_visible_only_to_superadmins() -> None:
    index = (
        ROOT / "templates" / "index.html"
    ).read_text(encoding="utf-8")
    sidebar = (
        ROOT / "templates" / "components" / "sidebar.html"
    ).read_text(encoding="utf-8")

    assert index.index('{% if user.role == "superadmin" %}') < index.index(
        'id="page-media"'
    )
    assert sidebar.index('{% if user.role == "superadmin" %}') < (
        sidebar.index('id="nav-media"')
    )


def test_installation_check_uses_public_auth_status() -> None:
    verify = Path(__file__).parents[1] / "scripts" / "verify-installation.sh"
    content = verify.read_text(encoding="utf-8")

    assert "/auth/status" in content


def test_hidden_superadmin_outputs_are_not_cleared_by_admin_save() -> None:
    outputs = (
        ROOT / "static" / "js" / "config_stream_outputs.js"
    ).read_text(encoding="utf-8")

    save_function = outputs.split(
        "function saveStreamOutputs()",
        1,
    )[1]
    assert '"stream-output-settings"' in save_function
    assert "if (!container)" in outputs


def test_outdated_delivery_card_is_removed() -> None:
    settings = (
        ROOT / "templates" / "components" / "settings_card.html"
    ).read_text(encoding="utf-8")

    assert "Bereitstellung" not in settings
    assert "cfg-viewer-protocol" not in settings
    assert "settings-advanced" not in settings


def test_transcoding_options_belong_to_each_source() -> None:
    settings = (
        ROOT / "templates" / "components" / "settings_card.html"
    ).read_text(encoding="utf-8")
    sources = (
        ROOT / "static" / "js" / "config_rtmp_inputs.js"
    ).read_text(encoding="utf-8")

    assert "cfg-encoder-codec" not in settings
    assert "Transcoding dieser Quelle" in sources
    assert "sourceTranscodingFields(source)" in sources
    assert "loadSourceEncoders" in sources


def test_superadmin_can_edit_user_role_and_password() -> None:
    users = (
        ROOT / "static" / "js" / "auth_users.js"
    ).read_text(encoding="utf-8")

    assert "function saveUser(username)" in users
    assert "Neues Passwort (optional)" in users
    assert "api.patch(" in users
