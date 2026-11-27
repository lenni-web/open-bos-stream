from __future__ import annotations

import logging
import time

from open_bos_stream.auth.service import AuthService
from open_bos_stream.db.database import Database
from open_bos_stream.logging.logger import SecretPathFilter, redact_secrets
from open_bos_stream.system.administration import SystemAdministrationService

PASSWORD = "sicheres-passwort"


def test_production_uses_owasp_iterations() -> None:
    assert AuthService.production_iterations == 600_000


def test_old_hash_is_upgraded_on_login(tmp_path, monkeypatch) -> None:
    auth = AuthService(str(tmp_path / "users.yaml"), str(tmp_path / "auth.secret"), database=Database(None))
    monkeypatch.setattr(AuthService, "PASSWORD_ITERATIONS", 1_000)
    auth.create_user("alt", PASSWORD, "superadmin", initial=True)
    assert auth.ready().user_by_username("alt")["password_hash"].startswith("pbkdf2_sha256$1000$")

    monkeypatch.setattr(AuthService, "PASSWORD_ITERATIONS", 2_000)
    assert auth.authenticate("alt", PASSWORD) is not None
    assert auth.ready().user_by_username("alt")["password_hash"].startswith("pbkdf2_sha256$2000$")
    # Neue Sitzung passt zum neuen Hash.
    token = auth.create_token(auth.authenticate("alt", PASSWORD))
    assert auth.verify_token(token)["username"] == "alt"


def test_unknown_user_costs_a_password_check(tmp_path, monkeypatch) -> None:
    auth = AuthService(str(tmp_path / "users.yaml"), str(tmp_path / "auth.secret"), database=Database(None))
    auth.create_user("vorhanden", PASSWORD, "superadmin", initial=True)
    checks = []
    original = AuthService._verify_password.__func__
    monkeypatch.setattr(AuthService, "_verify_password", classmethod(
        lambda cls, password, encoded: checks.append(encoded) or original(cls, password, encoded)
    ))
    assert auth.authenticate("gibt-es-nicht", PASSWORD) is None
    assert len(checks) == 1 and checks[0].startswith("pbkdf2_sha256$")


def test_guest_codes_and_tokens_are_masked_in_logs() -> None:
    assert redact_secrets("GET /g/AbC-12_xyz HTTP/1.1") == "GET /g/*** HTTP/1.1"
    assert redact_secrets("/whep/x?token=geheim&a=1") == "/whep/x?token=***&a=1"
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1,
        '%s - "%s %s HTTP/%s" %d', ("127.0.0.1:1", "GET", "/g/geheimcode", "1.1", 303), None,
    )
    SecretPathFilter().filter(record)
    assert "geheimcode" not in record.getMessage()
    assert SystemAdministrationService.redact_log("GET /g/geheimcode 303") == "GET /g/*** 303"
