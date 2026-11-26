"""Versand einzelner Nachrichten über SMTP."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from open_bos_stream.core.models import NotificationConfig

SMTP_TIMEOUT_SECONDS = 15


class MailDeliveryError(RuntimeError):
    """Die Nachricht konnte nicht zugestellt werden."""


def build_message(
    config: NotificationConfig,
    subject: str,
    body: str,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = config.sender
    message["To"] = ", ".join(config.recipients)
    # Betreff einzeilig halten: kein Header-Einschleusen über Quellennamen.
    message["Subject"] = " ".join(subject.split())
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain="open-bos-stream")
    message.set_content(body)
    return message


def send_mail(
    config: NotificationConfig,
    password: str,
    subject: str,
    body: str,
    *,
    smtp_factory=None,
) -> None:
    """Sendet eine Nachricht; Fehler werden als MailDeliveryError gemeldet."""

    message = build_message(config, subject, body)
    context = ssl.create_default_context()
    try:
        if smtp_factory is not None:
            client = smtp_factory(config)
        elif config.security == "ssl":
            client = smtplib.SMTP_SSL(
                config.smtp_host,
                config.smtp_port,
                timeout=SMTP_TIMEOUT_SECONDS,
                context=context,
            )
        else:
            client = smtplib.SMTP(
                config.smtp_host,
                config.smtp_port,
                timeout=SMTP_TIMEOUT_SECONDS,
            )
        with client:
            if config.security == "starttls":
                client.starttls(context=context)
            if config.username:
                client.login(config.username, password)
            client.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise MailDeliveryError(
            "Anmeldung am SMTP-Server fehlgeschlagen. Benutzername und "
            "Passwort prüfen."
        ) from exc
    except smtplib.SMTPNotSupportedError as exc:
        raise MailDeliveryError(
            "Der SMTP-Server unterstützt die gewählte Verschlüsselung oder "
            "Anmeldung nicht."
        ) from exc
    except smtplib.SMTPRecipientsRefused as exc:
        raise MailDeliveryError(
            "Der SMTP-Server hat die Empfänger abgelehnt."
        ) from exc
    except smtplib.SMTPException as exc:
        raise MailDeliveryError(f"SMTP-Fehler: {exc}") from exc
    except ssl.SSLError as exc:
        raise MailDeliveryError(
            f"Verschlüsselte Verbindung fehlgeschlagen: {exc.reason or exc}"
        ) from exc
    except OSError as exc:
        raise MailDeliveryError(
            f"SMTP-Server {config.smtp_host}:{config.smtp_port} nicht "
            f"erreichbar: {exc.strerror or exc}"
        ) from exc
