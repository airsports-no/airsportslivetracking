import copy
from collections import Counter

from django.db import migrations


def _uniform_width_waypoints(waypoints):
    """
    Returns a copy of ``waypoints`` with the SP/FP width normalized to match the interior
    ("secret") waypoints, for feeding into generate_corridor_polygon().

    ANR-family corridors are uniform-width along their whole length by design - see
    EditableRoute._create_waypoint_list (display/models/editable_route.py), which assigns the
    same corridor_width to every waypoint including SP/FP when building a route through the
    current pipeline (its commented-out lines 460/465 show an SP/FP-specific "extended gate
    width" override that has since been disabled). Some legacy routes (e.g. navigation task
    1197's route 1721: interior waypoints at 0.3 NM, SP/FP at 1.0 NM) were created back when
    that override was active, so their stored SP/FP width is wider than the rest of the route.
    generate_corridor_polygon() uses each waypoint's own width, so feeding it that legacy data
    unmodified bulges the polygon's first and last legs out to the SP/FP width instead of the
    correct uniform corridor width.

    Only SP/FP are touched, and only for this function's own polygon computation - the
    waypoints actually stored on the route (and their real .width) are left untouched.
    """
    interior_widths = [wp.width for wp in waypoints if wp.type not in ("sp", "fp")]
    if not interior_widths:
        return waypoints

    # Mode rather than the first interior point's width, in case one interior waypoint is
    # itself an outlier - the width shared by the most waypoints is the corridor's real width.
    reference_width = Counter(interior_widths).most_common(1)[0][0]

    normalized = list(waypoints)
    for index, wp in enumerate(waypoints):
        if wp.type in ("sp", "fp") and wp.width != reference_width:
            wp_copy = copy.copy(wp)
            wp_copy.width = reference_width
            normalized[index] = wp_copy
    return normalized


def backfill_corridor_polygon(apps, schema_editor):
    """
    Backfills Route.corridor_polygon for corridor-type routes (ANR Corridor / Air Sports
    Race / Air Sport Challenge) that predate that field.

    corridor_polygon was added by 0121_route_corridor_polygon and is normally computed once,
    at route-creation time, by create_anr_corridor_route_from_waypoint_list() /
    EditableRoute.create_airsports_route() calling generate_corridor_polygon() on the
    waypoint list - nothing re-derives it later. Routes created before that field existed
    (some via the current EditableRoute pipeline, some via an older ad hoc path that predates
    EditableRoute entirely - e.g. navigation task 1197, which has editable_route=None) just
    got the model default ([]) and were never backfilled. An empty corridor_polygon breaks
    both the frontend corridor rendering (RouteRenderer.tsx's renderAirsportsRoute only draws
    the corridor from this field) and live corridor-deviation scoring
    (anr_corridor_calculator.py's build_polygon() reads the same field).

    This recomputes corridor_polygon from each affected route's already-stored waypoints
    (lat/lon/width - unaffected by this gap, aside from the legacy SP/FP width quirk
    _uniform_width_waypoints() corrects for) using the same generate_corridor_polygon()
    function real route creation uses. It touches only corridor_polygon: gate_line and every
    other waypoint field are left exactly as they are, since those already render/score
    correctly for these legacy routes and re-deriving them risks changing data that isn't
    actually broken.
    """
    from display.utilities.corridor_renderer import generate_corridor_polygon
    from display.utilities.navigation_task_type_definitions import AIRSPORT_CHALLENGE, AIRSPORTS, ANR_CORRIDOR

    CORRIDOR_TASK_TYPES = {ANR_CORRIDOR, AIRSPORTS, AIRSPORT_CHALLENGE}

    NavigationTask = apps.get_model("display", "NavigationTask")
    Scorecard = apps.get_model("display", "Scorecard")
    Route = apps.get_model("display", "Route")

    # Deliberately fetched with .only() rather than select_related(): Scorecard carries a
    # long tail of fields unrelated to this migration (mid-flight in a separate schema
    # migration elsewhere), and a full-row fetch has no upside here - task_type is all this
    # needs.
    scorecard_task_types = dict(Scorecard.objects.only("id", "task_type").values_list("id", "task_type"))

    updated = 0
    skipped_short = 0
    for _navigation_task_id, route_id, scorecard_id, original_scorecard_id in NavigationTask.objects.values_list(
        "id", "route_id", "scorecard_id", "original_scorecard_id"
    ).iterator():
        effective_scorecard_id = scorecard_id or original_scorecard_id
        task_type = scorecard_task_types.get(effective_scorecard_id) or []
        # Scorecard.task_type is nominally a list, but a large share of legacy rows (630 of
        # 1654 in a spot check) have it pickled as a bare string instead (e.g. "anr_corridor"
        # rather than ["anr_corridor"]) - set.intersection() on a bare string iterates its
        # characters and silently matches nothing, so normalize before intersecting.
        if isinstance(task_type, str):
            task_type = [task_type]
        if not CORRIDOR_TASK_TYPES.intersection(task_type):
            continue

        route = Route.objects.only("id", "corridor_polygon", "waypoints", "rounded_corners").get(pk=route_id)
        if route.corridor_polygon:
            continue
        if not route.waypoints or len(route.waypoints) < 2:
            continue

        corridor_polygon, _path_points = generate_corridor_polygon(
            _uniform_width_waypoints(route.waypoints), route.rounded_corners
        )
        if not corridor_polygon:
            skipped_short += 1
            continue

        route.corridor_polygon = corridor_polygon
        route.save(update_fields=["corridor_polygon"])
        updated += 1

    if updated or skipped_short:
        print(
            f"\n  Backfilled corridor_polygon on {updated} route(s); "
            f"{skipped_short} corridor-type route(s) had too few usable waypoints to generate a polygon."
        )


def noop_reverse(apps, schema_editor):
    # Regenerated polygons are derived data, not something to blank back out on rollback.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0173_scorecard_config_rename_legacy_columns"),
    ]

    operations = [
        migrations.RunPython(backfill_corridor_polygon, noop_reverse),
    ]
