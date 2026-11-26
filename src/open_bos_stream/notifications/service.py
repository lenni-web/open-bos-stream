"""Versendet Störungsmeldungen per E-Mail im Hintergrund.

Der Versand läuft in einem eigenen Thread mit Warteschlange und Zeitlimit.
Ein langsamer oder nicht erreichbarer Mailserver bremst Streaming,
Aufnahme und Weboberfläche dadurch nie aus. Das SMTP-Passwort liegt
getrennt von stream.yaml in einer Datei mit Rechten 0600.
"""

from __future__ import annotations

import logging
import os
import queue
import socket
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

from open_bos_stream.core.installation import server_access_settings
from open_bos_stream.core.models import AppConfig, NotificationConfig
from open_bos_stream.notifications.mailer import MailDeliveryError, send_mail
from open_bos_stream.notifications.monitor import Notice
from open_bos_stream.version import VERSION

logger = logging.getLogger(__name__)

QUEUE_LIMIT = 50


class NotificationService:
    def __init__(
        self,
        config: AppConfig,
        secret_file: str | Path = "config/notifications.secret",
        sender=send_mail,
        event_log=None,
    ) -> None:
        self._config = config
        self._secret_file = Path(secret_file)
        self._send = sender
        self._queue: queue.Queue[Notice] = queue.Queue(maxsize=QUEUE_LIMIT)
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_result: dict | None = None
        self._events = event_log

    # ------------------------------------------------------------------
    # Einstellungen und Passwort
    # ------------------------------------------------------------------

    @property
    def settings(self) -> NotificationConfig:
        return self._config.notifications

    def password(self) -> str:
        try:
            return self._secret_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    @property
    def password_set(self) -> bool:
        return bool(self.password())

    def set_password(self, password: str | None, *, clear: bool = False) -> None:
        """Neues Passwort speichern; leer lassen behält das bisherige."""

        if clear:
            self._secret_file.unlink(missing_ok=True)
            return
        if not password:
            return
        if "\n" in password or "\r" in password:
            raise ValueError("Das Passwort darf keine Zeilenumbrüche enthalten.")
        self._secret_file.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{self._secret_file.name}.",
            dir=self._secret_file.parent,
        )
        try:
            os.chmod(temporary, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(password)
            os.replace(temporary, self._secret_file)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def status(self) -> dict:
        with self._lock:
            return dict(self._last_result) if self._last_result else {}

    # ------------------------------------------------------------------
    # Meldungen
    # ------------------------------------------------------------------

    def enqueue(self, notice: Notice) -> bool:
        settings = self.settings
        if not settings.enabled:
            return False
        if not getattr(settings.events, notice.event, False):
            return False
        try:
            self._queue.put_nowait(notice)
        except queue.Full:
            logger.warning(
                "Benachrichtigung verworfen, Warteschlange voll: %s",
                notice.subject,
            )
            return False
        self._ensure_worker()
        return True

    def send_test(self, settings: NotificationConfig | None = None) -> None:
        """Testnachricht synchron senden; Fehler gehen an den Aufrufer."""

        settings = settings or self.settings
        if not settings.smtp_host or not settings.sender or not settings.recipients:
            raise MailDeliveryError(
                "SMTP-Server, Absender und mindestens ein Empfänger sind "
                "erforderlich."
            )
        subject, body = self._compose(
            Notice(
                event="test",
                subject="Testnachricht",
                body=(
                    "Diese Testnachricht bestätigt, dass Open BOS Drohnen "
                    "Störungsmeldungen per E-Mail versenden kann."
                ),
            )
        )
        try:
            self._send(settings, self.password(), subject, body)
        except MailDeliveryError as exc:
            self._remember(subject, error=str(exc))
            raise
        self._remember(subject)

    # ------------------------------------------------------------------

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._run,
                name="open-bos-notifications",
                daemon=True,
            )
            self._worker.start()

    def _run(self) -> None:
        while True:
            notice = self._queue.get()
            subject, body = self._compose(notice)
            try:
                self._send(self.settings, self.password(), subject, body)
            except MailDeliveryError as exc:
                logger.warning(
                    "Benachrichtigung „%s“ nicht versendet: %s",
                    notice.subject,
                    exc,
                )
                self._remember(subject, error=str(exc))
            except Exception:
                logger.exception("Benachrichtigung fehlgeschlagen.")
                self._remember(subject, error="Interner Fehler beim Versand.")
            else:
                logger.info("Benachrichtigung versendet: %s", notice.subject)
                self._remember(subject)
            finally:
                self._queue.task_done()

    def _remember(self, subject: str, *, error: str | None = None) -> None:
        with self._lock:
            self._last_result = {
                "at": time.time(),
                "subject": subject,
                "success": error is None,
                "error": error,
            }
        if self._events is not None:
            # Betreff ohne Serverkennung "[Open BOS Drohnen …]".
            short = subject.split("] ", 1)[-1]
            if error is None:
                self._events.record("info", f"✉ E-Mail versendet: {short}")
            else:
                self._events.record(
                    "error",
                    f"✉ E-Mail nicht versendet: {short} ({error})",
                )

    @staticmethod
    def _server_label() -> tuple[str, str | None]:
        settings = server_access_settings()
        domain = settings.get("public_domain") or ""
        if domain:
            scheme = "https" if settings.get("https_enabled") == "yes" else "http"
            return domain, f"{scheme}://{domain}/"
        return socket.gethostname(), None

    def _compose(self, notice: Notice) -> tuple[str, str]:
        label, url = self._server_label()
        subject = f"[Open BOS Drohnen {label}] {notice.subject}"
        lines = [
            notice.body,
            "",
            f"Zeitpunkt: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
            f"Server: {label} (Version {VERSION})",
        ]
        if url:
            lines.append(f"Übersicht: {url}")
        lines += [
            "",
            "Diese Nachricht wurde automatisch von Open BOS Drohnen "
            "versendet. Die Benachrichtigungen lassen sich in den "
            "Einstellungen anpassen.",
        ]
        return subject, "\n".join(lines)
