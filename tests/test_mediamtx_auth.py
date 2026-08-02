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
