import datetime
import logging

from django.db import transaction

from display.calculators.photo_observation_calculator import (
    PhotoObservationResult,
    calculate_photo_observation,
    estimate_fit_page_scale_thousands,
    metres_per_millimetre,
)
from display.flight_order_and_maps.effective_route_rendering import get_effective_route_waypoints
from display.flight_order_and_maps.map_constants import LANDSCAPE, SCALE_TO_FIT
from display.models import Contestant, Photo, PhotoObservation
from display.utilities.gate_definitions import DUMMY, LANDING_GATE, TAKEOFF_GATE

logger = logging.getLogger(__name__)

EXCLUDED_TRACK_GATE_TYPES = {TAKEOFF_GATE, LANDING_GATE, DUMMY}


class PhotoObservationError(ValueError):
    pass


def get_track_polyline(contestant: Contestant) -> list[tuple[float, float]]:
    """The track the crew follows, as (latitude, longitude) pairs, in flying order."""
    waypoints = get_effective_route_waypoints(contestant.navigation_task, contestant)
    return [(wp.latitude, wp.longitude) for wp in waypoints if wp.type not in EXCLUDED_TRACK_GATE_TYPES]


def get_metres_per_mm(contestant: Contestant, polyline: list[tuple[float, float]]) -> float | None:
    """Ground distance of one millimetre on the contestant's printed map, from the flight order configuration."""
    configuration = getattr(contestant.navigation_task, "flightorderconfiguration", None)
    scale = configuration.map_scale if configuration else SCALE_TO_FIT
    if scale != SCALE_TO_FIT:
        return metres_per_millimetre(scale)
    return estimate_fit_page_scale_thousands(
        polyline,
        document_size=configuration.document_size if configuration else "A4",
        landscape=bool(configuration and configuration.map_orientation == LANDSCAPE),
    )


def resolve_photo(contestant: Contestant, photo_name: str) -> Photo:
    photo = Photo.objects.filter(route=contestant.navigation_task.route, name=photo_name, is_decoy=False).first()
    if photo is None:
        raise PhotoObservationError(f"Unknown observation photo '{photo_name}'")
    return photo


def score_observation(
    contestant: Contestant, photo: Photo, latitude: float, longitude: float
) -> tuple[PhotoObservationResult, float | None]:
    polyline = get_track_polyline(contestant)
    metres_per_mm = get_metres_per_mm(contestant, polyline)
    # The target coordinates for this contestant may have been adjusted by their compiled task configuration
    photo_latitude, photo_longitude = photo.latitude, photo.longitude
    config = getattr(contestant, "contestanttaskconfiguration", None)
    if config is not None and config.is_valid:
        for item in (config.compiled_effective_route_payload or {}).get("observation_photos", []):
            if item.get("name") == photo.name and item.get("coordinates"):
                photo_longitude, photo_latitude = item["coordinates"][:2]
    result = calculate_photo_observation(
        user_latitude=latitude,
        user_longitude=longitude,
        photo_latitude=photo_latitude,
        photo_longitude=photo_longitude,
        polyline=polyline,
        metres_per_mm=metres_per_mm,
    )
    return result, metres_per_mm


def _apply_result(observation: PhotoObservation, result: PhotoObservationResult) -> None:
    observation.scored = result.scored
    observation.status = result.reason
    observation.error_m = result.error_m
    observation.error_mm = result.error_mm
    observation.score_fraction = result.score_fraction
    observation.metres_per_mm = result.metres_per_mm
    if result.user_projection:
        observation.projected_latitude = result.user_projection.latitude
        observation.projected_longitude = result.user_projection.longitude
    if result.photo_projection:
        observation.photo_projected_latitude = result.photo_projection.latitude
        observation.photo_projected_longitude = result.photo_projection.longitude


def register_photo_observation(
    contestant: Contestant,
    *,
    photo_name: str,
    time: datetime.datetime,
    latitude: float,
    longitude: float,
) -> tuple[PhotoObservation, bool]:
    """
    Registers (and scores) the crew's observation of a photo. Registering the same photo again replaces the
    earlier registration only if it was made later, so that replays of queued requests from the app
    are harmless. Returns the stored observation and whether it was changed.
    """
    if time.tzinfo is None:
        time = time.replace(tzinfo=datetime.timezone.utc)
    photo = resolve_photo(contestant, photo_name)
    result, _ = score_observation(contestant, photo, latitude, longitude)
    with transaction.atomic():
        observation, created = PhotoObservation.objects.select_for_update().get_or_create(
            contestant=contestant,
            photo_name=photo.name,
            defaults={"photo": photo, "time": time, "latitude": latitude, "longitude": longitude},
        )
        if not created:
            if time <= observation.time:
                return observation, False
            observation.photo = photo
            observation.time = time
            observation.latitude = latitude
            observation.longitude = longitude
        _apply_result(observation, result)
        observation.save()
    _transmit(contestant)
    return observation, True


def delete_photo_observation(observation: PhotoObservation) -> None:
    contestant = observation.contestant
    observation.delete()
    _transmit(contestant)


def rescore_contestant_observations(contestant: Contestant) -> int:
    """Re-scores all of a contestant's observations, e.g. after the map scale in the flight order changed."""
    count = 0
    for observation in contestant.photo_observations.select_related("photo"):
        photo = observation.photo or resolve_photo(contestant, observation.photo_name)
        result, _ = score_observation(contestant, photo, observation.latitude, observation.longitude)
        _apply_result(observation, result)
        observation.save()
        count += 1
    if count:
        _transmit(contestant)
    return count


def _transmit(contestant: Contestant) -> None:
    from websocket_channels import WebsocketFacade

    try:
        WebsocketFacade().transmit_photo_observations(contestant)
    except Exception:
        logger.exception("Failed to push photo observations for contestant %s", contestant.pk)
