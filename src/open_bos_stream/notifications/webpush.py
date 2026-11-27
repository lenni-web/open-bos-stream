"""Web Push nach RFC 8291 (Verschlüsselung) und RFC 8292 (VAPID).

Eigene, kleine Umsetzung auf Basis von ``cryptography`` statt pywebpush,
damit keine weiteren Abhängigkeiten (z. B. aiohttp) auf den Server kommen.
Die Nachricht wird für genau ein Gerät verschlüsselt; der Push-Dienst des
Browsers (Google, Mozilla, Apple, Microsoft) sieht nur den Geheimtext.
"""

from __future__ import annotations

import base64
import json
import os
import struct
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Push-Dienste der gängigen Browser. Andere Ziele werden abgelehnt, damit
# der Server nicht als Sprungbrett für Anfragen ins interne Netz dient.
PUSH_SERVICE_HOSTS = (
    "fcm.googleapis.com",          # Chrome, Edge (Android), Samsung, Opera
    "push.services.mozilla.com",   # Firefox
    "push.apple.com",              # Safari (macOS, iOS ab 16.4)
    "notify.windows.com",          # Edge (Windows)
)

RECORD_SIZE = 4096
# Nutzdaten deutlich unter der Grenze der Push-Dienste (4 KB) halten.
MAX_PAYLOAD_BYTES = 3000
JWT_LIFETIME_SECONDS = 12 * 60 * 60


class WebPushError(Exception):
    """Versand an ein Gerät fehlgeschlagen."""

    def __init__(self, message: str, *, gone: bool = False) -> None:
        super().__init__(message)
        # Abo existiert beim Push-Dienst nicht mehr und kann weg.
        self.gone = gone


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    text = str(text or "").strip()
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def endpoint_allowed(endpoint: str) -> bool:
    try:
        parts = urlsplit(endpoint)
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or parts.port not in (None, 443):
        return False
    if parts.username or parts.password:
        return False
    return any(
        host == allowed or host.endswith("." + allowed)
        for allowed in PUSH_SERVICE_HOSTS
    )


def valid_client_keys(p256dh: str, auth: str) -> bool:
    try:
        public = b64url_decode(p256dh)
        secret = b64url_decode(auth)
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), public)
    except (ValueError, TypeError):
        return False
    return len(public) == 65 and len(secret) == 16


def _hmac(key: bytes, data: bytes) -> bytes:
    mac = hmac.HMAC(key, hashes.SHA256())
    mac.update(data)
    return mac.finalize()


def _raw_public(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )


def encrypt(
    payload: bytes,
    p256dh: str,
    auth: str,
    *,
    salt: bytes | None = None,
    sender_key: ec.EllipticCurvePrivateKey | None = None,
) -> bytes:
    """Nachricht im Format ``aes128gcm`` für ein Abo verschlüsseln."""

    receiver_raw = b64url_decode(p256dh)
    receiver = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(),
        receiver_raw,
    )
    auth_secret = b64url_decode(auth)
    sender_key = sender_key or ec.generate_private_key(ec.SECP256R1())
    sender_raw = _raw_public(sender_key.public_key())
    salt = salt or os.urandom(16)

    shared = sender_key.exchange(ec.ECDH(), receiver)
    prk_key = _hmac(auth_secret, shared)
    ikm = _hmac(
        prk_key,
        b"WebPush: info\x00" + receiver_raw + sender_raw + b"\x01",
    )
    prk = _hmac(salt, ikm)
    cek = _hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
    nonce = _hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12]
    # 0x02 kennzeichnet den letzten (einzigen) Datensatz.
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    header = salt + struct.pack("!IB", RECORD_SIZE, len(sender_raw)) + sender_raw
    return header + ciphertext


@dataclass
class VapidKey:
    """Schlüsselpaar, mit dem sich der Server bei Push-Diensten ausweist."""

    private_key: ec.EllipticCurvePrivateKey

    @classmethod
    def load_or_create(cls, path: str | Path) -> "VapidKey":
        path = Path(path)
        if path.exists():
            key = serialization.load_pem_private_key(path.read_bytes(), None)
            if not isinstance(key, ec.EllipticCurvePrivateKey):
                raise ValueError(f"{path} enthält keinen EC-Schlüssel.")
            return cls(key)
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=path.parent,
        )
        try:
            os.chmod(temporary, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(pem)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        return cls(key)

    @property
    def public_key(self) -> str:
        """Öffentlicher Schlüssel für ``applicationServerKey`` im Browser."""

        return b64url_encode(_raw_public(self.private_key.public_key()))

    def authorization(self, endpoint: str, subject: str, now: float | None = None) -> str:
        parts = urlsplit(endpoint)
        claims = {
            "aud": f"{parts.scheme}://{parts.netloc}",
            "exp": int((now or time.time()) + JWT_LIFETIME_SECONDS),
            "sub": subject,
        }
        header = {"typ": "JWT", "alg": "ES256"}
        signing_input = (
            b64url_encode(json.dumps(header, separators=(",", ":")).encode())
            + "."
            + b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
        )
        der = self.private_key.sign(
            signing_input.encode("ascii"),
            ec.ECDSA(hashes.SHA256()),
        )
        r, s = decode_dss_signature(der)
        signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        token = signing_input + "." + b64url_encode(signature)
        return f"vapid t={token}, k={self.public_key}"


def send(
    post,
    vapid: VapidKey,
    subscription: dict,
    message: dict,
    *,
    subject: str,
    ttl: int = 3600,
    urgency: str = "high",
    timeout: float = 10,
) -> None:
    """Eine Nachricht an ein Abo senden; Fehler als ``WebPushError``."""

    endpoint = subscription["endpoint"]
    if not endpoint_allowed(endpoint):
        raise WebPushError("Unbekannter Push-Dienst.", gone=True)
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise WebPushError("Nachricht zu groß für Web Push.")
    body = encrypt(payload, subscription["p256dh"], subscription["auth"])
    headers = {
        "Authorization": vapid.authorization(endpoint, subject),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(int(ttl)),
        "Urgency": urgency,
    }
    topic = message.get("tag")
    if topic:
        # Neuere Meldung zum selben Thema ersetzt eine noch nicht zugestellte.
        headers["Topic"] = b64url_encode(
            _hmac(b"open-bos-topic", str(topic).encode())
        )[:32]
    try:
        response = post(
            endpoint,
            data=body,
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
        )
    except Exception as exc:  # Netzwerkfehler, Zeitüberschreitung
        raise WebPushError(f"Push-Dienst nicht erreichbar ({type(exc).__name__}).") from exc
    status = getattr(response, "status_code", 0)
    if 200 <= status < 300:
        return
    if status in (404, 410):
        raise WebPushError("Gerät ist nicht mehr angemeldet.", gone=True)
    if status in (401, 403):
        raise WebPushError(f"Push-Dienst hat den Serverschlüssel abgelehnt (HTTP {status}).")
    if status == 413:
        raise WebPushError("Nachricht zu groß für den Push-Dienst.")
    if status == 429:
        raise WebPushError("Push-Dienst meldet zu viele Anfragen (HTTP 429).")
    raise WebPushError(f"Push-Dienst antwortet mit HTTP {status}.")
