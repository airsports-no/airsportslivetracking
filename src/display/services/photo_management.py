from __future__ import annotations

from typing import Any

from display.models import Photo


def get_navigation_task_photo_targets(navigation_task) -> list[dict[str, Any]]:
    if getattr(navigation_task, "task_subtype", None) in {"known_circuit", "unknown_legs"}:
        editable_route = navigation_task.editable_route
        if editable_route is None:
            return []
        targets: list[dict[str, Any]] = []
        for point in editable_route.get_observation_photos():
            properties = point.get("properties", {})
            geometry = point.get("geometry", {})
            coordinates = geometry.get("coordinates", [])
            name = properties.get("name")
            if not name or len(coordinates) != 2:
                continue
            lon, lat = coordinates
            targets.append(
                {
                    "name": name,
                    "latitude": lat,
                    "longitude": lon,
                    "target_kind": "observation",
                }
            )
        return targets

    targets: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    editable_route = navigation_task.editable_route
    if editable_route is not None:
        for point in editable_route.get_ordered_track_waypoints():
            properties = point.get("properties", {})
            geometry = point.get("geometry", {})
            coordinates = geometry.get("coordinates", [])
            name = properties.get("name")
            if not name or name in seen_names or len(coordinates) != 2:
                continue
            seen_names.add(name)
            lon, lat = coordinates
            targets.append(
                {
                    "name": name,
                    "latitude": lat,
                    "longitude": lon,
                    "target_kind": "route_waypoint",
                }
            )

    for waypoint in navigation_task.route.waypoints:
        name = getattr(waypoint, "name", None)
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        targets.append(
            {
                "name": name,
                "latitude": waypoint.latitude,
                "longitude": waypoint.longitude,
                "target_kind": "route_waypoint",
            }
        )

    if editable_route is None:
        return targets

    for point in editable_route.get_catalogue_turnpoints():
        properties = point.get("properties", {})
        geometry = point.get("geometry", {})
        coordinates = geometry.get("coordinates", [])
        name = properties.get("name")
        if not name or name in seen_names or len(coordinates) != 2:
            continue
        seen_names.add(name)
        lon, lat = coordinates
        targets.append(
            {
                "name": name,
                "latitude": lat,
                "longitude": lon,
                "target_kind": "catalogue_turnpoint",
            }
        )

    return targets


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
        photo.save(update_fields=["file"])
    photo.generate_image(force=True)
    photo.refresh_from_db()
    return photo


def get_decoy_collision_names(navigation_task) -> set[str]:
    """Names a decoy photo must not reuse: real photo targets plus unknown-leg
    trigger names (the latter aren't in get_navigation_task_photo_targets,
    which only covers observation_photo markers for unknown_legs tasks).
    """
    names = {target["name"] for target in get_navigation_task_photo_targets(navigation_task)}
    editable_route = navigation_task.editable_route
    if editable_route is not None:
        names.update(
            properties.get("name")
            for properties in (item.get("properties", {}) for item in editable_route.get_unknown_leg_waypoints())
            if properties.get("name")
        )
    return names


def create_decoy_photo(navigation_task, *, name: str, latitude: float, longitude: float, decoy_course: float | None = None) -> Photo:
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
        raise ValueError(f"'{name}' is already used by a real route feature. Choose a different name for the decoy photo.")
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
