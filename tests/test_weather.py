from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from open_bos_stream.core.models import WeatherConfig
from open_bos_stream.weather.assessment import assess
from open_bos_stream.weather.radar import (
    RadarService,
    RadarUnavailableError,
    radar_time,
)
from open_bos_stream.weather.service import (
    WeatherService,
    WeatherUnavailableError,
    parse_current,
    parse_kp,
)


ROOT = Path(__file__).resolve().parents[1]

BRIGHTSKY_CURRENT = {
    "weather": {
        "source_id": 7,
        "timestamp": "2026-11-26T21:00:00+00:00",
        "temperature": 0.4,
        "wind_speed_10": 36.0,
        "wind_gust_speed_10": 54.0,
        "wind_direction_10": 30,
        "precipitation_60": 0.0,
        "visibility": 31395,
    },
    "sources": [
        {"id": 7, "station_name": "Stade", "distance": 5300},
    ],
}

OPEN_METEO = {
    "hourly": {
        "time": ["2026-11-26T22:00", "2026-11-26T23:00"],
        "temperature_2m": [0.0, -0.4],
        "precipitation": [0.0, 0.0],
        "precipitation_probability": [3, 0],
        "wind_speed_10m": [1.9, 1.8],
        "wind_speed_80m": [4.6, 4.9],
        "wind_speed_120m": [5.8, 6.2],
        "wind_gusts_10m": [3.2, 3.4],
        "wind_direction_10m": [54, 74],
        "weather_code": [3, 3],
        "visibility": [13520, 10660],
    }
}

ALERTS = {
    "location": {"name": "Stadt Stade"},
    "alerts": [
        {
            "event_de": "FROST",
            "headline_de": "Amtliche WARNUNG vor FROST",
            "severity": "minor",
            "status": "actual",
        }
    ],
}

KP = [{"time_tag": "2026-11-26T18:00:00", "Kp": 0.67}]


def fake_fetch(responses: dict[str, object], calls: list[str]):
    def fetch(url: str):
        calls.append(url)
        for marker, response in responses.items():
            if marker in url:
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(url)

    return fetch


def standard_responses() -> dict[str, object]:
    return {
        "current_weather": BRIGHTSKY_CURRENT,
        "/alerts": ALERTS,
        "open-meteo": OPEN_METEO,
        "k-index": KP,
    }


# ----------------------------------------------------------------------
# Auswertung der Quellen
# ----------------------------------------------------------------------


def test_bright_sky_values_are_converted_to_metres_per_second() -> None:
    current = parse_current(BRIGHTSKY_CURRENT)

    assert current["wind_speed_ms"] == 10.0
    assert current["wind_gust_ms"] == 15.0
    assert current["station"] == "Stade"
    assert current["station_distance_km"] == 5.3


def test_kp_index_reads_object_and_table_format() -> None:
    assert parse_kp(KP) == {"time": "2026-11-26T18:00:00", "kp": 0.67}
    table = [
        ["time_tag", "Kp", "a_running", "station_count"],
        ["2026-11-26 18:00:00.000", "5.33", "48", "8"],
    ]
    assert parse_kp(table)["kp"] == 5.33
    assert parse_kp([]) is None


def test_report_combines_sources_and_caches_per_area() -> None:
    calls: list[str] = []
    clock = [0.0]
    service = WeatherService(
        fetch_json=fake_fetch(standard_responses(), calls),
        clock=lambda: clock[0],
    )

    report = service.report(WeatherConfig(), 53.56389, 9.52972)
    assert report["coordinates"] == {"latitude": 53.56, "longitude": 9.53}
    assert report["current"]["temperature_c"] == 0.4
    assert report["forecast"][0]["wind_speed_120m_ms"] == 5.8
    assert report["alerts"][0]["event"] == "FROST"
    assert report["kp"]["kp"] == 0.67
    assert report["errors"] == {}
    assert len(calls) == 4

    # Nachbarpunkt im selben Raster: alles aus dem Zwischenspeicher.
    service.report(WeatherConfig(), 53.5612, 9.5311)
    assert len(calls) == 4

    # Nach 11 Minuten werden Messwerte und Warnungen neu geladen.
    clock[0] = 11 * 60
    service.report(WeatherConfig(), 53.56, 9.53)
    assert len(calls) == 6


def test_failing_source_does_not_hide_the_others() -> None:
    responses = standard_responses()
    responses["open-meteo"] = WeatherUnavailableError("nicht erreichbar")
    service = WeatherService(fetch_json=fake_fetch(responses, []))

    report = service.report(WeatherConfig(), 53.56, 9.53)

    assert report["errors"] == {"forecast": "nicht erreichbar"}
    assert report["forecast"] == []
    assert report["current"]["wind_speed_ms"] == 10.0
    assert report["assessment"]["level"] != "unknown"


def test_without_any_data_the_assessment_is_unknown() -> None:
    error = WeatherUnavailableError("nicht erreichbar")
    service = WeatherService(
        fetch_json=fake_fetch(
            {key: error for key in standard_responses()},
            [],
        )
    )

    report = service.report(WeatherConfig(), 53.56, 9.53)

    assert report["assessment"]["level"] == "unknown"
    assert set(report["errors"]) == {"current", "alerts", "forecast", "kp"}


# ----------------------------------------------------------------------
# Ampel
# ----------------------------------------------------------------------


def report_with(current=None, forecast=None, alerts=None, kp=None) -> dict:
    return {
        "current": current or {},
        "forecast": forecast or [],
        "alerts": alerts or [],
        "kp": {"kp": kp} if kp is not None else None,
    }


def level(report: dict, config: WeatherConfig | None = None) -> str:
    return assess(report, config or WeatherConfig())["level"]


def test_calm_weather_is_green() -> None:
    report = report_with(
        current={"wind_speed_ms": 3, "wind_gust_ms": 5, "temperature_c": 12,
                 "precipitation_mm_h": 0, "visibility_m": 20000},
        forecast=[{"wind_speed_120m_ms": 6}],
        kp=1,
    )
    assert level(report) == "green"
    assert assess(report, WeatherConfig())["reasons"] == []


def test_wind_in_flight_height_counts() -> None:
    config = WeatherConfig(wind_limit_ms=10)
    assert level(report_with(forecast=[{"wind_speed_120m_ms": 8}]), config) == "yellow"
    assert level(report_with(forecast=[{"wind_speed_120m_ms": 11}]), config) == "red"


def test_gusts_rain_temperature_visibility_and_kp() -> None:
    assert level(report_with(current={"wind_gust_ms": 13})) == "red"
    assert level(report_with(current={"precipitation_mm_h": 0.2})) == "yellow"
    assert level(report_with(current={"precipitation_mm_h": 1.5})) == "red"
    assert level(report_with(current={"temperature_c": -12})) == "red"
    assert level(report_with(current={"temperature_c": -8})) == "yellow"
    assert level(report_with(current={"visibility_m": 800})) == "red"
    assert level(report_with(current={"visibility_m": 1500})) == "yellow"
    assert level(report_with(current={"temperature_c": 10}, kp=4)) == "yellow"
    assert level(report_with(current={"temperature_c": 10}, kp=5.3)) == "red"


def test_dwd_warnings_count_from_moderate_severity() -> None:
    base = {"temperature_c": 10}
    minor = [{"severity": "minor", "headline": "Frost"}]
    severe = [{"severity": "severe", "headline": "Unwetter: Orkanböen"}]

    assert level(report_with(current=base, alerts=minor)) == "green"
    result = assess(report_with(current=base, alerts=severe), WeatherConfig())
    assert result["level"] == "red"
    assert result["reasons"][0]["text"] == "DWD: Unwetter: Orkanböen"


def test_forecast_outlook_names_the_first_critical_hour() -> None:
    report = report_with(
        current={"temperature_c": 10},
        forecast=[
            {"time": "2026-11-26T14:00", "wind_gust_ms": 4},
            {"time": "2026-11-26T15:00", "wind_gust_ms": 6},
            {"time": "2026-11-26T16:00", "wind_gust_ms": 16},
            {"time": "2026-11-26T17:00", "precipitation_mm_h": 5},
        ],
    )
    result = assess(report, WeatherConfig())

    assert result["level"] == "yellow"
    assert result["reasons"] == [
        {"level": "yellow", "text": "Vorhersage ab 16:00 Uhr: Böen 16,0 m/s"}
    ]


# ----------------------------------------------------------------------
# Einstellungen
# ----------------------------------------------------------------------


def test_weather_config_validates_location_and_temperatures() -> None:
    assert WeatherConfig(latitude=53.6, longitude=9.5).latitude == 53.6
    with pytest.raises(ValidationError, match="Breite und Länge"):
        WeatherConfig(latitude=53.6)
    with pytest.raises(ValidationError, match="Mindesttemperatur"):
        WeatherConfig(min_temperature_c=15, max_temperature_c=12)


# ----------------------------------------------------------------------
# Niederschlagsradar
# ----------------------------------------------------------------------


def test_radar_time_rounds_to_five_minutes() -> None:
    now = datetime(2026, 11, 26, 21, 22, 41, tzinfo=timezone.utc)
    assert radar_time(0, now) is None
    assert radar_time(30, now) == "2026-11-26T21:50:00.000Z"
    assert radar_time(90, now) == "2026-11-26T22:50:00.000Z"


def test_radar_tiles_are_cached_and_validated() -> None:
    calls: list[dict] = []

    def fetch(params):
        calls.append(params)
        return b"\x89PNG"

    service = RadarService(
        fetch=fetch,
        now=lambda: datetime(2026, 11, 26, 21, 22, tzinfo=timezone.utc),
    )

    assert service.tile(0, 8, 134, 81) == b"\x89PNG"
    assert service.tile(0, 8, 134, 81) == b"\x89PNG"
    assert len(calls) == 1
    assert "TIME" not in calls[0]
    assert calls[0]["LAYERS"] == "dwd:Niederschlagsradar"

    service.tile(60, 8, 134, 81)
    assert calls[1]["TIME"] == "2026-11-26T22:20:00.000Z"

    with pytest.raises(KeyError):
        service.tile(45, 8, 134, 81)
    with pytest.raises(ValueError):
        service.tile(0, 14, 0, 0)


def test_radar_reports_geoserver_errors() -> None:
    class Response:
        headers = {"Content-Type": "text/xml"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"<ServiceExceptionReport/>"

    import urllib.request

    original = urllib.request.urlopen
    urllib.request.urlopen = lambda *args, **kwargs: Response()
    try:
        with pytest.raises(RadarUnavailableError):
            RadarService().tile(0, 8, 134, 81)
    finally:
        urllib.request.urlopen = original


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from open_bos_stream.api import weather as weather_api
    from open_bos_stream.core.container import auth_service, config
    from open_bos_stream.core.event_log import ServerEventLog
    from open_bos_stream.main import app

    monkeypatch.setattr(
        auth_service,
        "verify_token",
        lambda token, *, purpose="session": (
            {"username": token, "role": token}
            if token in {"guest", "viewer", "admin"}
            else None
        ),
    )
    monkeypatch.setattr(type(auth_service), "configured", property(lambda self: True))
    monkeypatch.setattr(weather_api, "server_event_log", ServerEventLog(None))
    monkeypatch.setattr(
        weather_api,
        "weather_service",
        WeatherService(fetch_json=fake_fetch(standard_responses(), [])),
    )
    saved: list[WeatherConfig] = []

    def update_weather(weather: WeatherConfig) -> WeatherConfig:
        saved.append(weather)
        return weather

    monkeypatch.setattr(
        weather_api.config_apply_service,
        "update_weather",
        update_weather,
    )
    monkeypatch.setattr(config, "weather", WeatherConfig())
    test_client = TestClient(app)
    test_client.saved = saved
    return test_client, config


def login(client, role: str) -> None:
    from open_bos_stream.core.container import auth_service

    client.cookies.clear()
    client.cookies.set(auth_service.COOKIE_NAME, role)


def test_guests_get_weather_for_the_map(client) -> None:
    test_client, _ = client
    login(test_client, "guest")

    response = test_client.get("/api/weather?lat=53.6&lon=9.47")
    assert response.status_code == 200
    body = response.json()
    assert body["location"]["origin"] == "query"
    # Testdaten: Böen 15 m/s über dem Standardgrenzwert von 12 m/s.
    assert body["assessment"]["level"] == "red"

    default = test_client.get("/api/weather").json()
    assert default["location"]["origin"] == "map"
    assert test_client.get("/api/weather?lat=53.6").status_code == 400
    assert test_client.get("/api/weather/radar").json()["enabled"] is True


def test_disabled_weather_returns_404(client) -> None:
    test_client, config = client
    config.weather = WeatherConfig(enabled=False)
    login(test_client, "viewer")

    assert test_client.get("/api/weather").status_code == 404
    assert test_client.get("/api/weather/radar").json()["enabled"] is False
    assert (
        test_client.get("/api/weather/radar/tiles/0/8/1/1.png").status_code
        == 404
    )


def test_only_admins_change_weather_settings(client) -> None:
    test_client, _ = client
    payload = WeatherConfig(
        location_name="Feuerwache",
        latitude=53.6,
        longitude=9.47,
    ).model_dump()

    login(test_client, "viewer")
    assert test_client.put("/api/weather/settings", json=payload).status_code == 403

    login(test_client, "admin")
    assert test_client.put(
        "/api/weather/settings",
        json={**payload, "longitude": None},
    ).status_code == 422
    response = test_client.put("/api/weather/settings", json=payload)
    assert response.status_code == 200
    assert test_client.saved[-1].location_name == "Feuerwache"


def test_full_config_save_keeps_server_side_weather() -> None:
    source = (ROOT / "src" / "open_bos_stream" / "api" / "config.py").read_text(
        encoding="utf-8"
    )
    assert "config.weather = stored.weather" in source


# ----------------------------------------------------------------------
# Oberfläche
# ----------------------------------------------------------------------


def test_weather_ui_is_wired_into_dashboard_map_and_settings() -> None:
    templates = ROOT / "src" / "open_bos_stream" / "templates"
    index = (templates / "index.html").read_text(encoding="utf-8")
    guest = (templates / "guest.html").read_text(encoding="utf-8")
    settings = (templates / "components" / "settings_card.html").read_text(
        encoding="utf-8"
    )
    config_js = (
        ROOT / "src" / "open_bos_stream" / "static" / "js" / "config.js"
    ).read_text(encoding="utf-8")

    assert '{% include "components/weather_card.html" %}' in index
    assert index.index("map-weather.js") < index.index("/static/js/map.js")
    assert "weather.js" in index
    assert guest.index("map-weather.js") < guest.index("/static/js/map.js")
    assert 'id="cfg-weather-enabled"' in settings
    # Wetter wird separat gespeichert und markiert die Konfiguration nicht.
    assert '".settings-section-weather"' in config_js


# ----------------------------------------------------------------------
# Wetterseite: Radar-Zeitleiste
# ----------------------------------------------------------------------


def test_timeline_covers_two_hours_back_and_ninety_minutes_ahead() -> None:
    from open_bos_stream.weather.radar import timeline_frames

    now = datetime(2026, 11, 26, 21, 22, 41, tzinfo=timezone.utc)
    frames = timeline_frames(now)

    assert frames[0] == {
        "stamp": "202611261920",
        "time": "2026-11-26T19:20:00Z",
        "offset": -120,
    }
    assert frames[-1]["stamp"] == "202611262250"
    assert [frame["offset"] for frame in frames].count(0) == 1
    assert len(frames) == 22


def test_timeline_tiles_accept_only_stamps_on_the_timeline() -> None:
    calls: list[dict] = []
    clock = [0.0]

    def fetch(params):
        calls.append(params)
        return b"\x89PNG"

    service = RadarService(
        fetch=fetch,
        clock=lambda: clock[0],
        now=lambda: datetime(2026, 11, 26, 21, 22, tzinfo=timezone.utc),
    )

    service.tile_at("202611261950", 7, 67, 40)
    assert calls[-1]["TIME"] == "2026-11-26T19:50:00.000Z"

    for stamp in ("20261126", "202611261953", "202611260900", "202611270100"):
        with pytest.raises(ValueError):
            service.tile_at(stamp, 7, 67, 40)

    # Vergangene Bilder bleiben eine Stunde im Speicher, aktuelle nur kurz.
    service.tile_at("202611262120", 7, 67, 40)
    clock[0] = 10 * 60
    service.tile_at("202611261950", 7, 67, 40)
    service.tile_at("202611262120", 7, 67, 40)
    assert [call["TIME"] for call in calls] == [
        "2026-11-26T19:50:00.000Z",
        "2026-11-26T21:20:00.000Z",
        "2026-11-26T21:20:00.000Z",
    ]


def test_frames_endpoint_for_the_weather_page(client) -> None:
    test_client, _ = client
    login(test_client, "viewer")

    body = test_client.get("/api/weather/radar/frames").json()

    assert len(body["frames"]) == 22
    assert body["max_zoom"] == 7
    assert body["location"]["origin"] == "map"
    assert (
        test_client.get("/api/weather/radar/time/2020/7/1/1.png").status_code
        == 400
    )


def test_weather_page_is_in_the_menu_for_everyone() -> None:
    templates = ROOT / "src" / "open_bos_stream" / "templates"
    sidebar = (templates / "components" / "sidebar.html").read_text(
        encoding="utf-8"
    )
    index = (templates / "index.html").read_text(encoding="utf-8")
    page = (templates / "components" / "weather_page.html").read_text(
        encoding="utf-8"
    )
    navigation = (
        ROOT / "src" / "open_bos_stream" / "static" / "js" / "navigation.js"
    ).read_text(encoding="utf-8")

    assert '"page": "weather", "label": "Wetter", "icon": "weather", "primary": true, "visible": true' in sidebar
    assert 'id="page-weather"' in index
    assert '{% include "components/weather_page.html" %}' in index
    assert 'id="weather-radar-slider"' in page
    assert 'id="weather-radar-play"' in page
    assert 'weather_card_variant = "page"' in page
    # Reihenfolge: Zusammenfassung, Radar, 24-Stunden-Vorhersage.
    assert (
        page.index("weather_card.html")
        < page.index('id="weather-radar-map"')
        < page.index("data-weather-forecast-card")
    )
    assert "setWeatherPageActive(page === \"weather\")" in navigation


def test_ampel_outlook_is_limited_to_the_next_hours() -> None:
    forecast = [{"time": f"2026-11-26T{hour:02d}:00"} for hour in range(10, 20)]
    forecast[8]["wind_gust_ms"] = 20

    result = assess(report_with(current={"temperature_c": 10}, forecast=forecast), WeatherConfig())

    assert result["level"] == "green"


# ----------------------------------------------------------------------
# Taupunkt, Wolkenbasis, Sonne
# ----------------------------------------------------------------------


def test_sun_times_match_reference_values_for_stade(monkeypatch) -> None:
    import time as time_module

    from open_bos_stream.weather.sun import sun_info

    monkeypatch.setenv("TZ", "Europe/Berlin")
    time_module.tzset()
    summer = sun_info(53.6, 9.47, datetime(2026, 6, 21, 10, tzinfo=timezone.utc))
    winter = sun_info(53.6, 9.47, datetime(2026, 12, 21, 11, tzinfo=timezone.utc))
    night = sun_info(53.6, 9.47, datetime(2026, 11, 26, 21, 30, tzinfo=timezone.utc))

    assert summer["sunrise"].startswith("2026-06-21T04:5")
    assert summer["sunset"].startswith("2026-06-21T21:5")
    assert winter["sunrise"].startswith("2026-12-21T08:3")
    assert winter["sunset"].startswith("2026-12-21T16:0")
    assert summer["dark"] is False
    assert night["dark"] is True
    assert night["civil_dusk"] > night["sunset"]


def test_dew_point_spread_and_cloud_base() -> None:
    from open_bos_stream.weather.service import derived_values

    derived = derived_values({"temperature_c": 6.0, "dew_point_c": 4.4}, [])
    assert derived == {
        "dew_point_c": 4.4,
        "dew_point_spread_c": 1.6,
        "cloud_base_m": 200,
    }
    # Ohne Messwert gilt die Vorhersage.
    assert derived_values(None, [{"temperature_c": 10, "dew_point_c": 2}])[
        "cloud_base_m"
    ] == 1000


def test_fog_icing_and_darkness_turn_the_ampel_yellow() -> None:
    report = report_with(current={"temperature_c": 1.0, "humidity_percent": 95})
    report["derived"] = {
        "dew_point_c": -0.5,
        "dew_point_spread_c": 1.5,
        "cloud_base_m": 190,
    }
    report["sun"] = {"dark": True}

    texts = [reason["text"] for reason in assess(report, WeatherConfig())["reasons"]]

    assert any(text.startswith("Taupunktdifferenz 1,5 °C") for text in texts)
    assert "Tiefe Wolkenuntergrenze (geschätzt 190 m)" in texts
    assert "Vereisungsgefahr an Propellern und Sensoren" in texts
    assert any(text.startswith("Dunkelheit") for text in texts)
    assert assess(report, WeatherConfig())["level"] == "yellow"


def test_report_contains_sun_and_derived_values() -> None:
    service = WeatherService(
        fetch_json=fake_fetch(standard_responses(), []),
        now=lambda: datetime(2026, 6, 21, 10, tzinfo=timezone.utc),
    )
    report = service.report(WeatherConfig(), 53.56, 9.53)

    assert report["sun"]["dark"] is False
    assert report["sun"]["sunrise"]
    assert set(report["derived"]) == {
        "dew_point_c",
        "dew_point_spread_c",
        "cloud_base_m",
    }
