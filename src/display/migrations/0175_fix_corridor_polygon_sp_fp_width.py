import copy
from collections import Counter

from django.db import migrations


def _uniform_width_waypoints(waypoints):
    """
    Same normalization as 0174's _uniform_width_waypoints - duplicated here rather than
    imported, since migration data functions shouldn't depend on another migration's private
    helpers (0174 could be squashed away later).

    Returns (normalized_waypoints, changed): a copy of ``waypoints`` with the SP/FP width
    matched to the interior ("secret") waypoints' width, for feeding into
    generate_corridor_polygon(). ``changed`` is False when SP/FP already matched (nothing to
    fix) or there are no interior waypoints to compare against.
    """
    interior_widths = [wp.width for wp in waypoints if wp.type not in ("sp", "fp")]
    if not interior_widths:
        return waypoints, False

    reference_width = Counter(interior_widths).most_common(1)[0][0]

    normalized = list(waypoints)
    changed = False
    for index, wp in enumerate(waypoints):
        if wp.type in ("sp", "fp") and wp.width != reference_width:
            wp_copy = copy.copy(wp)
            wp_copy.width = reference_width
            normalized[index] = wp_copy
            changed = True
    return normalized, changed


def fix_corridor_polygon_sp_fp_width(apps, schema_editor):
    """
    Re-fixes corridor_polygon on ANR Corridor routes whose SP/FP waypoint width diverges from
    the rest of the route (see 0174's _uniform_width_waypoints docstring for why that happens
    on legacy data).

    Scoped to ANR_CORRIDOR only, NOT the other two corridor-family task types (AIRSPORTS,
    AIRSPORT_CHALLENGE) that 0174 covers for its own (different) purpose. ANR routes are
    uniform-width along their whole length by construction - see create_anr_route
    (display/models/editable_route.py), which always passes an explicit corridor_width so
    every waypoint including SP/FP gets the same width. AIRSPORTS/AIRSPORT_CHALLENGE routes
    (create_airsports_route) have no such constraint: _create_waypoint_list() falls back to
    each point's own individually-configured width when no corridor_width is passed, so a
    genuinely different SP/FP width on those routes is a legitimate route-editor choice, not a
    bug - normalizing it the way this migration does for ANR would corrupt real data. A dev-DB
    check found 55 AIRSPORTS/AIRSPORT_CHALLENGE routes with a "mismatched" SP/FP width that
    must NOT be touched, alongside 51 genuinely-buggy ANR_CORRIDOR routes that should be.

    0174 (this migration's predecessor) was supposed to fix this when it backfilled
    corridor_polygon, but the fix landed in a later commit that edited 0174's *file* after
    0174 had already run and been recorded as applied in django_migrations - Django tracks
    migrations by (app, name), not file content, so redeploying that edit did not re-run it.
    Every ANR route 0174 backfilled in production still has the original SP/FP-bulged polygon.

    This migration doesn't gate on corridor_polygon being empty (0174's guard) - it looks at
    every ANR_CORRIDOR route with waypoints and regenerates corridor_polygon whenever SP/FP
    width doesn't match the interior width, whether or not a polygon already exists. That
    covers both 0174's backfilled-but-wrong routes and any pre-existing routes that were
    originally created with this same width bug baked in (confirmed present on some routes
    that already had a non-empty polygon before 0174 ever ran).
    """
    from display.utilities.corridor_renderer import generate_corridor_polygon
    from display.utilities.navigation_task_type_definitions import ANR_CORRIDOR

    CORRIDOR_TASK_TYPES = {ANR_CORRIDOR}

    NavigationTask = apps.get_model("display", "NavigationTask")
    Scorecard = apps.get_model("display", "Scorecard")
    Route = apps.get_model("display", "Route")

    # See 0174 for why .only() rather than select_related() here.
    scorecard_task_types = dict(Scorecard.objects.only("id", "task_type").values_list("id", "task_type"))

    fixed = 0
    for _navigation_task_id, route_id, scorecard_id, original_scorecard_id in NavigationTask.objects.values_list(
        "id", "route_id", "scorecard_id", "original_scorecard_id"
    ).iterator():
        effective_scorecard_id = scorecard_id or original_scorecard_id
        task_type = scorecard_task_types.get(effective_scorecard_id) or []
        # See 0174 for why this bare-string normalization is needed.
        if isinstance(task_type, str):
            task_type = [task_type]
        if not CORRIDOR_TASK_TYPES.intersection(task_type):
            continue

        route = Route.objects.only("id", "corridor_polygon", "waypoints", "rounded_corners").get(pk=route_id)
        if not route.waypoints or len(route.waypoints) < 2:
            continue

        normalized_waypoints, changed = _uniform_width_waypoints(route.waypoints)
        if not changed:
            continue

        corridor_polygon, _path_points = generate_corridor_polygon(normalized_waypoints, route.rounded_corners)
        if not corridor_polygon:
            continue

        route.corridor_polygon = corridor_polygon
        route.save(update_fields=["corridor_polygon"])
        fixed += 1

    if fixed:
        print(f"\n  Re-fixed corridor_polygon SP/FP width on {fixed} route(s).")


def noop_reverse(apps, schema_editor):
    # Regenerated polygons are derived data, not something to blank back out on rollback.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0174_backfill_route_corridor_polygon"),
    ]

    operations = [
        migrations.RunPython(fix_corridor_polygon_sp_fp_width, noop_reverse),
    ]
