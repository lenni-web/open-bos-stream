import logging
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from open_bos_stream.auth.middleware import secure_cookies
from open_bos_stream.auth.service import AuthError
from open_bos_stream.core.container import (
    auth_service,
    config,
    login_rate_limiter,
)
from open_bos_stream.auth.guest_access import (
    allowed_media_paths,
    is_guest,
    media_uri_allowed,
)
from open_bos_stream.auth.roles import GUEST, PUBLIC


router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


class Credentials(BaseModel):
    # Benutzername oder E-Mail-Adresse.
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class SetupRequest(Credentials):
    setup_code: str = Field(default="", max_length=32)


@router.get("/status", dependencies=[PUBLIC])
async def status(request: Request):
    return {
        "configured": auth_service.configured,
        "user": getattr(request.state, "user", None),
    }


@router.post("/setup", dependencies=[PUBLIC])
async def setup(payload: SetupRequest, request: Request, response: Response):
    # Der Einrichtungscode steht im Journal bzw. in config/setup.code und
    # verhindert, dass ein Fremder einen frisch installierten Server übernimmt.
    try:
        user = auth_service.complete_setup(
            payload.username,
            payload.password,
            payload.setup_code,
        )
    except AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _set_session(request, response, auth_service.create_token(user))
    return {"success": True, "user": user}


@router.post("/login", dependencies=[PUBLIC])
async def login(payload: Credentials, request: Request, response: Response):
    client_ip = request.client.host if request.client else "unknown"
    login_name = auth_service.login_name(payload.username)
    retry_after = login_rate_limiter.retry_after(
        login_name,
        client_ip,
    )
    if retry_after:
        logger.warning(
            "Anmeldung vorübergehend gesperrt: Benutzer %r, IP %s, "
            "Restzeit %ss",
            login_name,
            client_ip,
            retry_after,
        )
        raise HTTPException(
            status_code=429,
            detail=(
                "Zu viele fehlgeschlagene Anmeldungen. "
                "Bitte später erneut versuchen."
            ),
            headers={"Retry-After": str(retry_after)},
        )
    user = auth_service.authenticate(payload.username, payload.password)
    if not user:
        retry_after = login_rate_limiter.record_failure(
            login_name,
            client_ip,
        )
        logger.warning(
            "Fehlgeschlagene Anmeldung: Benutzer %r, IP %s%s",
            login_name,
            client_ip,
            (
                f", für {retry_after}s gesperrt"
                if retry_after
                else ""
            ),
        )
        raise HTTPException(
            status_code=401,
            detail="Benutzername, E-Mail oder Passwort ist falsch.",
        )
    login_rate_limiter.record_success(login_name, client_ip)
    _set_session(request, response, auth_service.create_token(user))
    return {"success": True, "user": user}


@router.get("/media-access", status_code=204, dependencies=[GUEST])
async def media_access(request: Request):
    """Sitzungsprüfung für Caddys HLS-/WHEP-Weiterleitung.

    Gäste erhalten nur die Streams der Drohnen ihres Gastlinks. Caddy
    reicht die angefragte Adresse in X-Forwarded-Uri weiter.
    """

    user = request.state.user
    allowed = allowed_media_paths(user, config)
    if allowed is not None:
        uri = request.headers.get("x-forwarded-uri", "")
        if not media_uri_allowed(uri, allowed):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Dieser Stream ist für den Gastzugang nicht freigegeben."
                    if is_guest(user)
                    else "Dieser Stream gehört zu einer anderen Organisation."
                ),
            )
    return Response(status_code=204)


@router.get("/media-token", dependencies=[GUEST])
async def media_token(request: Request):
    """Token für direkte WHEP-/HLS-Abrufe bei MediaMTX ohne Caddy."""

    user = request.state.user
    try:
        token = auth_service.create_media_token(user)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    expires_in = (
        max(0, int(user["expires_at"] - time.time()))
        if is_guest(user)
        else auth_service.SESSION_SECONDS
    )
    return {"token": token, "expires_in": expires_in}


@router.post("/logout", dependencies=[PUBLIC])
async def logout(request: Request, response: Response):
    # Die Sitzung wird serverseitig widerrufen, nicht nur das Cookie gelöscht.
    auth_service.revoke_token(request.cookies.get(auth_service.COOKIE_NAME))
    response.delete_cookie(auth_service.COOKIE_NAME, path="/")
    return {"success": True}


def _set_session(request: Request, response: Response, token: str) -> None:
    response.set_cookie(
        auth_service.COOKIE_NAME,
        token,
        max_age=auth_service.SESSION_SECONDS,
        httponly=True,
        samesite="strict",
        secure=secure_cookies(request),
        path="/",
    )
