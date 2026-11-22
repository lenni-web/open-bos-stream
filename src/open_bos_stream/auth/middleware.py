from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from open_bos_stream.auth.service import AuthService
from open_bos_stream.display.ticket import TICKET_PARAMETER, ticket_valid


PUBLIC_PREFIXES = (
    "/static/",
    "/auth/status",
    "/auth/setup",
    "/auth/login",
    "/auth/logout",
    "/login",
    "/display/stream",
    "/internal/mediamtx/auth",
)


def secure_cookies(request: Request) -> bool:
    """Cookies nur über HTTPS mit dem Secure-Attribut ausliefern.

    Hinter Caddy liefert uvicorn das Schema aus X-Forwarded-Proto.
    """

    return request.url.scheme == "https"


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service: AuthService) -> None:
        super().__init__(app)
        self.service = service

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        user = self.service.verify_token(
            request.cookies.get(self.service.COOKIE_NAME)
        )
        request.state.user = user

        local_kiosk = (
            path == "/"
            and request.query_params.get("display") == "1"
            and request.client is not None
            and request.client.host in {"127.0.0.1", "::1"}
            and ticket_valid(request.query_params.get(TICKET_PARAMETER))
        )
        if local_kiosk:
            request.state.user = {
                "username": "Lokales Display",
                "role": "viewer",
            }
            response = await call_next(request)
            response.set_cookie(
                self.service.COOKIE_NAME,
                self.service.create_display_token(),
                max_age=self.service.SESSION_SECONDS,
                httponly=True,
                samesite="strict",
                secure=secure_cookies(request),
                path="/",
            )
            return response

        if path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)

        if not self.service.configured:
            if path == "/" or "text/html" in request.headers.get("accept", ""):
                return RedirectResponse("/login?setup=1", status_code=303)
            return JSONResponse(
                {"detail": "Ersteinrichtung erforderlich."},
                status_code=401,
            )

        if not user:
            if path == "/" or "text/html" in request.headers.get("accept", ""):
                return RedirectResponse("/login", status_code=303)
            return JSONResponse(
                {"detail": "Anmeldung erforderlich."},
                status_code=401,
            )

        # Die Rolle prüft jeder Endpunkt selbst (auth/roles.py).
        return await call_next(request)
