"""Push-Benachrichtigungen: Geräte des eigenen Kontos verwalten."""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from open_bos_stream.auth.roles import VIEWER
from open_bos_stream.core.container import push_service
from open_bos_stream.notifications.push_service import PushError, available_events

router = APIRouter(
    dependencies=[VIEWER],
    prefix="/api/push",
    tags=["Push-Benachrichtigungen"],
)


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(max_length=120)
    auth: str = Field(max_length=40)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(max_length=1000)
    keys: SubscriptionKeys
    label: str = Field(default="", max_length=80)
    events: list[str] | None = Field(default=None, max_length=20)
    replaces: str | None = Field(default=None, max_length=1000)


class EventsIn(BaseModel):
    events: list[str] = Field(max_length=20)


def _account(request: Request) -> dict:
    user = request.state.user
    # Gäste und das lokale Display haben kein eigenes Konto.
    if not user.get("user_id"):
        raise HTTPException(
            status_code=403,
            detail="Push-Benachrichtigungen gibt es nur für angemeldete Konten.",
        )
    return user


def _public(item: dict) -> dict:
    return {
        "id": item["id"],
        "label": item["label"],
        "events": item["events"],
        "endpoint": item["endpoint"],
        "service": urlsplit(item["endpoint"]).hostname or "",
        "created_at": item["created_at"],
        "last_success_at": item["last_success_at"],
        "last_error": item["last_error"],
    }


@router.get("")
async def push_overview(request: Request) -> dict:
    user = _account(request)
    public_key = await run_in_threadpool(lambda: push_service.public_key)
    devices = await run_in_threadpool(push_service.subscriptions, user["user_id"])
    return {
        "public_key": public_key,
        "events": [
            {"key": key, "label": label}
            for key, label in available_events(user).items()
        ],
        "subscriptions": [_public(item) for item in devices],
    }


@router.post("/subscriptions")
async def subscribe(update: SubscriptionIn, request: Request) -> dict:
    user = _account(request)
    try:
        item = await run_in_threadpool(
            lambda: push_service.subscribe(
                user,
                endpoint=update.endpoint,
                p256dh=update.keys.p256dh,
                auth=update.keys.auth,
                label=update.label,
                events=update.events,
                replaces=update.replaces,
            )
        )
    except PushError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "subscription": _public(item)}


@router.put("/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: int,
    update: EventsIn,
    request: Request,
) -> dict:
    user = _account(request)
    try:
        item = await run_in_threadpool(
            push_service.update_events,
            user,
            subscription_id,
            update.events,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "subscription": _public(item)}


@router.delete("/subscriptions/{subscription_id}")
async def unsubscribe(subscription_id: int, request: Request) -> dict:
    user = _account(request)
    try:
        await run_in_threadpool(push_service.unsubscribe, user, subscription_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True}


@router.post("/test")
async def send_test(request: Request) -> dict:
    user = _account(request)
    try:
        result = await run_in_threadpool(push_service.send_test, user)
    except PushError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not result["sent"]:
        detail = (
            result["errors"][0]
            if result["errors"]
            else "Kein angemeldetes Gerät mehr erreichbar."
        )
        raise HTTPException(status_code=502, detail=detail)
    message = (
        "Testbenachrichtigung an 1 Gerät gesendet."
        if result["sent"] == 1
        else f"Testbenachrichtigung an {result['sent']} Geräte gesendet."
    )
    if result["failed"]:
        message += f" {result['failed']} Gerät(e) nicht erreicht."
    return {"success": True, "message": message, **result}
