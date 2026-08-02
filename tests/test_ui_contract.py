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
        "stream-diagnostic-primary",
        "source-diagnostic-list",
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

    dashboard = (
        ROOT / "static" / "js" / "dashboard.js"
    ).read_text(encoding="utf-8")
    assert "function updateSourceDiagnostics(sources)" in dashboard
    assert "source-runtime-summary" in dashboard
    assert "runtime.drop_frames" in dashboard
    assert "runtime.dup_frames" in dashboard
    assert "runtime.last_progress_at" in dashboard
    assert "runtime.cpu_percent" in dashboard
    assert "runtime.memory_bytes" in dashboard
    assert "source.health" in dashboard
    assert "runtime.restart_count" in dashboard
    assert "function runSourceProbe(sourceId)" in dashboard
    assert "function sourceProbeResultMarkup(source, state)" in dashboard
    assert "data-source-probe" in dashboard
    assert "api.probeSource(sourceId)" in dashboard
    assert "Mehrquellenstatus" in (
        ROOT / "templates" / "components" / "system_card.html"
    ).read_text(encoding="utf-8")
    health = (
        ROOT / "static" / "js" / "dashboard_health.js"
    ).read_text(encoding="utf-8")
    assert "Temperatur n/v" in health
    assert '"Nicht verfügbar"' in health
    assert "function updateSystemWebAccess(info)" in dashboard
    assert "HTTPS erreichbar" in dashboard


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
    assert '"webkitendfullscreen"' in source_js
    assert '"webkitbeginfullscreen"' in source_js
    assert "resumeSourcePlayback" in source_js
    assert "switchSourceFullscreenStream" in source_js
    assert "fullscreenViewerPath" in source_js
    assert "prepareFullscreenStream" in source_js
    assert "releaseFullscreenStream" in source_js
    assert "Hauptstream wird geladen" in source_js
    assert '"fullscreenchange"' in source_js
    assert "deferUnavailableStop(4000)" in source_js


def test_mobile_web_app_manifest_and_icons_are_linked() -> None:
    index = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    login = (ROOT / "templates" / "login.html").read_text(encoding="utf-8")
    manifest = (ROOT / "static" / "manifest.webmanifest").read_text(
        encoding="utf-8"
    )

    for template in (index, login):
        assert 'rel="manifest"' in template
        assert 'rel="apple-touch-icon"' in template
        assert 'name="theme-color"' in template
    assert '"display": "standalone"' in manifest
    assert '"purpose": "any maskable"' in manifest


def test_each_source_player_recovers_independently() -> None:
    source_js = (
        ROOT / "static" / "js" / "multi_source.js"
    ).read_text(encoding="utf-8")
    player_js = (
        ROOT / "static" / "js" / "live_player.js"
    ).read_text(encoding="utf-8")

    assert "function recoverSourcePlayer(entry, input, now)" in source_js
    assert "Browser-Decoder ohne Bildfortschritt" in source_js
    assert "PLAYER_STALL_TIMEOUT_MS = 8000" in source_js
    assert "PLAYER_RECONNECT_MAX_MS = 15000" in source_js
    assert "sourceCardIsFullscreen(entry)" in source_js
    assert "recovery: playerRecoveryState()" in source_js
    assert 'reconnect(reason = "manual")' in player_js
    assert "this.play(streamName, protocol, true)" in player_js
    assert "function sourcePlayerDiagnostics()" in source_js
    assert "last_frame_progress_at" in source_js
    assert "reconnect_count" in source_js


def test_system_page_shows_per_source_browser_diagnostics() -> None:
    dashboard = (
        ROOT / "static" / "js" / "dashboard.js"
    ).read_text(encoding="utf-8")
    events = (
        ROOT / "static" / "js" / "dashboard_events.js"
    ).read_text(encoding="utf-8")

    assert "window.sourcePlayerDiagnostics?.()" in dashboard
    assert "source-player-summary" in dashboard
    assert "player.packets_lost" in dashboard
    assert "player.frames_dropped" in dashboard
    assert "player.reconnect_count" in dashboard
    assert '"open-bos:player-reconnect"' in events


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
    assert 'minlength="12"' in source_js
    assert 'maxlength="12"' in source_js
    assert "Das Feld ist bearbeitbar" in source_js
    assert "window.installationProfile" not in source_js
    assert "Drohnen-Typ" in source_js
    assert 'data-field="drone_type"' in source_js
    assert 'drone_type: value("drone_type", "").trim()' in source_js


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


def test_system_page_is_hidden_from_viewers() -> None:
    index = (
        ROOT / "templates" / "index.html"
    ).read_text(encoding="utf-8")
    sidebar = (
        ROOT / "templates" / "components" / "sidebar.html"
    ).read_text(encoding="utf-8")

    system_page = index.index('id="page-system"')
    system_nav = sidebar.index('id="nav-system"')
    assert index.rfind(
        '{% if user.role != "viewer" %}', 0, system_page
    ) != -1
    assert sidebar.rfind(
        '{% if user.role != "viewer" %}', 0, system_nav
    ) != -1


def test_viewer_streams_update_without_system_page() -> None:
    dashboard = (
        ROOT / "static" / "js" / "dashboard.js"
    ).read_text(encoding="utf-8")

    update = dashboard.split("function updateDashboard(data)", 1)[1].split(
        "function updateMediaCaptureBar", 1
    )[0]
    assert update.index("updateMultiSources(") < update.index(
        'document.getElementById("page-system")'
    )
    assert 'if (!info || !document.getElementById("system-app-name"))' in (
        dashboard
    )


def test_superadmin_media_source_controls_are_present() -> None:
    settings = (
        ROOT / "templates" / "components" / "settings_card.html"
    ).read_text(encoding="utf-8")
    panel = (
        ROOT / "templates" / "components" / "multi_source_panel.html"
    ).read_text(encoding="utf-8")
    config = (
        ROOT / "static" / "js" / "config.js"
    ).read_text(encoding="utf-8")

    assert 'id="cfg-media-source"' in settings
    assert "Snapshot- und Aufnahmequelle" in settings
    assert '{% if user.role == "superadmin" %}' in panel
    assert 'id="media-capture-bar"' in panel
    assert 'id="media-snapshot-button"' in panel
    assert 'id="media-recording-toggle"' in panel
    assert "function renderMediaCaptureConfig()" in config
    assert "function saveMediaCaptureConfig()" in config


def test_admin_initialization_does_not_call_superadmin_media_functions() -> None:
    app = (
        ROOT / "static" / "js" / "app.js"
    ).read_text(encoding="utf-8")

    superadmin_block = app.split(
        'if (window.currentUser?.role === "superadmin") {',
        1,
    )[1].split("}", 1)[0]
    assert "refreshSnapshot();" in superadmin_block
    assert "refreshMediaLibrary();" in superadmin_block
    assert app.index('role !== "viewer"') < app.index(
        "refreshSnapshot();"
    )


def test_installation_check_uses_public_auth_status() -> None:
    verify = Path(__file__).parents[1] / "scripts" / "verify-installation.sh"
    content = verify.read_text(encoding="utf-8")

    assert "/auth/status" in content


def test_multi_source_test_tools_are_documented_and_keep_tokens_local() -> None:
    project = Path(__file__).parents[1]
    generator = (
        project / "scripts" / "generate-test-video.sh"
    ).read_text(encoding="utf-8")
    publisher = (
        project / "scripts" / "multi-source-test.sh"
    ).read_text(encoding="utf-8")
    readme = (project / "README.md").read_text(encoding="utf-8")
    ignore = (project / ".gitignore").read_text(encoding="utf-8")

    assert "testsrc2=size=1280x720:rate=25" in generator
    assert "-c:v libx264" in generator
    assert "-profile:v baseline" in generator
    assert "-bf 0" in generator
    assert "has_b_frames" in publisher
    assert "type:B" in publisher
    assert "--tokens-file" in publisher
    assert "chmod 600" in publisher
    assert "-stream_loop -1" in publisher
    assert "-c copy" in publisher
    assert "1|4|8" in publisher
    assert "Reproduzierbarer Mehrquellen-Dauertest" in readme
    assert "testdata/*.mp4" in ignore
    assert "test-results/" in ignore
    assert "test-tokens.env*" in ignore


def test_persistent_browser_and_server_test_logging_are_available() -> None:
    project = Path(__file__).parents[1]
    index = (ROOT / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    system = (
        ROOT / "templates" / "components" / "system_card.html"
    ).read_text(encoding="utf-8")
    logging_js = (
        ROOT / "static" / "js" / "test_logging.js"
    ).read_text(encoding="utf-8")
    monitor = (
        project / "scripts" / "server-test-monitor.sh"
    ).read_text(encoding="utf-8")

    assert "/static/js/test_logging.js" in index
    assert 'id="test-session-start"' in system
    assert 'id="test-session-download"' in system
    assert "TEST_LOG_SAMPLE_INTERVAL_MS = 5000" in logging_js
    assert "TEST_LOG_PERSIST_INTERVAL_MS = 30000" in logging_js
    assert "window.localStorage" in logging_js
    assert "sourcePlayerDiagnostics" in logging_js
    assert "player_reconnect" in logging_js
    assert "journalctl" in monitor
    assert "open-bos-streamer.service" in monitor
    assert "/proc/net/dev" in monitor
    assert "redact_stream" in monitor
    assert "passphrase|password|pass" in monitor


def test_rtsp_sources_offer_a_masked_preview_url() -> None:
    source_js = (
        ROOT / "static" / "js" / "config_rtmp_inputs.js"
    ).read_text(encoding="utf-8")

    assert 'data-field="preview_url"' in source_js
    assert 'data-role="toggle-preview-url"' in source_js
    assert "H.264-Substream" in source_js


def test_server_profile_skips_local_display_and_web_proxy_polling() -> None:
    index = (ROOT / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    app = (ROOT / "static" / "js" / "app.js").read_text(
        encoding="utf-8"
    )
    web = (ROOT / "api" / "web.py").read_text(encoding="utf-8")

    assert "window.installationProfile" in index
    assert 'window.installationProfile === "local"' in app
    assert '"installation_profile": installation_profile()' in web


def test_login_page_has_product_identity_and_description() -> None:
    login = (
        ROOT / "templates" / "login.html"
    ).read_text(encoding="utf-8")

    assert "🚒" in login
    assert "Open BOS Stream" in login
    assert "Empfangen, Überwachen und Anzeigen" in login
    assert 'id="auth-title"' in login
    assert 'id="auth-form"' in login


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

    config = (
        ROOT / "static" / "js" / "config.js"
    ).read_text(encoding="utf-8")
    api = (
        ROOT / "static" / "js" / "api.js"
    ).read_text(encoding="utf-8")
    assert 'api.saveSources(currentConfig.sources)' in config
    assert '"/config/sources"' in api


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
