from __future__ import annotations

import json
import os
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from open_bos_stream.notifications import webpush
from open_bos_stream.notifications.monitor import Notice, NotificationMonitor
from open_bos_stream.notifications.push_service import PushError, PushService
from tests.test_organizations import PASSWORD, auth, build, session, source  # noqa: F401


ENDPOINT = "https://fcm.googleapis.com/fcm/send/geraet-1"


class Device:
    """Simuliertes Browser-Abo mit eigenem Schlüsselpaar."""

    def __init__(self, endpoint: str = ENDPOINT) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.auth = os.urandom(16)
        self.endpoint = endpoint

    @property
    def p256dh(self) -> str:
        return webpush.b64url_encode(webpush._raw_public(self.key.public_key()))

    def json(self) -> dict:
        return {
            "endpoint": self.endpoint,
            "keys": {"p256dh": self.p256dh, "auth": webpush.b64url_encode(self.auth)},
        }

    def decrypt(self, body: bytes) -> dict:
        """Entschlüsselung wie im Browser (RFC 8291), unabhängig nachgebaut."""

        salt = body[:16]
        record_size, id_length = struct.unpack("!IB", body[16:21])
        assert record_size == 4096
        sender_raw = body[21:21 + id_length]
        ciphertext = body[21 + id_length:]
        sender = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), sender_raw)
        shared = self.key.exchange(ec.ECDH(), sender)
        receiver_raw = webpush._raw_public(self.key.public_key())
        prk_key = webpush._hmac(self.auth, shared)
        ikm = webpush._hmac(prk_key, b"WebPush: info\x00" + receiver_raw + sender_raw + b"\x01")
        prk = webpush._hmac(salt, ikm)
        cek = webpush._hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
        nonce = webpush._hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12]
        plain = AESGCM(cek).decrypt(nonce, ciphertext, None)
        assert plain.endswith(b"\x02")
        return json.loads(plain[:-1])


class FakePost:
    def __init__(self, status: int = 201) -> None:
        self.status = status
        self.calls: list[dict] = []

    def __call__(self, url, *, data, headers, timeout, allow_redirects):
        assert allow_redirects is False
        self.calls.append({"url": url, "data": data, "headers": headers})
        return SimpleNamespace(status_code=self.status)


# ----------------------------------------------------------------------
# Protokoll
# ----------------------------------------------------------------------


def test_payload_is_encrypted_for_the_device_only() -> None:
    device = Device()
    body = webpush.encrypt(b'{"title":"Hallo"}', device.p256dh, webpush.b64url_encode(device.auth))

    assert b"Hallo" not in body
    assert device.decrypt(body) == {"title": "Hallo"}
    with pytest.raises(Exception):
        Device().decrypt(body)


def test_vapid_header_is_a_valid_es256_token(tmp_path: Path) -> None:
    key_file = tmp_path / "webpush.key"
    vapid = webpush.VapidKey.load_or_create(key_file)
    assert oct(key_file.stat().st_mode & 0o777) == "0o600"
    # Beim nächsten Start bleibt der Schlüssel gleich (Abos bleiben gültig).
    assert webpush.VapidKey.load_or_create(key_file).public_key == vapid.public_key

    header = vapid.authorization(ENDPOINT, "https://drohnen.example.org", now=1000)
    token, key = header.removeprefix("vapid t=").split(", k=")
    assert key == vapid.public_key
    head, claims, signature = token.split(".")
    assert json.loads(webpush.b64url_decode(claims)) == {
        "aud": "https://fcm.googleapis.com",
        "exp": 1000 + webpush.JWT_LIFETIME_SECONDS,
        "sub": "https://drohnen.example.org",
    }
    raw = webpush.b64url_decode(signature)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    vapid.private_key.public_key().verify(
        der, f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256())
    )


@pytest.mark.parametrize(
    ("endpoint", "allowed"),
    [
        (ENDPOINT, True),
        ("https://updates.push.services.mozilla.com/wpush/v2/abc", True),
        ("https://web.push.apple.com/QGx", True),
        ("https://wns2-db5p.notify.windows.com/w/?token=x", True),
        ("http://fcm.googleapis.com/fcm/send/x", False),
        ("https://fcm.googleapis.com:8443/x", False),
        ("https://user@fcm.googleapis.com/x", False),
        ("https://evilfcm.googleapis.com.example.org/x", False),
        ("https://127.0.0.1/x", False),
        ("https://intern.local/x", False),
    ],
)
def test_only_known_push_services_are_contacted(endpoint: str, allowed: bool) -> None:
    assert webpush.endpoint_allowed(endpoint) is allowed


# ----------------------------------------------------------------------
# Geräte und Empfänger
# ----------------------------------------------------------------------


@pytest.fixture
def push(auth, tmp_path: Path):  # noqa: F811
    ids = build(auth)
    config = SimpleNamespace(sources=[source("b1", ids["b"]), source("frei", None)])
    post = FakePost()
    service = PushService(config, auth, key_file=tmp_path / "webpush.key", post=post)
    service.ids = ids
    service.post = post
    return service


def subscribe(push: PushService, auth, username: str, device: Device | None = None, **extra) -> dict:  # noqa: F811
    device = device or Device(f"https://fcm.googleapis.com/fcm/send/{username}")
    data = device.json()
    return push.subscribe(
        session(auth, username),
        endpoint=data["endpoint"],
        p256dh=data["keys"]["p256dh"],
        auth=data["keys"]["auth"],
        **extra,
    )


def test_subscribe_validates_endpoint_and_keys(push, auth) -> None:  # noqa: F811
    user = session(auth, "b-zuschauer")
    device = Device()
    with pytest.raises(PushError):
        push.subscribe(user, endpoint="https://intern.local/x", p256dh=device.p256dh, auth="AAAAAAAAAAAAAAAAAAAAAA")
    with pytest.raises(PushError):
        push.subscribe(user, endpoint=ENDPOINT, p256dh="kaputt", auth="kaputt")


def test_viewer_may_only_choose_source_events(push, auth) -> None:  # noqa: F811
    viewer = subscribe(push, auth, "b-zuschauer", events=["source_offline", "storage_low"])
    kreis = subscribe(push, auth, "kreis")

    assert viewer["events"] == ["source_offline"]
    assert "storage_low" in kreis["events"] and "server_started" in kreis["events"]


def test_source_notice_reaches_only_accounts_that_see_the_source(push, auth) -> None:  # noqa: F811
    for username in ("b-zuschauer", "a-admin", "kreis", "betreiber"):
        subscribe(push, auth, username)

    def receivers(notice: Notice) -> set[str]:
        owners = {item["user_id"] for item in push.recipients(notice)}
        return {auth.ready().user_by_id(user_id)["username"] for user_id in owners}

    offline = Notice(event="source_offline", subject="x", body="y", source_id="b1")
    assert receivers(offline) == {"b-zuschauer", "kreis", "betreiber"}
    unassigned = Notice(event="source_offline", subject="x", body="y", source_id="frei")
    assert receivers(unassigned) == {"b-zuschauer", "a-admin", "kreis", "betreiber"}
    storage = Notice(event="storage_low", subject="x", body="y")
    assert receivers(storage) == {"kreis", "betreiber"}
    # Nur gewählte Ereignisse.
    assert receivers(Notice(event="unbekannt", subject="x", body="y")) == set()


def test_deliver_encrypts_and_removes_vanished_devices(push, auth) -> None:  # noqa: F811
    device = Device()
    subscribe(push, auth, "b-zuschauer", device=device)

    notice = Notice(event="source_offline", subject="Störung: Quelle „B1“ ohne Signal",
                    body="Kein Signal.\n\nDetails", source_id="b1")
    result = push.deliver(notice)

    assert result["sent"] == 1
    call = push.post.calls[0]
    assert call["url"] == ENDPOINT
    assert call["headers"]["Content-Encoding"] == "aes128gcm"
    assert call["headers"]["Urgency"] == "high"
    message = device.decrypt(call["data"])
    assert message["title"] == notice.subject
    assert message["body"] == "Kein Signal."
    assert message["tag"] == "source_offline:b1"
    assert push.subscriptions()[0]["last_success_at"]

    push.post.status = 410
    assert push.deliver(notice)["removed"] == 1
    assert push.subscriptions() == []


def test_failed_delivery_is_remembered(push, auth) -> None:  # noqa: F811
    subscribe(push, auth, "kreis")
    push.post.status = 500

    result = push.deliver(Notice(event="storage_low", subject="x", body="y"))

    assert result["failed"] == 1
    assert "HTTP 500" in push.subscriptions()[0]["last_error"]


def test_resubscribe_keeps_choice_and_renewed_subscription_takes_it_over(push, auth) -> None:  # noqa: F811
    device = Device()
    first = subscribe(push, auth, "kreis", device=device, events=["storage_low"])
    again = subscribe(push, auth, "kreis", device=device)
    assert again["id"] == first["id"] and again["events"] == ["storage_low"]

    renewed = Device("https://fcm.googleapis.com/fcm/send/erneuert")
    item = subscribe(push, auth, "kreis", device=renewed, replaces=device.endpoint)
    assert item["events"] == ["storage_low"]
    assert [entry["endpoint"] for entry in push.subscriptions()] == [renewed.endpoint]


def test_only_own_devices_can_be_changed(push, auth) -> None:  # noqa: F811
    item = subscribe(push, auth, "kreis")
    with pytest.raises(LookupError):
        push.unsubscribe(session(auth, "b-zuschauer"), item["id"])
    push.unsubscribe(session(auth, "kreis"), item["id"])
    assert push.subscriptions() == []


def test_deleted_account_loses_its_devices(push, auth) -> None:  # noqa: F811
    subscribe(push, auth, "b-zuschauer")
    user_id = session(auth, "b-zuschauer")["user_id"]
    auth.ready().delete_user(user_id)
    assert push.subscriptions() == []


def test_monitor_names_the_affected_source() -> None:
    monitor = NotificationMonitor(source_delay=0)
    online = {"sources": [{"id": "b1", "name": "B1", "online": True}],
              "services": {"mediamtx": {"online": True}}}
    offline = {"sources": [{"id": "b1", "name": "B1", "online": False}],
               "services": {"mediamtx": {"online": True}}}
    monitor.evaluate(online, 0)
    notices = [item for item in monitor.evaluate(offline, 1) if item.event == "source_offline"]
    assert notices and notices[0].source_id == "b1"


# ----------------------------------------------------------------------
# Schnittstelle und Service Worker
# ----------------------------------------------------------------------


@pytest.fixture
def api(auth, tmp_path: Path, monkeypatch):  # noqa: F811
    from fastapi.testclient import TestClient

    from open_bos_stream.api import push as push_api
    from open_bos_stream.core import container
    from open_bos_stream.main import app

    real = container.auth_service
    for name in ("org", "_ready", "users_file", "secret_file", "revoked_file", "_secret_cache"):
        monkeypatch.setattr(real, name, getattr(auth, name))
    ids = build(real)
    post = FakePost()
    service = PushService(
        SimpleNamespace(sources=[source("b1", ids["b"])]),
        real,
        key_file=tmp_path / "webpush.key",
        post=post,
    )
    monkeypatch.setattr(push_api, "push_service", service)
    client = TestClient(app)

    def login(username: str) -> None:
        client.cookies.clear()
        client.cookies.set(real.COOKIE_NAME, real.create_token(real.authenticate(username, PASSWORD)))

    client.login = login
    client.post_calls = post.calls
    return client


def test_push_api_round_trip(api) -> None:
    api.login("b-zuschauer")
    overview = api.get("/api/push").json()
    assert overview["public_key"]
    assert [item["key"] for item in overview["events"]] == ["incident_started", "source_offline", "recording_problem"]

    assert api.post("/api/push/test").status_code == 422

    device = Device()
    created = api.post("/api/push/subscriptions", json={**device.json(), "label": "iPhone · App"})
    assert created.status_code == 200
    item = created.json()["subscription"]
    assert item["label"] == "iPhone · App" and item["service"] == "fcm.googleapis.com"

    tested = api.post("/api/push/test")
    assert tested.status_code == 200
    assert device.decrypt(api.post_calls[-1]["data"])["title"] == "Testbenachrichtigung"

    changed = api.put(f"/api/push/subscriptions/{item['id']}", json={"events": ["recording_problem"]})
    assert changed.json()["subscription"]["events"] == ["recording_problem"]

    api.login("kreis")
    assert api.get("/api/push").json()["subscriptions"] == []
    assert api.delete(f"/api/push/subscriptions/{item['id']}").status_code == 404

    api.login("b-zuschauer")
    assert api.delete(f"/api/push/subscriptions/{item['id']}").status_code == 200


def test_push_api_rejects_unknown_push_service(api) -> None:
    api.login("kreis")
    data = Device("https://intern.local/push").json()
    assert api.post("/api/push/subscriptions", json=data).status_code == 422


def test_service_worker_is_served_publicly_at_the_root(api) -> None:
    api.cookies.clear()
    response = api.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.headers["service-worker-allowed"] == "/"
    assert "showNotification" in response.text


def test_service_worker_uses_logo_and_transparent_badge() -> None:
    static = Path("src/open_bos_stream/static")
    worker = (static / "js/service-worker.js").read_text(encoding="utf-8")
    assert 'icon: "/static/icons/open-bos-stream-192.png"' in worker
    assert 'badge: "/static/icons/open-bos-stream-badge-96.png"' in worker
    # PNG-Farbtyp 6 = RGBA; ohne Transparenz zeigt Android nur ein Quadrat.
    badge = (static / "icons/open-bos-stream-badge-96.png").read_bytes()
    assert badge[25] == 6
