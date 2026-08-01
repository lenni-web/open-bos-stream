from pathlib import Path

import yaml

from open_bos_stream.core import installation
from open_bos_stream.core.installation import installation_profile
from open_bos_stream.version import VERSION


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_release_version_is_0_10_10() -> None:
    assert VERSION == "0.10.10"


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
    dependency_installer = read("scripts/install-mediamtx.sh")
    service = read("scripts/mediamtx.service")

    assert 'mediamtx.${PROFILE}.yml' in installer
    assert "sudo systemctl enable mediamtx.service" in installer
    assert "sudo systemctl restart mediamtx.service" in installer
    assert "/usr/local/bin/mediamtx" in installer
    assert "/home/streampi/mediamtx" in installer
    assert 'getent passwd "${SERVICE_USER}"' in installer
    assert '"${SERVICE_HOME:-/home/${SERVICE_USER}}/mediamtx"' in installer
    assert "/usr/local/bin/mediamtx.new" in installer
    assert "mediamtx_v${MEDIAMTX_VERSION}_linux_${architecture}" in (
        dependency_installer
    )
    assert "sha256sum" in dependency_installer
    assert "x86_64|amd64" in dependency_installer
    assert "aarch64|arm64" in dependency_installer
    assert "armv7l|armv7" in dependency_installer
    assert "armv6l|armv6" in dependency_installer
    assert "ExecStart=/usr/local/bin/mediamtx" in service
    assert "WorkingDirectory=/var/lib/open-bos-stream" in service


def test_install_and_update_expose_mediamtx_options() -> None:
    install = read("scripts/install.sh")
    update = read("scripts/update.sh")

    for script in (install, update):
        assert "--install-mediamtx" in script
        assert "--no-install-mediamtx" in script
        assert "--mediamtx-version" in script
        assert "--mediamtx-archive" in script
        assert '"${SCRIPT_DIR}/install-mediamtx.sh"' in script

    dependencies = read("scripts/install-dependencies.sh")
    assert "curl" in dependencies
    assert "tar" in dependencies


def test_installer_creates_and_persists_service_identity() -> None:
    common = read("scripts/common.sh")
    ensure_user = read("scripts/ensure-service-user.sh")
    installer = read("scripts/install-service.sh")
    install = read("scripts/install.sh")
    update = read("scripts/update.sh")

    assert 'INSTALL_CONFIG_FILE="${PROFILE_DIR}/install.env"' in common
    assert "OPEN_BOS_SERVICE_USER" in common
    assert "OPEN_BOS_SERVICE_GROUP" in common
    assert "validate_service_identity" in common
    assert "runuser -u" in common
    assert "sudo groupadd --system" in ensure_user
    assert "sudo useradd" in ensure_user
    assert "--create-home" in ensure_user
    assert '"${INSTALL_CONFIG_FILE}"' in ensure_user
    assert 's/^User=.*/User=${SERVICE_USER}/' in installer
    assert 's/^Group=.*/Group=${SERVICE_GROUP}/' in installer
    assert 's/^streampi /${SERVICE_USER} /' in installer
    assert 'sudo -H -u "${SERVICE_USER}"' in installer
    assert 'chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${VENV_DIR}"' in (
        installer
    )
    assert 'PACKAGE_BUILD_DIR="$(mktemp -d)"' in installer
    assert 'cp -R "${TARGET_DIR}/src"' in installer
    assert '"${PACKAGE_BUILD_DIR}"' in installer
    assert '--exclude "*.egg-info/"' in read("scripts/deploy.sh")
    for script in (install, update):
        assert "--service-user" in script
        assert "--service-group" in script
        assert '"${SCRIPT_DIR}/ensure-service-user.sh"' in script
    dependencies = read("scripts/install-dependencies.sh")
    assert "sudo" in dependencies


def test_caddy_routes_application_whep_and_hls() -> None:
    caddy = read("scripts/Caddyfile.server")

    assert "acme-v02.api.letsencrypt.org" in caddy
    assert "handle_path /whep/*" in caddy
    assert "header_down Location ^/ /whep/" in caddy
    assert "handle_path /hls/*" in caddy
    assert "header_down Location ^/ /hls/" in caddy
    assert "reverse_proxy 127.0.0.1:8000" in caddy


def test_server_access_accepts_domain_or_https_url() -> None:
    script = read("scripts/configure-server-access.sh")

    assert 'value="${value#http://}"' in script
    assert 'value="${value#https://}"' in script
    assert 'DOMAIN="$(normalize_domain "${DOMAIN}")"' in script
    assert "z. B. ffw-stream.de" in script


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
