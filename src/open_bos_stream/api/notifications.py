"""Einstellungen und Testversand der E-Mail-Benachrichtigungen."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from open_bos_stream.auth.roles import SUPERADMIN
from open_bos_stream.core.container import (
    config_apply_service,
    notification_service,
)
from open_bos_stream.core.models import NotificationConfig
from open_bos_stream.notifications.mailer import MailDeliveryError

router = APIRouter(
    dependencies=[SUPERADMIN],
    prefix="/config/notifications",
    tags=["Benachrichtigungen"],
)


class NotificationUpdate(NotificationConfig):
    """Einstellungen plus optionales neues Passwort.

    Ein leeres Passwort behält das gespeicherte; ``clear_password`` löscht
    es. Das gespeicherte Passwort wird nie an den Browser ausgeliefert.
    """

    password: str | None = Field(default=None, max_length=255)
    clear_password: bool = False


def _settings_payload() -> dict:
    return {
        **notification_service.settings.model_dump(),
        "password_set": notification_service.password_set,
        "last_result": notification_service.status() or None,
    }


@router.get("")
async def get_notifications() -> dict:
    return _settings_payload()


@router.put("")
async def save_notifications(update: NotificationUpdate) -> dict:
    settings = NotificationConfig.model_validate(
        update.model_dump(exclude={"password", "clear_password"})
    )
    try:
        await run_in_threadpool(
            notification_service.set_password,
            update.password,
            clear=update.clear_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await run_in_threadpool(
        config_apply_service.update_notifications,
        settings,
    )
    return {
        "success": True,
        "message": "Benachrichtigungen wurden gespeichert.",
        "notifications": _settings_payload(),
    }


@router.post("/test")
async def send_test_notification() -> dict:
    try:
        await run_in_threadpool(notification_service.send_test)
    except MailDeliveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    recipients = ", ".join(notification_service.settings.recipients)
    return {
        "success": True,
        "message": f"Testnachricht an {recipients} versendet.",
    }
