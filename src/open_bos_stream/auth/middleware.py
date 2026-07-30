from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from open_bos_stream.auth.service import AuthService


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
SUPERADMIN_PREFIXES = (
    "/display",
    "/web-access",
    "/stream-output",
    "/auth/users",
    "/media",
    "/recording",
    "/snapshot",
)
SUPERADMIN_PATHS = {
    "/config/restore",
}


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
                secure=False,
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

        mutation = request.method not in {"GET", "HEAD", "OPTIONS"}
        if mutation and not self.service.has_role(user, "admin"):
            return JSONResponse(
                {"detail": "Für diese Aktion ist die Rolle Admin erforderlich."},
                status_code=403,
            )
        if (
            (
                path.startswith(SUPERADMIN_PREFIXES)
                or path in SUPERADMIN_PATHS
            )
            and not self.service.has_role(user, "superadmin")
        ):
            return JSONResponse(
                {"detail": "Diese Aktion ist Superadmins vorbehalten."},
                status_code=403,
            )

        return await call_next(request)
