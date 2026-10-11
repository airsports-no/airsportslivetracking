import datetime
import logging

from django.db import transaction
from django.db.models import F

from display.calculators.photo_observation_calculator import (
    CIMA_FULL_TOLERANCE_MM,
    CIMA_HALF_TOLERANCE_MM,
    DEFAULT_MAP_SCALE_THOUSANDS,
    LEGACY_FULL_TOLERANCE_MM,
    LEGACY_HALF_TOLERANCE_MM,
    PhotoObservationResult,
    calculate_photo_observation,
    metres_per_millimetre,
)
from display.flight_order_and_maps.effective_route_rendering import get_effective_route_waypoints
from display.flight_order_and_maps.map_constants import SCALE_TO_FIT
from display.models import (
    Contestant,
    GateCumulativeScore,
    Photo,
    PhotoObservation,
    ScoreLogEntry,
    TrackAnnotation,
)
from display.models.scoring_models import ANOMALY
from display.utilities.cima_task_type_definitions import KNOWN_CIRCUIT, UNKNOWN_LEGS
from display.utilities.gate_definitions import DUMMY, LANDING_GATE, TAKEOFF_GATE, TURNPOINT

logger = logging.getLogger(__name__)

EXCLUDED_TRACK_GATE_TYPES = {TAKEOFF_GATE, LANDING_GATE, DUMMY}

# Legacy tasks deduct observation_photo_penalty per missed observation. 2.A4/2.A5 award observation_photo_value
# (Vh) per observation: full within 2 mm, half within 5 mm.
MODE_LEGACY = "legacy"
MODE_CIMA = "cima"
CIMA_OBSERVATION_SUBTYPES = (KNOWN_CIRCUIT, UNKNOWN_LEGS)


class PhotoObservationError(ValueError):
    pass


def get_scoring_mode(contestant: Contestant) -> str | None:
    """None means observations are recorded but do not affect the score (the task type has no such rule)."""
    subtype = contestant.navigation_task.effective_task_subtype or ""
    if subtype.startswith("legacy_"):
        return MODE_LEGACY
    if subtype in CIMA_OBSERVATION_SUBTYPES:
        return MODE_CIMA
    return None


def get_tolerances_mm(mode: str | None) -> tuple[float, float]:
    if mode == MODE_CIMA:
        return CIMA_FULL_TOLERANCE_MM, CIMA_HALF_TOLERANCE_MM
    return LEGACY_FULL_TOLERANCE_MM, LEGACY_HALF_TOLERANCE_MM


def get_contestant_observation_photos(contestant: Contestant) -> list[Photo]:
    """The real (non-decoy) observation photos this contestant is expected to mark."""
    route = contestant.navigation_task.route
    if getattr(route, "pk", None) is None:
        return []
    photos = list(Photo.objects.filter(route=route, is_decoy=False))
    config = getattr(contestant, "contestanttaskconfiguration", None)
    if config is not None and config.is_valid:
        names = {
            item.get("name") for item in (config.compiled_effective_route_payload or {}).get("observation_photos", [])
        }
        names.discard(None)
        if names:
            photos = [photo for photo in photos if photo.name in names]
    return photos


def get_cima_observation_qmax(contestant: Contestant) -> float:
    """Qh at its maximum, Vh * Nh: the part of Qmax contributed by the observation photos."""
    if get_scoring_mode(contestant) != MODE_CIMA:
        return 0.0
    value = contestant.navigation_task.scorecard.observation_photo_value or 0
    return float(value) * len(get_contestant_observation_photos(contestant))


def get_track_polyline(contestant: Contestant) -> list[tuple[float, float]]:
    """The track the crew follows, as (latitude, longitude) pairs, in flying order."""
    waypoints = get_effective_route_waypoints(contestant.navigation_task, contestant)
    return [(wp.latitude, wp.longitude) for wp in waypoints if wp.type not in EXCLUDED_TRACK_GATE_TYPES]


def get_metres_per_mm(contestant: Contestant) -> float:
    """Ground distance of one millimetre on the contestant's printed map, from the flight order configuration."""
    configuration = getattr(contestant.navigation_task, "flightorderconfiguration", None)
    scale = configuration.map_scale if configuration else SCALE_TO_FIT
    # "Fit page" has no fixed scale, so it gets the same default as a task without a flight order configuration
    return metres_per_millimetre(scale if scale != SCALE_TO_FIT else DEFAULT_MAP_SCALE_THOUSANDS)


def resolve_photo(contestant: Contestant, photo_id: int) -> Photo:
    for photo in get_contestant_observation_photos(contestant):
        if photo.pk == photo_id:
            return photo
    raise PhotoObservationError(f"Photo {photo_id} is not an observation photo of this flight")


def _photo_coordinates(contestant: Contestant, photo: Photo) -> tuple[float, float]:
    # The target coordinates for this contestant may have been adjusted by their compiled task configuration
    config = getattr(contestant, "contestanttaskconfiguration", None)
    if config is not None and config.is_valid:
        for item in (config.compiled_effective_route_payload or {}).get("observation_photos", []):
            if item.get("name") == photo.name and item.get("coordinates"):
                longitude, latitude = item["coordinates"][:2]
                return latitude, longitude
    return photo.latitude, photo.longitude


def score_observation(
    contestant: Contestant, photo: Photo, latitude: float, longitude: float
) -> PhotoObservationResult:
    photo_latitude, photo_longitude = _photo_coordinates(contestant, photo)
    full_tolerance, half_tolerance = get_tolerances_mm(get_scoring_mode(contestant))
    return calculate_photo_observation(
        user_latitude=latitude,
        user_longitude=longitude,
        photo_latitude=photo_latitude,
        photo_longitude=photo_longitude,
        polyline=get_track_polyline(contestant),
        metres_per_mm=get_metres_per_mm(contestant),
        full_tolerance_mm=full_tolerance,
        half_tolerance_mm=half_tolerance,
    )


def calculate_score_change(contestant: Contestant, score_fraction: float) -> float:
    """
    The change to the contestant's score for an observation with this score fraction, in the direction of the
    scorecard (a deduction is negative on a descending scorecard).
    """
    mode = get_scoring_mode(contestant)
    scorecard = contestant.navigation_task.scorecard
    descending = scorecard.score_sorting_direction == "desc"
    if mode == MODE_LEGACY:
        magnitude = 0.0 if score_fraction > 0 else float(scorecard.observation_photo_penalty or 0)
    elif mode == MODE_CIMA:
        magnitude = float(scorecard.observation_photo_value or 0) * (1 - score_fraction)
        if magnitude and descending and scorecard.initial_score > 0:
            # The same 1000 * Q / Qmax normalization the gate component uses, with the observations in Qmax
            from display.calculators.cima_score_normalization import get_cima_gate_qmax

            qmax = get_cima_gate_qmax(contestant)
            if qmax:
                return -scorecard.initial_score * magnitude / qmax
    else:
        return 0.0
    return -magnitude if descending else magnitude


def _gate_name(photo: Photo) -> str:
    return f"OBS {photo.name}"[:30]


def _remove_existing_score(contestant: Contestant, photo: Photo) -> None:
    from display.services.administrative_penalties import AdministrativePenaltyService

    for entry in ScoreLogEntry.objects.filter(contestant=contestant, gate=_gate_name(photo)):
        AdministrativePenaltyService.remove_score_log_entry(entry)


def _apply_score(
    contestant: Contestant,
    photo: Photo,
    score_change: float,
    message: str,
    time: datetime.datetime,
    latitude: float,
    longitude: float,
) -> None:
    """Replaces any score previously given for this photo with this one."""
    _remove_existing_score(contestant, photo)
    gate = _gate_name(photo)
    if score_change != 0:
        gate_score, _ = GateCumulativeScore.objects.get_or_create(gate=gate, contestant=contestant)
        gate_score.points += score_change
        gate_score.save(update_fields=["points"])
        entry = ScoreLogEntry.create_and_push(
            contestant=contestant,
            time=time,
            gate=gate,
            type=ANOMALY,
            message=message,
            points=score_change,
            planned=None,
            actual=None,
            offset_string="",
            string=f"{gate}: {float(score_change)} points {message}",
            times_string="",
        )
        TrackAnnotation.create_and_push(
            contestant=contestant,
            latitude=latitude,
            longitude=longitude,
            message=entry.string,
            type=ANOMALY,
            gate=gate,
            gate_type=TURNPOINT,
            time=time,
            score_log_entry=entry,
        )
        contestant.contestanttrack.increment_score(score_change)
    Contestant.objects.filter(pk=contestant.pk).update(score_version=F("score_version") + 1)


def _describe(result: PhotoObservationResult, photo: Photo) -> str:
    if result.reason == "out_of_track":
        return f"Observation {photo.name}: out of track"
    if result.error_mm is None:
        return f"Observation {photo.name}: not scored ({result.reason})"
    return f"Observation {photo.name}: {result.error_mm:.1f} mm from the target (score {result.score_fraction:g})"


def _apply_result_fields(observation: PhotoObservation, result: PhotoObservationResult) -> None:
    observation.scored = result.scored
    observation.status = result.reason
    observation.error_m = result.error_m
    observation.error_mm = result.error_mm
    observation.score_fraction = result.score_fraction
    observation.metres_per_mm = result.metres_per_mm
    observation.projected_latitude = result.user_projection.latitude if result.user_projection else None
    observation.projected_longitude = result.user_projection.longitude if result.user_projection else None
    observation.photo_projected_latitude = result.photo_projection.latitude if result.photo_projection else None
    observation.photo_projected_longitude = result.photo_projection.longitude if result.photo_projection else None


def _save_scored_observation(observation: PhotoObservation, photo: Photo, result: PhotoObservationResult) -> None:
    contestant = observation.contestant
    _apply_result_fields(observation, result)
    # An observation that could not be scored (no route) is not held against the crew
    score_change = calculate_score_change(contestant, result.score_fraction) if result.scored else 0.0
    observation.points = score_change
    observation.save()
    _apply_score(
        contestant,
        photo,
        score_change,
        _describe(result, photo),
        observation.time,
        observation.latitude,
        observation.longitude,
    )


def register_photo_observation(
    contestant: Contestant,
    *,
    photo: int,
    time: datetime.datetime,
    latitude: float,
    longitude: float,
) -> tuple[PhotoObservation, bool]:
    """
    Registers (and scores) the crew's observation of a photo, identified by the photo's id. Registering the same
    photo again replaces the earlier registration only if it was made later, so that replays of queued requests
    from the app are harmless. Returns the stored observation and whether it was changed.
    """
    if time.tzinfo is None:
        time = time.replace(tzinfo=datetime.timezone.utc)
    photo_object = resolve_photo(contestant, photo)
    result = score_observation(contestant, photo_object, latitude, longitude)
    with transaction.atomic():
        observation, created = PhotoObservation.objects.select_for_update().get_or_create(
            contestant=contestant,
            photo=photo_object,
            defaults={"photo_name": photo_object.name, "time": time, "latitude": latitude, "longitude": longitude},
        )
        if not created:
            if time <= observation.time:
                return observation, False
            observation.time = time
            observation.latitude = latitude
            observation.longitude = longitude
        _save_scored_observation(observation, photo_object, result)
    _transmit(contestant)
    return observation, True


def delete_photo_observation(observation: PhotoObservation) -> None:
    contestant = observation.contestant
    photo = observation.photo
    with transaction.atomic():
        observation.delete()
        if photo is not None:
            _remove_existing_score(contestant, photo)
            Contestant.objects.filter(pk=contestant.pk).update(score_version=F("score_version") + 1)
    _transmit(contestant)


def rescore_contestant_observations(contestant: Contestant) -> int:
    """Re-scores all of a contestant's observations, e.g. after the map scale or scorecard changed."""
    count = 0
    for observation in contestant.photo_observations.select_related("photo").exclude(photo=None):
        result = score_observation(contestant, observation.photo, observation.latitude, observation.longitude)
        with transaction.atomic():
            _save_scored_observation(observation, observation.photo, result)
        count += 1
    if count:
        _transmit(contestant)
    return count


def finalize_photo_observations(contestant: Contestant) -> int:
    """
    Called when the flight ends: every observation photo that the crew did not mark is a miss. Safe to call more
    than once. Returns the number of misses scored.
    """
    if get_scoring_mode(contestant) is None:
        return 0
    # A reset of the track and score removes the score log, so give observations their score back first
    for observation in contestant.photo_observations.select_related("photo").exclude(photo=None):
        if (
            observation.points != 0
            and not ScoreLogEntry.objects.filter(contestant=contestant, gate=_gate_name(observation.photo)).exists()
        ):
            _apply_score(
                contestant,
                observation.photo,
                observation.points,
                f"Observation {observation.photo.name}: {observation.error_mm or 0:.1f} mm from the target",
                observation.time,
                observation.latitude,
                observation.longitude,
            )
    registered = set(contestant.photo_observations.values_list("photo_id", flat=True))
    missed = 0
    for photo in get_contestant_observation_photos(contestant):
        if (
            photo.pk in registered
            or ScoreLogEntry.objects.filter(contestant=contestant, gate=_gate_name(photo)).exists()
        ):
            continue
        latitude, longitude = _photo_coordinates(contestant, photo)
        _apply_score(
            contestant,
            photo,
            calculate_score_change(contestant, 0.0),
            f"Observation {photo.name}: not marked",
            contestant.finished_by_time,
            latitude,
            longitude,
        )
        missed += 1
    return missed


def _transmit(contestant: Contestant) -> None:
    from websocket_channels import WebsocketFacade

    try:
        WebsocketFacade().transmit_photo_observations(contestant)
    except Exception:
        logger.exception("Failed to push photo observations for contestant %s", contestant.pk)
