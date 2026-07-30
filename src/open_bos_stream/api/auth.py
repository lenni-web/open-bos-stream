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
async def users():
    return auth_service.users()


@router.post("/users")
async def create_user(payload: UserCreate):
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
    try:
        auth_service.delete_user(
            username,
            request.state.user["username"],
        )
    except AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True}


@router.patch("/users/{username}")
async def update_user(username: str, payload: UserUpdate):
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
