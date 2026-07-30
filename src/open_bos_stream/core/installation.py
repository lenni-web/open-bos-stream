"""Host-spezifische Installationsmerkmale."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

InstallationProfile = Literal["local", "server"]

PROFILE_FILE = Path("/etc/open-bos-stream/profile")
SERVER_CONFIG_FILE = Path("/etc/open-bos-stream/server.env")


def installation_profile() -> InstallationProfile:
    """Liest das unveränderliche, vom Installer gesetzte Hostprofil."""

    configured = os.environ.get("OPEN_BOS_PROFILE")
    if configured is None:
        try:
            configured = PROFILE_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            configured = "local"
    return "server" if configured == "server" else "local"


def server_access_settings() -> dict[str, str]:
    """Liefert ausschließlich die nicht geheimen Serverparameter."""

    settings = {
        "public_domain": "",
        "https_enabled": "no",
        "webrtc_mode": "local",
        "firewall_mode": "off",
    }
    try:
        lines = SERVER_CONFIG_FILE.read_text(
            encoding="utf-8",
        ).splitlines()
    except OSError:
        return settings

    keys = {
        "PUBLIC_DOMAIN": "public_domain",
        "HTTPS_ENABLED": "https_enabled",
        "WEBRTC_MODE": "webrtc_mode",
        "FIREWALL_MODE": "firewall_mode",
    }
    for line in lines:
        key, separator, value = line.partition("=")
        if separator and key in keys:
            settings[keys[key]] = value.strip()
    return settings
