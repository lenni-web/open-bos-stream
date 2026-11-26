"""Rollenprüfung pro Endpunkt.

Jeder Endpunkt deklariert seine Mindestrolle als FastAPI-Abhängigkeit, am
Router oder an der Route. Ein Test stellt sicher, dass keine Route ohne
diese Angabe existiert; neue Endpunkte sind dadurch nie versehentlich offen.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from open_bos_stream.auth.service import ROLE_LEVEL


ROLE_MESSAGES = {
    "guest": "Anmeldung erforderlich.",
    "viewer": "Anmeldung erforderlich.",
    "operator": "Für diese Aktion ist die Rolle Drohnenteam erforderlich.",
    "admin": "Für diese Aktion ist die Rolle Admin erforderlich.",
    "superadmin": "Diese Aktion ist Superadmins vorbehalten.",
}


def _role_dependency(minimum: str):
    def dependency(request: Request) -> dict:
        user = getattr(request.state, "user", None)
        if not user or ROLE_LEVEL.get(user.get("role"), -1) < ROLE_LEVEL[minimum]:
            raise HTTPException(
                status_code=401 if not user else 403,
                detail=ROLE_MESSAGES[minimum],
            )
        return user

    dependency.minimum_role = minimum
    dependency.__name__ = f"require_{minimum}"
    return dependency


def _server_admin_dependency(request: Request) -> dict:
    """Kreis-Admin oder Superadmin: serverweite Einstellungen.

    Sitzungen aus Organisationen tragen ``server_admin``; ältere bzw.
    vereinfachte Benutzerangaben ohne Organisationsdaten gelten ab Admin.
    """

    user = _role_dependency("admin")(request)
    if "org_view" in user and not (
        user.get("server_admin") or user.get("role") == "superadmin"
    ):
        raise HTTPException(
            status_code=403,
            detail="Diese Einstellung gilt für den ganzen Server und ist "
            "Kreis-Admins vorbehalten.",
        )
    return user


_server_admin_dependency.minimum_role = "admin"


def _public_dependency() -> None:
    """Ausdrücklich öffentlicher Endpunkt (eigene Prüfung im Handler)."""


_public_dependency.minimum_role = "public"

GUEST = Depends(_role_dependency("guest"))
VIEWER = Depends(_role_dependency("viewer"))
ADMIN = Depends(_role_dependency("admin"))
SUPERADMIN = Depends(_role_dependency("superadmin"))
SERVER_ADMIN = Depends(_server_admin_dependency)
OPERATOR = Depends(_role_dependency("operator"))
PUBLIC = Depends(_public_dependency)


def route_roles(route) -> list[str]:
    """Deklarierte Rollen einer Route (für Tests und Diagnose)."""

    return [
        dependency.call.minimum_role
        for dependency in route.dependant.dependencies
        if hasattr(dependency.call, "minimum_role")
    ]
