from open_bos_stream.weather.places import weather_places

FALLBACK = {"latitude": 53.56, "longitude": 9.53, "name": "Kartenmitte", "origin": "map"}


def organization(identifier, parent=None, position=None, name="Wehr"):
    latitude, longitude = position or (None, None)
    return {
        "id": identifier, "parent_id": parent, "name": name, "short_name": "",
        "latitude": latitude, "longitude": longitude,
    }


def incident(identifier, organization_ids, position=(53.5, 9.6)):
    latitude, longitude = position or (None, None)
    return {
        "id": identifier, "organization_ids": organization_ids, "address": "Waldweg",
        "title": "", "keyword": "", "code": "x", "latitude": latitude, "longitude": longitude,
    }


class Org:
    def __init__(self, organizations, own):
        self._organizations, self._own = organizations, own

    def organizations(self):
        return self._organizations

    def memberships(self, user_id):
        return [{"organization_id": item} for item in self._own]


class Incidents:
    def __init__(self, items):
        self.items = items

    def visible(self, user, *, status=None):
        assert status == "running"
        return self.items


USER = {"user_id": 1, "role": "viewer"}
TREE = [organization(1, position=(53.6, 9.4), name="Samtgemeinde"), organization(2, 1, name="Ortswehr")]


def test_station_falls_back_to_parent_pin() -> None:
    places, automatic = weather_places(USER, Org(TREE, [2]), Incidents([]), FALLBACK)

    assert automatic == "station:1"
    assert [item["key"] for item in places] == ["station:1", "default"]
    assert places[-1]["name"] == "Standardstandort"


def test_incident_of_own_unit_is_automatic_choice() -> None:
    items = [incident(7, [99]), incident(8, [2]), incident(9, [2], position=None)]
    places, automatic = weather_places(USER, Org(TREE, [2]), Incidents(items), FALLBACK)

    assert automatic == "incident:8"
    # Fremde Einsätze bleiben wählbar, ohne Koordinaten fehlen sie.
    assert [item["key"] for item in places] == ["incident:7", "incident:8", "station:1", "default"]


def test_guests_only_get_the_default_location() -> None:
    places, automatic = weather_places(
        {"role": "guest"}, Org(TREE, [2]), Incidents([incident(8, [2])]), FALLBACK
    )

    assert automatic == "default"
    assert [item["key"] for item in places] == ["default"]
