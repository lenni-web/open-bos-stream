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
        "stream-log-toggle",
        "stream-log-panel",
        "stream-log-content",
        "system-reboot",
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
    shell = (ROOT / "static" / "js" / "shell.js").read_text(encoding="utf-8")
    # Ohne Sensor (Server) wird die Temperatur ausgeblendet statt "n/v".
    assert "temperatureRow.hidden = !hasTemperature;" in shell
    assert '"Nicht verfügbar"' in health
    assert "function updateSystemWebAccess(info)" in dashboard
    assert "HTTPS erreichbar" in dashboard

    system_admin = (
        ROOT / "static" / "js" / "system_admin.js"
    ).read_text(encoding="utf-8")
    assert "api.streamLog()" in system_admin
    assert "api.rebootSystem()" in system_admin
    assert system_admin.count("window.confirm(") == 2


def test_app_shell_has_status_user_menu_and_theme_switch() -> None:
    ids = template_ids("header.html")
    index = (
        ROOT / "templates" / "index.html"
    ).read_text(encoding="utf-8")
    sidebar = (
        ROOT / "templates" / "components" / "sidebar.html"
    ).read_text(encoding="utf-8")
    header = (
        ROOT / "templates" / "components" / "header.html"
    ).read_text(encoding="utf-8")

    for element_id in (
        "clock",
        "topbar-title",
        "status-button",
        "status-label",
        "user-button",
        "user-panel",
    ):
        assert element_id in ids
    # Systemdetails nur für Kreis-Admins und Superadmins.
    assert '{% if can.server_admin %}\n            <div id="status-panel"' in header
    for choice in ("auto", "light", "dark"):
        assert f'data-theme-choice="{choice}"' in header
    # Farbschema wird im <head> gesetzt, damit nichts aufblitzt.
    assert index.index("/static/js/theme.js") < index.index("<body")
    assert "/static/css/theme.css" in index
    assert "/static/css/shell.css" in index
    assert "<h1>Übersicht</h1>" in index
    assert 'id="sidebar-collapse"' in sidebar
    assert 'import icon' in sidebar
    assert "nav-icon" not in sidebar


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
    modern_css = (
        ROOT / "static" / "css" / "modern.css"
    ).read_text(encoding="utf-8")

    assert 'id="source-settings"' in settings
    assert 'id="source-add-button"' in settings
    assert "+ Quelle hinzufügen" in settings
    assert "Profil-Empfehlung:" in settings
    assert "bis zu vier Quellen" in settings
    assert "fünf bis acht Quellen" in settings
    assert "Im Vollbild bleibt bei beiden das Original erhalten" in settings
    assert ".settings-profile-recommendation" in modern_css
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
    # Nur ohne Online-Karten und ohne MBTiles erscheint der Hinweis.
    assert "if (!info.options.length)" in map_js
    assert "showMissingMap(info.offline_path)" in map_js


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
    # Signalwechsel protokolliert der Server (core/status_events.py).
    status_events = (ROOT / "core" / "status_events.py").read_text(
        encoding="utf-8"
    )
    assert "Signal verfügbar" in status_events
    assert "Signal verloren" in status_events
    assert "Signal verfügbar" not in events
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
    assert "recoverPlaybackAfterFullscreen" in source_js
    assert "fullscreenRecoveryUntil" in source_js
    assert 'video.addEventListener("pause"' in source_js
    assert "[0, 100, 300, 700, 1400, 2400]" in source_js
    assert "switchSourceFullscreenStream" in source_js
    assert "fullscreenViewerPath" in source_js
    assert "prepareFullscreenStream" in source_js
    assert "releaseFullscreenStream" in source_js
    assert "Hauptstream wird geladen" in source_js
    assert '"fullscreenchange"' in source_js
    assert "deferUnavailableStop(4000)" in source_js


def test_rtmp_multi_source_preview_profile_is_selectable() -> None:
    source_js = (
        ROOT / "static" / "js" / "config_rtmp_inputs.js"
    ).read_text(encoding="utf-8")

    assert '"preview_transcode"' in source_js
    assert '"preview_transcode_economy"' in source_js
    assert "Mehrquellen-Vorschau · ausgewogen (max. 480p)" in source_js
    assert "Mehrquellen-Vorschau · sparsam (max. 360p)" in source_js
    assert '"640×360, 12 fps und etwa 800 kbit/s"' in source_js
    assert '"854×480, 12 fps und etwa 1,1 Mbit/s"' in source_js
    assert "Vollbild zeigt den Originalstream" in source_js


def test_dashboard_polling_uses_two_second_interval() -> None:
    app_js = (ROOT / "static" / "js" / "app.js").read_text(
        encoding="utf-8"
    )
    recording_js = (
        ROOT / "static" / "js" / "recording.js"
    ).read_text(encoding="utf-8")

    assert "refreshDashboard,\n        2000" in app_js
    assert "updateClock,\n        1000" in app_js
    assert "updateRecordingTimer,\n        1000" in app_js
    assert "function updateRecordingTimer()" in recording_js
    assert "currentRecordingDuration()" in recording_js


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
    assert '"purpose": "any"' in manifest
    assert '"purpose": "maskable"' in manifest
    assert "open-bos-stream-maskable-512.png" in manifest


def test_media_player_has_compatibility_fallback() -> None:
    media = (ROOT / "static" / "js" / "media.js").read_text(
        encoding="utf-8"
    )
    recording = (ROOT / "api" / "recording.py").read_text(encoding="utf-8")
    container = (ROOT / "core" / "container.py").read_text(encoding="utf-8")

    assert "tryCompatibleMediaPlayback" in media
    assert "/recording/play-compatible/" in media
    assert '@router.get("/play-compatible/{filename}")' in recording
    assert "RecordingPlaybackCache" in container
    assert "run_in_threadpool(playback_cache.prepare" in recording


def test_dashboard_polling_does_not_block_event_loop() -> None:
    dashboard = (ROOT / "api" / "dashboard.py").read_text(encoding="utf-8")
    system = (ROOT / "api" / "system.py").read_text(encoding="utf-8")

    assert "run_in_threadpool(dashboard_service.status)" in dashboard
    assert "run_in_threadpool(health_service.health)" in system


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
    assert "Organisation und Konten" not in settings


def render_sidebar(role: str, *, server_admin: bool | None = None) -> str:
    from jinja2 import Environment, FileSystemLoader

    from open_bos_stream.api.web import permissions

    user = {"role": role, "username": "test"}
    can = permissions(user)
    if server_admin is not None:
        can["server_admin"] = server_admin
    environment = Environment(loader=FileSystemLoader(ROOT / "templates"))
    return environment.get_template("components/sidebar.html").render(
        user=user,
        can=can,
        version="test",
    )


def test_mobile_menu_keeps_three_main_items_and_moves_the_rest() -> None:
    superadmin = render_sidebar("superadmin")
    viewer = render_sidebar("viewer")

    for page in ("dashboard", "streams", "map", "weather"):
        assert f'id="nav-{page}"' in viewer
        tag = superadmin[superadmin.index(f'id="nav-{page}"'):]
        assert "app-nav-secondary" not in tag[:tag.index(">")]
    for page in ("media", "settings", "system"):
        tag = superadmin[superadmin.index(f'id="nav-{page}"'):]
        assert "app-nav-secondary" in tag[:tag.index(">")]
        assert f'data-page="{page}"' in superadmin
    assert 'id="nav-more"' in superadmin
    # Zuschauer haben nur Hauptpunkte und brauchen kein „Mehr“.
    assert 'id="nav-more"' not in viewer
    assert "BOS Drohnen Suite" in superadmin


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
    assert '"visible": user.role == "superadmin"' in sidebar
    assert 'id="nav-media"' in render_sidebar("superadmin")
    assert 'id="nav-media"' not in render_sidebar("admin")


def test_system_page_is_hidden_from_viewers() -> None:
    index = (
        ROOT / "templates" / "index.html"
    ).read_text(encoding="utf-8")
    sidebar = (
        ROOT / "templates" / "components" / "sidebar.html"
    ).read_text(encoding="utf-8")

    system_page = index.index('id="page-system"')
    assert index.rfind(
        '{% if can.server_admin %}', 0, system_page
    ) != -1
    assert 'id="nav-system"' in render_sidebar("admin")
    assert 'id="nav-system"' not in render_sidebar("viewer")
    # Wehr-Admins ohne Kreisrolle sehen die Systemseite nicht.
    assert 'id="nav-system"' not in render_sidebar("admin", server_admin=False)
    # Drohnenteams sehen die Einstellungen (Gastlinks), aber nicht System.
    operator = render_sidebar("operator", server_admin=False)
    assert 'id="nav-settings"' in operator
    assert 'id="nav-system"' not in operator


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
    assert 'id="cfg-recording-automatic-list"' in settings
    assert "Höchstens vier Quellen" in settings
    assert 'id="cfg-recording-mode-status"' in settings
    assert "Snapshot- und Aufnahmequelle" in settings
    assert '{% if user.role == "superadmin" %}' in panel
    assert 'id="media-capture-bar"' in panel
    assert 'id="media-recording-mode"' in panel
    assert 'id="media-snapshot-button"' in panel
    assert 'id="media-recording-toggle"' in panel
    assert "function renderMediaCaptureConfig()" in config
    assert "function saveMediaCaptureConfig()" in config
    assert "function saveRecordingModeImmediately()" in config
    assert "api.saveMediaCapture(payload)" in config
    assert "automatic_source_ids: automaticRecordingSelection()" in config
    assert "const MAX_AUTOMATIC_RECORDINGS = 4;" in config
    # Busy-Text darf die Kurzbeschriftungen der Buttons nicht zerstören.
    assert 'button.textContent = "Konfiguration testen"' not in config
    multi = (ROOT / "static" / "js" / "multi_source.js").read_text(
        encoding="utf-8"
    )
    assert "updateSourceRecordingBadge(entry.card, input.recording)" in multi


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
    assert app.index("window.currentPermissions?.admin") < app.index(
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

    assert "open-bos-stream.svg" in login
    assert "Open BOS Drohnen" in login
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


def test_stream_outputs_offer_an_explicit_source_selection() -> None:
    outputs = (
        ROOT / "static" / "js" / "config_stream_outputs.js"
    ).read_text(encoding="utf-8")

    assert "Weiterzuleitende Quelle" in outputs
    assert 'data-field="source-id"' in outputs
    assert "source_id:" in outputs

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


def test_organisation_management_replaces_flat_user_list() -> None:
    script = (ROOT / "static" / "js" / "organizations.js").read_text(encoding="utf-8")
    settings = (
        ROOT / "templates" / "components" / "settings_card.html"
    ).read_text(encoding="utf-8")
    index = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    assert not (ROOT / "static" / "js" / "auth_users.js").exists()
    assert "/static/js/organizations.js" in index
    page = (ROOT / "templates" / "components" / "organization_page.html").read_text(encoding="utf-8")
    assert 'id="org-management"' in page
    assert '{% include "components/organization_page.html" %}' in index
    for endpoint in (
        '"/api/org/organizations"',
        '"/api/org/users"',
        "/api/org/users/${userId}/memberships/${organizationId}",
        "/api/org/users/${userId}/qualifications",
    ):
        assert endpoint in script
    # Superadmin-Rolle nur für Superadmins sichtbar.
    assert "window.currentPermissions?.superadmin" in script


def test_viewer_view_hides_technical_details() -> None:
    index = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    header = (
        ROOT / "templates" / "components" / "header.html"
    ).read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "modern.css").read_text(encoding="utf-8")
    sources = (
        ROOT / "static" / "js" / "multi_source.js"
    ).read_text(encoding="utf-8")

    assert '<body class="role-{{ user.role }}">' in index
    assert '"viewer": "Zuschauer"' in header
    for selector in (
        ".role-viewer .dashboard-bottom",
        ".role-viewer .multi-source-placeholder small",
        ".role-viewer .multi-source-meta [data-value]",
    ):
        assert selector in css
    # Profilnamen wie "rtmp · copy_repair" nur für Admins anzeigen.
    assert "function sourceSubtitle(input)" in sources
    assert "return input.drone_type || \"\";" in sources
    assert "${input.type} · ${input.profile}" not in sources.replace(
        "`${input.type} · ${input.profile}` +",
        "",
    )


def test_mobile_layout_keeps_long_texts_inside_cards() -> None:
    css = (ROOT / "static" / "css" / "modern.css").read_text(encoding="utf-8")
    header = (
        ROOT / "templates" / "components" / "header.html"
    ).read_text(encoding="utf-8")

    # Lange Quellennamen und Profile brechen um, der Status bleibt daneben.
    assert ".multi-source-state {\n    flex: 0 0 auto;\n    white-space: nowrap;" in css
    assert "overflow-wrap: anywhere;" in css
    # Smartphones: einspaltige Offline-Quellen, gekürzte Kopfzeile.
    assert ".offline-source-grid {\n        grid-template-columns: minmax(0, 1fr);" in css
    shell_css = (ROOT / "static" / "css" / "shell.css").read_text(encoding="utf-8")
    assert 'class="app-user-name"' in header
    assert 'class="app-status-label"' in header
    assert ".app-status-label,\n    .app-user-name," in shell_css
    assert ".source-order-actions {\n        flex: 1 1 100%;" in css


def test_login_page_links_public_feature_overview_pdf() -> None:
    login = (ROOT / "templates" / "login.html").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "modern.css").read_text(encoding="utf-8")
    pdf = ROOT / "static" / "docs" / "open-bos-stream-funktionsuebersicht.pdf"

    assert 'href="/static/docs/open-bos-stream-funktionsuebersicht.pdf' in login
    assert pdf.read_bytes().startswith(b"%PDF")
    # Das Einrichtungscode-Feld bleibt bei der normalen Anmeldung verborgen.
    assert 'id="auth-setup-code-field" class="form-field" hidden' in login
    assert ".auth-card [hidden] {\n    display: none;" in css


def test_map_layer_control_starts_collapsed() -> None:
    template = (
        ROOT / "templates" / "components" / "map.html"
    ).read_text(encoding="utf-8")
    start = template.index('id="map-layer-control"')
    tag = template[start:template.index(">", start)]

    assert "open" not in tag.split()


def test_stream_output_names_are_escaped_and_not_inlined_in_handlers() -> None:
    """Review N1: Ausgangsnamen dürfen kein HTML oder Skript einschleusen."""

    outputs = (ROOT / "static" / "js" / "stream_outputs.js").read_text(
        encoding="utf-8"
    )
    settings = (
        ROOT / "static" / "js" / "config_stream_outputs.js"
    ).read_text(encoding="utf-8")

    assert "<strong>${escapeHTML(output.name)}</strong>" in outputs
    assert 'data-output-name="${escapeHTML(output.name)}"' in outputs
    assert "StreamOutput('${output.name}')" not in outputs
    assert 'value="${escapeHTML(output.name)}"' in settings
    assert 'value="${escapeHTML(output.url)}"' in settings


def test_logout_and_organisation_menu_are_available() -> None:
    shell = (ROOT / "static" / "js" / "shell.js").read_text(encoding="utf-8")
    header = (ROOT / "templates" / "components" / "header.html").read_text(encoding="utf-8")

    assert 'onclick="logoutUser()"' in header
    assert "async function logoutUser()" in shell
    assert 'id="nav-organization"' in render_sidebar("admin")
    assert 'id="nav-organization"' not in render_sidebar("operator", server_admin=False)


def test_every_onclick_handler_is_defined() -> None:
    """Ein Klick auf einen Knopf darf nicht ins Leere laufen."""

    import re

    scripts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "static" / "js").glob("*.js")
    )
    defined = set(re.findall(r"(?:async\s+)?function\s+(\w+)\s*\(", scripts))
    defined |= set(re.findall(r"window\.(\w+)\s*=", scripts))
    builtins = {"event", "showPage", "this", "orgState"}
    missing = set()
    for template in (ROOT / "templates").rglob("*.html"):
        text = template.read_text(encoding="utf-8")
        for handler in re.findall(r'on(?:click|change|submit|toggle)="([^"]+)"', text):
            for name in re.findall(r"(?<![\w.])([A-Za-z_]\w*)\s*\(", handler):
                if name not in defined and name not in builtins:
                    missing.add(f"{template.name}: {name}")
    assert missing == set()
