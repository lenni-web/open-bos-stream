from __future__ import annotations

import asyncio

import pytest
import yaml
from fastapi import HTTPException
from starlette.requests import Request

from open_bos_stream.api import mediamtx_auth
from open_bos_stream.api.mediamtx_auth import MediaMTXAuthRequest
from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.models import SourceConfig


def auth_request(
    *,
    token: str,
    path: str = "quelle-1",
    protocol: str = "rtmp",
    ip: str = "203.0.113.10",
    query: str = "",
) -> MediaMTXAuthRequest:
    return MediaMTXAuthRequest(
        action="publish",
        path=path,
        protocol=protocol,
        token=token,
        ip=ip,
        query=query,
    )


def local_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/internal/mediamtx/auth",
            "headers": [],
            "client": ("127.0.0.1", 43120),
        }
    )


def configure_auth(monkeypatch, token: str) -> None:
    source = SourceConfig(
        id="quelle-1",
        name="Quelle 1",
        type="rtmp",
        publish_token=token,
    )
    monkeypatch.setattr(mediamtx_auth.config, "sources", [source])


def authorize(payload: MediaMTXAuthRequest) -> dict[str, bool]:
    return asyncio.run(
        mediamtx_auth.authorize_mediamtx(payload, local_request())
    )


def test_matching_source_token_allows_external_rtmp_publisher(
    monkeypatch,
) -> None:
    token = "a" * 12
    configure_auth(monkeypatch, token)

    assert authorize(auth_request(token=token)) == {"authorized": True}


def test_query_token_from_older_mediamtx_is_accepted(monkeypatch) -> None:
    token = "a" * 12
    configure_auth(monkeypatch, token)

    assert authorize(
        auth_request(token="", query=f"token={token}")
    ) == {"authorized": True}


def test_query_appended_to_legacy_path_is_normalized(monkeypatch) -> None:
    token = "a" * 12
    configure_auth(monkeypatch, token)

    assert authorize(
        auth_request(token="", path=f"quelle-1?token={token}")
    ) == {"authorized": True}


def test_rejected_token_is_not_written_to_log(
    monkeypatch,
    caplog,
) -> None:
    configure_auth(monkeypatch, "a" * 12)
    rejected_token = "b" * 12

    with pytest.raises(HTTPException):
        authorize(auth_request(token=rejected_token))

    assert rejected_token not in caplog.text
    assert "Token vorhanden=True" in caplog.text


@pytest.mark.parametrize(
    ("payload", "status_code"),
    [
        (auth_request(token="b" * 12), 401),
        (auth_request(token="a" * 12, path="quelle-2"), 403),
        (auth_request(token="a" * 12, protocol="rtsp"), 403),
    ],
)
def test_invalid_external_publisher_is_rejected(
    monkeypatch,
    payload: MediaMTXAuthRequest,
    status_code: int,
) -> None:
    configure_auth(monkeypatch, "a" * 12)

    with pytest.raises(HTTPException) as error:
        authorize(payload)

    assert error.value.status_code == status_code


def test_internal_relay_is_allowed_without_token(monkeypatch) -> None:
    configure_auth(monkeypatch, "a" * 12)

    assert authorize(
        auth_request(token="", protocol="rtsp", ip="127.0.0.1")
    ) == {"authorized": True}


def test_rtmp_source_gets_random_publisher_token() -> None:
    first = SourceConfig(id="quelle-1", name="Quelle", type="rtmp")
    second = SourceConfig(id="quelle-2", name="Quelle", type="rtmp")

    assert first.publish_token is not None
    assert len(first.publish_token) == 12
    assert first.publish_token != second.publish_token


def test_long_legacy_publisher_token_is_shortened_stably() -> None:
    source = SourceConfig(
        id="quelle-1",
        name="Quelle",
        type="rtmp",
        publish_token="abcdefghijklmnopqrstuvwx",
    )

    assert source.publish_token == "abcdefghijkl"


def test_migration_persists_missing_publisher_token(tmp_path) -> None:
    data = ConfigLoader().load().model_dump()
    data["sources"] = [
        {
            "id": "quelle-1",
            "name": "Quelle 1",
            "type": "rtmp",
        }
    ]
    config_file = tmp_path / "stream.yaml"
    config_file.write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )
    first = ConfigLoader(str(config_file)).load()
    second = ConfigLoader(str(config_file)).load()

    assert first.sources[0].publish_token
    assert (
        first.sources[0].publish_token
        == second.sources[0].publish_token
    )
    assert "publish_token:" in config_file.read_text(encoding="utf-8")


def test_migration_persists_shortened_legacy_token(tmp_path) -> None:
    data = ConfigLoader().load().model_dump()
    data["sources"] = [
        {
            "id": "quelle-1",
            "name": "Quelle 1",
            "type": "rtmp",
            "publish_token": "abcdefghijklmnopqrstuvwx",
        }
    ]
    config_file = tmp_path / "stream.yaml"
    config_file.write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )

    config = ConfigLoader(str(config_file)).load()
    persisted = yaml.safe_load(
        config_file.read_text(encoding="utf-8")
    )

    assert config.sources[0].publish_token == "abcdefghijkl"
    assert persisted["sources"][0]["publish_token"] == "abcdefghijkl"


def read_request(
    *,
    protocol: str,
    ip: str = "203.0.113.10",
    token: str = "",
    query: str = "",
) -> MediaMTXAuthRequest:
    return MediaMTXAuthRequest(
        action="read",
        path="quelle-1",
        protocol=protocol,
        token=token,
        ip=ip,
        query=query,
    )


@pytest.mark.parametrize("protocol", ["rtmp", "rtsp", "srt", "webrtc", "hls"])
def test_external_readers_without_token_are_rejected(protocol) -> None:
    with pytest.raises(HTTPException) as error:
        authorize(read_request(protocol=protocol))

    assert error.value.status_code == 401


@pytest.mark.parametrize("ip", ["127.0.0.1", "::1"])
def test_local_readers_are_allowed(ip) -> None:
    # Caddy (nach Sitzungsprüfung) und die internen FFmpeg-Prozesse.
    assert authorize(read_request(protocol="rtsp", ip=ip)) == {"authorized": True}


def test_browser_reader_with_media_token_is_allowed(tmp_path, monkeypatch) -> None:
    from open_bos_stream.auth.service import AuthService

    auth = AuthService(str(tmp_path / "users.yaml"), str(tmp_path / "auth.secret"))
    user = auth.create_user("zuschauer", "sicheres-passwort", "viewer")
    monkeypatch.setattr(mediamtx_auth, "auth_service", auth)
    media = auth.create_media_token(user)
    session = auth.create_token(user)

    assert authorize(read_request(protocol="webrtc", token=media)) == {"authorized": True}
    assert authorize(read_request(protocol="hls", query=f"token={media}")) == {"authorized": True}
    for payload in (
        read_request(protocol="webrtc", token=session),
        read_request(protocol="rtmp", token=media),
    ):
        with pytest.raises(HTTPException):
            authorize(payload)


def test_mediamtx_configs_no_longer_exempt_readers() -> None:
    for name in ("mediamtx.server.yml", "mediamtx.local.yml"):
        data = yaml.safe_load(open(f"config/{name}", encoding="utf-8"))
        excluded = {item["action"] for item in data["authHTTPExclude"]}
        assert "read" not in excluded
        assert data["authMethod"] == "http"


@pytest.mark.parametrize("protocol", ["hls", "webrtc"])
def test_reader_payload_with_null_id_from_mediamtx_is_accepted(protocol):
    """MediaMTX 1.21 sendet vor dem Sitzungsaufbau "id": null."""

    payload = MediaMTXAuthRequest.model_validate(
        {
            "ip": "127.0.0.1",
            "user": "",
            "password": "",
            "token": "",
            "action": "read",
            "path": "quelle-1",
            "protocol": protocol,
            "id": None,
            "query": "",
            "userAgent": "Safari",
        }
    )

    assert payload.id == ""
    assert authorize(payload) == {"authorized": True}
