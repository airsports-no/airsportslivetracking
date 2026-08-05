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
