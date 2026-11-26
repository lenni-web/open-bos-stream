"""Sonnenauf- und -untergang sowie bürgerliche Dämmerung.

Berechnung nach der Sonnenaufgangsgleichung (Genauigkeit etwa eine Minute),
ohne externen Dienst. Die bürgerliche Dämmerung endet, wenn die Sonne 6°
unter dem Horizont steht; danach gilt es im Luftrecht als Nacht.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone


SUNRISE_ANGLE = -0.833
CIVIL_TWILIGHT_ANGLE = -6.0
J2000 = 2451545.0
UNIX_EPOCH_JD = 2440587.5
OBLIQUITY = math.radians(23.4397)


def _julian_noon(day: date) -> float:
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)
    return UNIX_EPOCH_JD + noon.timestamp() / 86400


def _from_julian(value: float) -> datetime:
    return datetime.fromtimestamp((value - UNIX_EPOCH_JD) * 86400, tz=timezone.utc)


def sun_event_times(
    latitude: float,
    longitude: float,
    day: date,
    angle: float,
) -> tuple[datetime, datetime] | None:
    """Zeitpunkte (UTC), an denen die Sonne `angle` Grad Höhe erreicht.

    None, wenn sie diese Höhe an dem Tag nicht über- bzw. unterschreitet.
    """

    n = round(_julian_noon(day) - J2000 + 0.0008)
    mean_noon = n - longitude / 360
    anomaly = math.radians((357.5291 + 0.98560028 * mean_noon) % 360)
    center = (
        1.9148 * math.sin(anomaly)
        + 0.02 * math.sin(2 * anomaly)
        + 0.0003 * math.sin(3 * anomaly)
    )
    ecliptic = math.radians(
        (math.degrees(anomaly) + center + 180 + 102.9372) % 360
    )
    transit = (
        J2000
        + mean_noon
        + 0.0053 * math.sin(anomaly)
        - 0.0069 * math.sin(2 * ecliptic)
    )
    declination = math.asin(math.sin(ecliptic) * math.sin(OBLIQUITY))
    lat = math.radians(latitude)
    cos_hour = (
        math.sin(math.radians(angle)) - math.sin(lat) * math.sin(declination)
    ) / (math.cos(lat) * math.cos(declination))
    if not -1 <= cos_hour <= 1:
        return None
    hour = math.degrees(math.acos(cos_hour)) / 360
    return _from_julian(transit - hour), _from_julian(transit + hour)


def sun_info(latitude: float, longitude: float, now: datetime) -> dict:
    """Sonnenzeiten des Tages in Ortszeit und ob es gerade dunkel ist."""

    local_now = now.astimezone()
    day = local_now.date()
    sun = sun_event_times(latitude, longitude, day, SUNRISE_ANGLE)
    civil = sun_event_times(latitude, longitude, day, CIVIL_TWILIGHT_ANGLE)

    def local(value: datetime | None) -> str | None:
        return value.astimezone().isoformat(timespec="minutes") if value else None

    dark = None
    if civil is not None:
        dark = not civil[0] <= now <= civil[1]
    return {
        "sunrise": local(sun[0] if sun else None),
        "sunset": local(sun[1] if sun else None),
        "civil_dawn": local(civil[0] if civil else None),
        "civil_dusk": local(civil[1] if civil else None),
        "dark": dark,
    }

