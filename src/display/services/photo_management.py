from __future__ import annotations

from typing import Any

from display.models import Photo
from display.utilities.gate_definitions import DUMMY, SECRETPOINT, UNKNOWN_LEG


def get_observation_photo_names(navigation_task) -> set[str]:
    """Names of the observation photos (the route's observation_photo features), as opposed to the photos of the
    route's waypoints and decoys that are also kept in the Photo table."""
    editable_route = navigation_task.editable_route
    if editable_route is None:
        return set()
    return {
        point["properties"]["name"]
        for point in editable_route.get_observation_photos()
        if point.get("properties", {}).get("name")
    }


def get_unknown_leg_photo_names(navigation_task) -> set[str]:
    """Names of the unknown-leg waypoints of a 2.A5 task, whose photos the flight order prints for the crews to find."""
    editable_route = navigation_task.editable_route
    if getattr(navigation_task, "task_subtype", None) != "unknown_legs" or editable_route is None:
        return set()
    return {
        point["properties"]["name"]
        for point in editable_route.get_unknown_leg_waypoints()
        if point.get("properties", {}).get("name")
    }


# Route points the flight order has no picture of (as on its turning point pages): the hidden gates, including the
# generated points of a curved leg, the dummy points and the unknown-leg points, whose photos are their own
NOT_PHOTOGRAPHED_POINT_TYPES = {SECRETPOINT, DUMMY, UNKNOWN_LEG}


def get_navigation_task_photo_targets(navigation_task) -> list[dict[str, Any]]:
    """
    What the organisers can give a photo of: the route's waypoints that the flight order shows a picture of, the
    catalogue turnpoints, the unknown-leg waypoints of a 2.A5 task and the observation photo markers. Each target's
    picture is generated from satellite images until the organisers upload their own.
    """
    targets: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    def add(name, latitude, longitude, target_kind):
        if not name or name in seen_names:
            return
        seen_names.add(name)
        targets.append({"name": name, "latitude": latitude, "longitude": longitude, "target_kind": target_kind})

    def add_features(features, target_kind, skip_point_types=frozenset()):
        for point in features:
            properties = point.get("properties", {})
            coordinates = point.get("geometry", {}).get("coordinates", [])
            if len(coordinates) != 2 or properties.get("pointType") in skip_point_types:
                continue
            lon, lat = coordinates
            add(properties.get("name"), lat, lon, target_kind)

    editable_route = navigation_task.editable_route
    if editable_route is not None:
        add_features(editable_route.get_ordered_track_waypoints(), "route_waypoint", NOT_PHOTOGRAPHED_POINT_TYPES)
    # Waypoints the route has without an editable-route feature (routes made before the route editor)
    for waypoint in navigation_task.route.waypoints:
        if getattr(waypoint, "type", None) not in NOT_PHOTOGRAPHED_POINT_TYPES:
            add(getattr(waypoint, "name", None), waypoint.latitude, waypoint.longitude, "route_waypoint")
    if editable_route is None:
        return targets
    add_features(editable_route.get_catalogue_turnpoints(), "catalogue_turnpoint")
    if getattr(navigation_task, "task_subtype", None) == "unknown_legs":
        add_features(editable_route.get_unknown_leg_waypoints(), "unknown_leg")
    add_features(editable_route.get_observation_photos(), "observation")
    return targets


def get_public_photo_names(navigation_task) -> set[str]:
    """
    Names of the photos everyone who may see the task may see: its photo targets, except the unknown-leg photos (they
    give the unknown legs away) and, when the task does not use observation registration, the observation photos (the
    answer key). Decoys are never among them, nor photos of points that are no longer photo targets (the hidden gates
    of older photo lists).
    """
    names = {target["name"] for target in get_navigation_task_photo_targets(navigation_task)}
    names -= get_unknown_leg_photo_names(navigation_task)
    if not navigation_task.allow_observation_registration:
        names -= get_observation_photo_names(navigation_task)
    return names


def photos_visible_to(user, photos) -> list[Photo]:
    """The photos the user may see: all of them on the tasks the user organises, the public ones on others"""
    visible: list[Photo] = []
    public_names_by_route: dict[int, set[str] | None] = {}
    for photo in photos:
        if photo.route_id not in public_names_by_route:
            navigation_task = getattr(photo.route, "navigationtask", None)
            # A route not yet in a task has nothing to give away
            organiser = navigation_task is None or (
                user is not None and user.is_authenticated and navigation_task.user_has_change_permissions(user)
            )
            public_names_by_route[photo.route_id] = None if organiser else get_public_photo_names(navigation_task)
        public_names = public_names_by_route[photo.route_id]
        if public_names is None or photo.name in public_names:
            visible.append(photo)
    return visible


def sync_navigation_task_photo_targets(navigation_task) -> list[Photo]:
    targets = get_navigation_task_photo_targets(navigation_task)
    ordered_photos: list[Photo] = []

    for target in targets:
        photo, created = Photo.objects.get_or_create(
            route=navigation_task.route,
            name=target["name"],
            defaults={
                "latitude": target["latitude"],
                "longitude": target["longitude"],
            },
        )

        fields_to_update: list[str] = []
        if photo.latitude != target["latitude"]:
            photo.latitude = target["latitude"]
            fields_to_update.append("latitude")
        if photo.longitude != target["longitude"]:
            photo.longitude = target["longitude"]
            fields_to_update.append("longitude")
        if fields_to_update:
            photo._leg = None
            fields_to_update.append("_leg")
            photo.save(update_fields=fields_to_update)

        if created or not photo.file:
            photo.generate_image(force=created)

        ordered_photos.append(photo)

    return ordered_photos


def revert_photo_to_satellite(photo: Photo) -> Photo:
    if photo.file:
        photo.file.delete(save=False)
        photo.file = None
    photo.uploaded = False
    photo.save(update_fields=["file", "uploaded"])
    photo.generate_image(force=True)
    photo.refresh_from_db()
    return photo


def get_decoy_collision_names(navigation_task) -> set[str]:
    """Names a decoy photo must not reuse: the real photo targets, which include the unknown-leg waypoints."""
    return {target["name"] for target in get_navigation_task_photo_targets(navigation_task)}


def create_decoy_photo(
    navigation_task, *, name: str, latitude: float, longitude: float, decoy_course: float | None = None
) -> Photo:
    """Register an organizer-authored decoy/false photo for 2.A5 unknown legs.

    Decoy photos are not tied to any real route feature - they exist purely
    to add difficulty by mixing false leads in among the genuine unknown-leg
    photos shown in the flight order. The name must not collide with a real
    feature name, since that would make the decoy indistinguishable from a
    genuine target to the rest of the photo-management pipeline.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("Decoy photo requires a name.")
    if name in get_decoy_collision_names(navigation_task):
        raise ValueError(
            f"'{name}' is already used by a real route feature. Choose a different name for the decoy photo."
        )
    if Photo.objects.filter(route=navigation_task.route, name=name).exists():
        raise ValueError(f"A photo named '{name}' already exists for this task.")

    photo = Photo.objects.create(
        route=navigation_task.route,
        name=name,
        latitude=latitude,
        longitude=longitude,
        is_decoy=True,
        decoy_course=decoy_course,
    )
    photo.generate_image(force=True)
    photo.refresh_from_db()
    return photo


def delete_decoy_photo(photo: Photo) -> None:
    if not photo.is_decoy:
        raise ValueError("Only decoy photos can be deleted through this action.")
    if photo.file:
        photo.file.delete(save=False)
    photo.delete()
