"""
The weather a flight actually had, from Open-Meteo's archive of weather model runs (DWD's ICON, which has the low
pressure levels we fly in). Used by the flight summaries (display.services.flight_analysis).

Data: Open-Meteo.com (CC BY 4.0), which must be credited where it is shown. The free API is for non-commercial use;
with OPEN_METEO_API_KEY set the paid ("customer") API is used instead.
"""

import bisect
import datetime
import logging
import math

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

FREE_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
CUSTOMER_URL = "https://customer-historical-forecast-api.open-meteo.com/v1/forecast"
MODEL = "icon_seamless"
SOURCE = "Open-Meteo.com, DWD ICON weather model"

# Winds are interpolated between these, by their height above the ground
PRESSURE_LEVELS = (1000, 975, 950, 925, 900, 850)
HEIGHTS_ABOVE_GROUND = (10, 80, 120, 180)
SURFACE_VARIABLES = ("weather_code", "cloud_cover", "cloud_cover_low", "visibility", "precipitation", "temperature_2m")
# Cloud at a pressure level covering at least this much of the sky counts as the cloud base
CLOUD_BASE_COVER = 50

M_PER_FT = 0.3048

WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "freezing fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    56: "freezing drizzle",
    57: "heavy freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "freezing rain",
    67: "heavy freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light rain showers",
    81: "rain showers",
    82: "violent rain showers",
    85: "snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "thunderstorm with heavy hail",
}


def _hourly_variables() -> list[str]:
    variables = list(SURFACE_VARIABLES) + ["wind_gusts_10m"]
    for height in HEIGHTS_ABOVE_GROUND:
        variables += [f"wind_speed_{height}m", f"wind_direction_{height}m"]
    for level in PRESSURE_LEVELS:
        variables += [
            f"wind_speed_{level}hPa",
            f"wind_direction_{level}hPa",
            f"geopotential_height_{level}hPa",
            f"cloud_cover_{level}hPa",
        ]
    return variables


def fetch_weather(latitude: float, longitude: float, start: datetime.datetime, end: datetime.datetime) -> dict | None:
    """
    The hourly weather at the point over the days from start to end, as Open-Meteo returns it (wind in knots, times in
    UTC). None when it cannot be had.
    """
    params = {
        "latitude": f"{latitude:.4f}",
        "longitude": f"{longitude:.4f}",
        "start_date": start.astimezone(datetime.timezone.utc).date().isoformat(),
        "end_date": end.astimezone(datetime.timezone.utc).date().isoformat(),
        "hourly": ",".join(_hourly_variables()),
        "models": MODEL,
        "wind_speed_unit": "kn",
        "timezone": "UTC",
    }
    url = FREE_URL
    if settings.OPEN_METEO_API_KEY:
        url = CUSTOMER_URL
        params["apikey"] = settings.OPEN_METEO_API_KEY
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        location = response.json()
    except (requests.RequestException, ValueError):
        logger.exception("Could not fetch the weather from Open-Meteo")
        return None
    if not isinstance(location, dict) or "hourly" not in location:
        logger.warning(f"Unexpected answer from Open-Meteo: {str(location)[:200]}")
        return None
    return location


def _hour_index(location: dict, when: datetime.datetime) -> tuple[int, int, float] | None:
    """The hours on either side of the time and how far between them it is (0..1)."""
    times = location["hourly"]["time"]
    hour = when.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    stamps = [datetime.datetime.fromisoformat(time) for time in times]
    position = bisect.bisect_right(stamps, hour)
    if position == 0 or position >= len(stamps):
        return None
    before, after = position - 1, position
    fraction = (hour - stamps[before]).total_seconds() / (stamps[after] - stamps[before]).total_seconds()
    return before, after, fraction


def _value(location: dict, name: str, index: int):
    values = location["hourly"].get(name)
    return values[index] if values is not None else None


def _wind_profile(location: dict, index: int) -> list[tuple[float, float, float]]:
    """(height above ground in metres, east, north) wind components in knots at one hour, lowest first."""
    profile = []
    elevation = location.get("elevation") or 0
    for height in HEIGHTS_ABOVE_GROUND:
        profile.append(
            (
                height,
                _value(location, f"wind_speed_{height}m", index),
                _value(location, f"wind_direction_{height}m", index),
            )
        )
    for level in PRESSURE_LEVELS:
        altitude = _value(location, f"geopotential_height_{level}hPa", index)
        if altitude is not None:
            profile.append(
                (
                    altitude - elevation,
                    _value(location, f"wind_speed_{level}hPa", index),
                    _value(location, f"wind_direction_{level}hPa", index),
                )
            )
    components = []
    for height, speed, direction in profile:
        if speed is None or direction is None or height <= 0:
            continue
        # The direction the wind comes from: the air moves the opposite way
        components.append(
            (height, -speed * math.sin(math.radians(direction)), -speed * math.cos(math.radians(direction)))
        )
    return sorted(components)


def _interpolate(profile: list[tuple[float, float, float]], height: float) -> tuple[float, float] | None:
    if not profile:
        return None
    if height <= profile[0][0]:
        return profile[0][1], profile[0][2]
    if height >= profile[-1][0]:
        return profile[-1][1], profile[-1][2]
    for (low, low_east, low_north), (high, high_east, high_north) in zip(profile, profile[1:]):
        if low <= height <= high:
            fraction = (height - low) / (high - low) if high > low else 0
            return low_east + (high_east - low_east) * fraction, low_north + (high_north - low_north) * fraction
    return None


def to_speed_and_direction(east: float, north: float) -> tuple[float, float]:
    speed = math.hypot(east, north)
    direction = (math.degrees(math.atan2(-east, -north)) + 360) % 360
    return round(speed, 1), round(direction) % 360


def wind_components_at(location: dict, when: datetime.datetime, height_above_ground_ft: float):
    """The (east, north) wind in knots at the height above the ground and the time, or None."""
    hours = _hour_index(location, when)
    if hours is None:
        return None
    before, after, fraction = hours
    height = height_above_ground_ft * M_PER_FT
    first = _interpolate(_wind_profile(location, before), height)
    second = _interpolate(_wind_profile(location, after), height)
    if first is None or second is None:
        return first or second
    return first[0] + (second[0] - first[0]) * fraction, first[1] + (second[1] - first[1]) * fraction


def cloud_base_ft(location: dict, index: int) -> int | None:
    """Roughly how high above the ground the lowest layer of cloud covering half the sky or more was, in feet."""
    elevation = location.get("elevation") or 0
    bases = []
    for level in PRESSURE_LEVELS:
        cover = _value(location, f"cloud_cover_{level}hPa", index)
        altitude = _value(location, f"geopotential_height_{level}hPa", index)
        if cover is not None and altitude is not None and cover >= CLOUD_BASE_COVER:
            bases.append(max(0.0, altitude - elevation))
    return round(min(bases) / M_PER_FT, -1) if bases else None


def conditions_at(location: dict, when: datetime.datetime) -> dict | None:
    """The weather at the hour closest to the time."""
    hours = _hour_index(location, when)
    if hours is None:
        return None
    before, after, fraction = hours
    index = after if fraction >= 0.5 else before
    code = _value(location, "weather_code", index)
    visibility = _value(location, "visibility", index)
    return {
        "weather": WEATHER_CODES.get(code, "unknown") if code is not None else None,
        "cloud_cover_percent": _value(location, "cloud_cover", index),
        "low_cloud_cover_percent": _value(location, "cloud_cover_low", index),
        "cloud_base_ft_above_ground": cloud_base_ft(location, index),
        "visibility_km": round(visibility / 1000, 1) if visibility is not None else None,
        "precipitation_mm_per_hour": _value(location, "precipitation", index),
        "temperature_c": _value(location, "temperature_2m", index),
        "surface_gusts_kt": _value(location, "wind_gusts_10m", index),
    }
