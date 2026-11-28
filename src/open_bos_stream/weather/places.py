"""Orte, für die ein Konto das Wetter ansehen kann.

Reihenfolge der Liste: laufende Einsätze, eigene Wache(n), Standardort der
Servereinstellungen. Der Gerätestandort kommt allein aus dem Browser.
"""

from __future__ import annotations


def _located(item: dict) -> bool:
    return item.get("latitude") is not None and item.get("longitude") is not None


def _place(key: str, kind: str, name: str, item: dict) -> dict:
    return {
        "key": key,
        "origin": kind,
        "name": name,
        "latitude": item["latitude"],
        "longitude": item["longitude"],
    }


def weather_places(user: dict, org, incidents, fallback: dict) -> tuple[list[dict], str]:
    """Wählbare Orte und der Schlüssel der automatischen Wahl.

    Automatisch gilt: Einsatz mit Beteiligung der eigenen Wehr, sonst eigene
    Wache, sonst Standardort. Andere sichtbare Einsätze bleiben wählbar, damit
    z. B. Kreis-Admins nicht ungefragt woandershin springen.
    """

    default = fallback | {"key": "default"}
    if default.get("name") in (None, "", "Kartenmitte"):
        default["name"] = "Standardstandort"
    if not user or user.get("role") == "guest" or user.get("user_id") is None:
        return [default], "default"

    organizations = {item["id"]: item for item in org.organizations()}
    own = [item["organization_id"] for item in org.memberships(user["user_id"])]

    running = [
        item for item in incidents.visible(user, status="running") if _located(item)
    ]
    incident_places = [
        _place(
            f"incident:{item['id']}",
            "incident",
            "Einsatz " + (item["address"] or item["title"] or item["keyword"] or item["code"]),
            item,
        )
        for item in running
    ]

    stations: dict[int, dict] = {}
    for organization_id in own:
        # Ohne eigenen Pin zählt der Standort der übergeordneten Organisation.
        current = organizations.get(organization_id)
        while current is not None and not _located(current):
            current = organizations.get(current["parent_id"])
        if current is not None:
            stations[current["id"]] = _place(
                f"station:{current['id']}",
                "station",
                "Wache " + (current["short_name"] or current["name"]),
                current,
            )

    places = [*incident_places, *stations.values(), default]
    involved = next(
        (
            f"incident:{item['id']}"
            for item in running
            if set(item["organization_ids"]) & set(own)
        ),
        None,
    )
    station = next((item["key"] for item in stations.values()), None)
    return places, involved or station or "default"
