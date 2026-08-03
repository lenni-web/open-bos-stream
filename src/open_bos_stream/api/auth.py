from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from open_bos_stream.auth.service import AuthError
from open_bos_stream.core.container import auth_service


router = APIRouter(prefix="/auth", tags=["Authentication"])


class Credentials(BaseModel):
    username: str
    password: str


class UserCreate(Credentials):
    role: str


class UserUpdate(BaseModel):
    role: str | None = None
    password: str | None = None


def _assert_admin_scope(
    request: Request,
    *,
    target_role: str | None = None,
    desired_role: str | None = None,
) -> None:
    """Verhindert Superadmin-Verwaltung durch normale Admins."""

    if request.state.user["role"] == "superadmin":
        return
    if target_role == "superadmin" or desired_role == "superadmin":
        raise HTTPException(
            status_code=403,
            detail=(
                "Admins dürfen keine Superadmin-Konten verwalten oder "
                "Superadmins anlegen."
            ),
        )


@router.get("/status")
async def status(request: Request):
    return {
        "configured": auth_service.configured,
        "user": getattr(request.state, "user", None),
    }


@router.post("/setup")
async def setup(payload: Credentials, response: Response):
    try:
        user = auth_service.create_user(
            payload.username,
            payload.password,
            "superadmin",
            initial=True,
        )
    except AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _set_session(response, auth_service.create_token(user))
    return {"success": True, "user": user}


@router.post("/login")
async def login(payload: Credentials, response: Response):
    user = auth_service.authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Benutzername oder Passwort ist falsch.",
        )
    _set_session(response, auth_service.create_token(user))
    return {"success": True, "user": user}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(auth_service.COOKIE_NAME, path="/")
    return {"success": True}


@router.get("/users")
async def users(request: Request):
    result = auth_service.users()
    if request.state.user["role"] != "superadmin":
        result = [item for item in result if item["role"] != "superadmin"]
    return result


@router.post("/users")
async def create_user(payload: UserCreate, request: Request):
    _assert_admin_scope(request, desired_role=payload.role)
    try:
        user = auth_service.create_user(
            payload.username,
            payload.password,
            payload.role,
        )
    except AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "user": user}


@router.delete("/users/{username}")
async def delete_user(username: str, request: Request):
    target = auth_service.user(username)
    if target is None:
        raise HTTPException(status_code=404, detail="Benutzer wurde nicht gefunden.")
    _assert_admin_scope(request, target_role=target["role"])
    try:
        auth_service.delete_user(
            username,
            request.state.user["username"],
        )
    except AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True}


@router.patch("/users/{username}")
async def update_user(
    username: str,
    payload: UserUpdate,
    request: Request,
):
    target = auth_service.user(username)
    if target is None:
        raise HTTPException(status_code=404, detail="Benutzer wurde nicht gefunden.")
    _assert_admin_scope(
        request,
        target_role=target["role"],
        desired_role=payload.role,
    )
    try:
        user = auth_service.update_user(
            username,
            role=payload.role,
            password=payload.password,
        )
    except AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "user": user}


def _set_session(response: Response, token: str) -> None:
    response.set_cookie(
        auth_service.COOKIE_NAME,
        token,
        max_age=auth_service.SESSION_SECONDS,
        httponly=True,
        samesite="strict",
        secure=False,
        path="/",
    )
