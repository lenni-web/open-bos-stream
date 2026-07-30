from pathlib import Path

import yaml

from open_bos_stream.core import installation
from open_bos_stream.core.installation import installation_profile
from open_bos_stream.version import VERSION


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_release_version_is_0_10_9() -> None:
    assert VERSION == "0.10.9"


def test_server_profile_can_be_selected_from_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPEN_BOS_PROFILE", "server")

    assert installation_profile() == "server"


def test_server_access_settings_are_read(
    monkeypatch,
    tmp_path,
) -> None:
    settings_file = tmp_path / "server.env"
    settings_file.write_text(
        "PUBLIC_DOMAIN=stream.example.de\n"
        "HTTPS_ENABLED=yes\n"
        "WEBRTC_MODE=public\n"
        "FIREWALL_MODE=configure\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        installation,
        "SERVER_CONFIG_FILE",
        settings_file,
    )

    assert installation.server_access_settings() == {
        "public_domain": "stream.example.de",
        "https_enabled": "yes",
        "webrtc_mode": "public",
        "firewall_mode": "configure",
    }


def test_server_mediamtx_authenticates_rtmp_publishers() -> None:
    config = yaml.safe_load(
        read("config/mediamtx.server.yml")
    )

    assert config["apiAddress"] == "127.0.0.1:9997"
    assert config["rtspAddress"] == "127.0.0.1:8554"
    assert config["authMethod"] == "http"
    assert config["authHTTPAddress"] == (
        "http://127.0.0.1:8000/internal/mediamtx/auth"
    )
    assert "publish" not in config["authHTTPExclude"]


def test_local_mediamtx_authenticates_rtmp_publishers() -> None:
    config = yaml.safe_load(
        read("config/mediamtx.local.yml")
    )

    assert config["authMethod"] == "http"
    assert config["authHTTPAddress"] == (
        "http://127.0.0.1:8000/internal/mediamtx/auth"
    )
    assert "apiAddress" not in config
    assert "rtspAddress" not in config
    assert "publish" not in config["authHTTPExclude"]


def test_installer_manages_mediamtx_in_both_profiles() -> None:
    installer = read("scripts/install-service.sh")

    assert 'mediamtx.${PROFILE}.yml' in installer
    assert "sudo systemctl enable mediamtx.service" in installer
    assert "sudo systemctl restart mediamtx.service" in installer


def test_caddy_routes_application_whep_and_hls() -> None:
    caddy = read("scripts/Caddyfile.server")

    assert "acme-v02.api.letsencrypt.org" in caddy
    assert "handle_path /whep/*" in caddy
    assert "header_down Location ^/ /whep/" in caddy
    assert "handle_path /hls/*" in caddy
    assert "header_down Location ^/ /hls/" in caddy
    assert "reverse_proxy 127.0.0.1:8000" in caddy


def test_https_player_uses_same_origin_routes() -> None:
    player = read(
        "src/open_bos_stream/static/js/live_player.js"
    )

    assert "${window.location.origin}/whep/${path}/whep" in player
    assert "${window.location.origin}/hls/${path}/index.m3u8" in player


def test_firewall_preserves_ssh_and_warns_about_rtmp() -> None:
    script = read("scripts/configure-server-access.sh")

    assert 'sudo sshd -T' in script
    assert 'sudo ufw allow "${ssh_port}/tcp"' in script
    assert 'sudo ufw allow 1935/tcp comment "RTMP Publisher Token"' in script
    assert "Publisher benötigen aber einen Token" in script
