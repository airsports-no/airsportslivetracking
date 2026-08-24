from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from display.forms_wizards import ContestSelectForm, _no_compatible_task_types_message, _task_template_choices
from display.models import EditableRoute
from display.services.route_compatibility import (
    LEGACY_COMPILER_PRIMITIVE_KEYS,
    extract_route_primitives,
    get_blocking_reasons,
    get_compatible_task_subtypes,
)
from display.utilities.cima_task_type_definitions import (
    ANR_CATALOGUE,
    CIRCLE,
    DURATION,
    KNOWN_CIRCUIT,
    LEGACY_AIRSPORTS,
    LEGACY_ANR_CORRIDOR,
    LEGACY_LANDING,
    LEGACY_PRECISION,
    PRECISION_NAVIGATION,
)
from display.utilities.navigation_task_type_definitions import ANR_CORRIDOR, PRECISION
from display.views_wizards import _no_compatible_routes_message

TRACK_FEATURE = {
    "type": "Feature",
    "properties": {"featureType": "route_path"},
    "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]},
}


def waypoint_feature(point_type: str, name: str = "TP") -> dict:
    return {
        "type": "Feature",
        "properties": {
            "id": f"{name}-1",
            "name": name,
            "pointType": point_type,
            "featureType": "route_waypoint",
            "width": 1852,
            "isTiming": True,
            "isPassing": True,
            "sequence": 0,
        },
        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
    }


def landing_gate_feature() -> dict:
    return {
        "type": "Feature",
        "properties": {"id": "ldg-1", "name": "LDG", "featureType": "landing_gate"},
        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.0, 60.001]]},
    }


class TestRouteCompatibilityRuleset(TestCase):
    def test_route_with_track_is_compatible_with_all_backbone_legacy_families(self):
        route = EditableRoute.objects.create(
            name="Track route",
            route={"type": "FeatureCollection", "features": [TRACK_FEATURE, waypoint_feature("tp")]},
        )
        compatible = get_compatible_task_subtypes(route)
        for subtype in (LEGACY_PRECISION, LEGACY_ANR_CORRIDOR, LEGACY_AIRSPORTS):
            self.assertIn(subtype, compatible)

    def test_route_without_track_is_incompatible_with_backbone_legacy_families(self):
        route = EditableRoute.objects.create(name="Empty route", route={"type": "FeatureCollection", "features": []})
        compatible = get_compatible_task_subtypes(route)
        for subtype in (LEGACY_PRECISION, LEGACY_ANR_CORRIDOR, LEGACY_AIRSPORTS):
            self.assertNotIn(subtype, compatible)
        reasons = get_blocking_reasons(extract_route_primitives(route), LEGACY_PRECISION)
        self.assertIn("Missing required route feature: route_path", reasons)

    def test_dummy_waypoint_blocks_corridor_task_types_but_not_plain_precision(self):
        route = EditableRoute.objects.create(
            name="Dummy branch route",
            route={"type": "FeatureCollection", "features": [TRACK_FEATURE, waypoint_feature("dummy")]},
        )
        compatible = get_compatible_task_subtypes(route)
        self.assertIn(LEGACY_PRECISION, compatible)
        self.assertNotIn(LEGACY_ANR_CORRIDOR, compatible)
        self.assertNotIn(LEGACY_AIRSPORTS, compatible)
        reasons = get_blocking_reasons(extract_route_primitives(route), LEGACY_ANR_CORRIDOR)
        self.assertIn("Route feature not allowed for this task type: dummy_waypoint", reasons)

    def test_landing_requires_landing_gate(self):
        route_without_gate = EditableRoute.objects.create(
            name="No landing gate", route={"type": "FeatureCollection", "features": [TRACK_FEATURE]}
        )
        self.assertNotIn(LEGACY_LANDING, get_compatible_task_subtypes(route_without_gate))

        route_with_gate = EditableRoute.objects.create(
            name="Landing gate",
            route={"type": "FeatureCollection", "features": [landing_gate_feature()]},
        )
        self.assertIn(LEGACY_LANDING, get_compatible_task_subtypes(route_with_gate))

    def test_anr_catalogue_does_not_require_auxiliary_paths(self):
        # route_to_sp_path/route_from_fp_path are optional auxiliary compliance features that
        # most authored routes never have - a plain route with just a track is compatible.
        route = EditableRoute.objects.create(
            name="Plain ANR route",
            route={"type": "FeatureCollection", "features": [TRACK_FEATURE, waypoint_feature("tp")]},
        )
        self.assertEqual(get_blocking_reasons(extract_route_primitives(route), ANR_CATALOGUE), [])
        self.assertIn(ANR_CATALOGUE, get_compatible_task_subtypes(route))

    def test_route_waypoint_required_for_backbone_task_types_but_not_no_backbone_ones(self):
        # A track with no route_waypoint Point features (e.g. authored purely for a no-backbone
        # subtype like circle) must not satisfy any task type that needs an actual backbone.
        route = EditableRoute.objects.create(
            name="Track only, no waypoints",
            route={"type": "FeatureCollection", "features": [TRACK_FEATURE]},
        )
        compatible = get_compatible_task_subtypes(route)
        for subtype in (
            LEGACY_PRECISION,
            LEGACY_ANR_CORRIDOR,
            LEGACY_AIRSPORTS,
            PRECISION_NAVIGATION,
            KNOWN_CIRCUIT,
            ANR_CATALOGUE,
        ):
            self.assertNotIn(subtype, compatible)

    def test_hidden_gate_is_never_required(self):
        # Hidden gates are optional evidence on every task type, not a structural prerequisite.
        route = EditableRoute.objects.create(
            name="Plain precision route",
            route={
                "type": "FeatureCollection",
                "features": [TRACK_FEATURE, waypoint_feature("sp", "SP"), waypoint_feature("fp", "FP")],
            },
        )
        for subtype in (PRECISION_NAVIGATION, KNOWN_CIRCUIT):
            self.assertEqual(get_blocking_reasons(extract_route_primitives(route), subtype), [])
            self.assertIn(subtype, get_compatible_task_subtypes(route))

    def test_circle_requires_all_four_markers(self):
        route = EditableRoute.objects.create(
            name="Partial circle",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"id": "cm-1", "name": "CM", "featureType": "circle_center_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    }
                ],
            },
        )
        reasons = get_blocking_reasons(extract_route_primitives(route), CIRCLE)
        self.assertIn("Missing required route feature: circle_start_marker", reasons)
        self.assertIn("Missing required route feature: circle_entry_marker", reasons)
        self.assertIn("Missing required route feature: circle_exit_marker", reasons)
        self.assertNotIn(CIRCLE, get_compatible_task_subtypes(route))

    def test_unsaved_route_with_no_features_key_returns_no_primitives(self):
        # Model default for `route` is an empty list, not {"features": []} - must not crash.
        route = EditableRoute(name="Brand new, unsaved")
        self.assertEqual(extract_route_primitives(route), {})
        # DURATION (2.B3) has no required primitives, so it's trivially compatible with any route,
        # including one with no content at all.
        self.assertEqual(get_compatible_task_subtypes(route), ["duration"])

    def test_duration_does_not_require_takeoff_or_landing_gate(self):
        # calculator_factory.py always adds SpeedInferredTakeoffLandingCalculator for DURATION
        # tasks, a fallback source of takeoff/landing events for routes with no authored gates.
        route = EditableRoute.objects.create(
            name="No gates", route={"type": "FeatureCollection", "features": [TRACK_FEATURE]}
        )
        self.assertIn(DURATION, get_compatible_task_subtypes(route))


class TestTaskTemplateChoicesRouteFiltering(TestCase):
    def test_no_route_leaves_choices_unfiltered(self):
        choices = _task_template_choices(user=None, editable_route=None)
        legacy_keys = dict(dict(choices).get("Legacy", ()))
        self.assertIn(PRECISION, legacy_keys)
        self.assertIn(ANR_CORRIDOR, legacy_keys)

    def test_incompatible_route_hard_filters_out_task_types(self):
        route = EditableRoute.objects.create(
            name="Dummy branch route",
            route={"type": "FeatureCollection", "features": [TRACK_FEATURE, waypoint_feature("dummy")]},
        )
        choices = _task_template_choices(user=None, editable_route=route)
        legacy_keys = dict(dict(choices).get("Legacy", ()))
        self.assertIn(PRECISION, legacy_keys)
        self.assertNotIn(ANR_CORRIDOR, legacy_keys)

    def test_empty_route_yields_no_legacy_choices(self):
        route = EditableRoute.objects.create(name="Empty", route={"type": "FeatureCollection", "features": []})
        choices = _task_template_choices(user=None, editable_route=route)
        groups = dict(choices)
        self.assertNotIn("Legacy", groups)


class TestNoCompatibleTaskTypesMessage(TestCase):
    def setUp(self):
        # can_user_see_task_subtype treats user=None as unrestricted ("no user context"), so
        # exercising the gated-out case requires a real, ungranted, non-superuser account.
        self.user = get_user_model().objects.create(email="no-compatible-types@example.com")

    @override_settings(GATE_CIMA_TASK_VISIBILITY=True, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
    def test_message_names_closest_match_when_nothing_is_compatible(self):
        # Duration (2.B3) has no required primitives so it's normally always compatible; gating
        # CIMA visibility out here is what makes "zero compatible choices" actually reachable.
        route = EditableRoute.objects.create(name="Empty", route={"type": "FeatureCollection", "features": []})
        message = _no_compatible_task_types_message(self.user, route)
        self.assertIsNotNone(message)
        self.assertIn("closest match", message)

    def test_message_is_none_when_route_has_no_blocking_reasons(self):
        # Duration is unconditionally compatible with any route by default (CIMA visible), so
        # there's nothing to explain.
        route = EditableRoute.objects.create(name="Empty", route={"type": "FeatureCollection", "features": []})
        self.assertIsNone(_no_compatible_task_types_message(self.user, route))

    @override_settings(GATE_CIMA_TASK_VISIBILITY=True, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
    def test_contest_select_form_exposes_message_when_choices_are_empty(self):
        route = EditableRoute.objects.create(name="Empty", route={"type": "FeatureCollection", "features": []})
        form = ContestSelectForm(user=self.user, editable_route=route)
        self.assertEqual(form.fields["task_template"].choices, [])
        self.assertIsNotNone(form.no_compatible_task_types_message)

    def test_contest_select_form_has_no_message_when_choices_exist(self):
        route = EditableRoute.objects.create(
            name="Plain precision route",
            route={"type": "FeatureCollection", "features": [TRACK_FEATURE, waypoint_feature("tp")]},
        )
        form = ContestSelectForm(user=self.user, editable_route=route)
        self.assertTrue(form.fields["task_template"].choices)
        self.assertIsNone(form.no_compatible_task_types_message)


class TestNoCompatibleRoutesMessage(TestCase):
    def test_message_lists_required_and_forbidden_primitives(self):
        message = _no_compatible_routes_message(CIRCLE)
        self.assertIn("circle_center_marker", message)
        self.assertIn("circle_start_marker", message)

    def test_message_lists_forbidden_primitives_for_anr_corridor(self):
        message = _no_compatible_routes_message(LEGACY_ANR_CORRIDOR)
        self.assertIn("must not have", message)
        self.assertIn("dummy_waypoint", message)


class TestTaskCompilerPrimitivesContractUnchanged(TestCase):
    def test_build_compiled_primitives_keys_match_historical_contract(self):
        route = EditableRoute.objects.create(
            name="Contract check",
            route={"type": "FeatureCollection", "features": [TRACK_FEATURE, waypoint_feature("tp")]},
        )
        primitives = extract_route_primitives(route)
        subset = {key: primitives[key] for key in LEGACY_COMPILER_PRIMITIVE_KEYS}
        self.assertEqual(set(subset.keys()), set(LEGACY_COMPILER_PRIMITIVE_KEYS))
        # route_path/route_waypoint/takeoff_gate/landing_gate are ruleset-only additions and must
        # not leak into the persisted compiled_primitives contract.
        self.assertNotIn("route_path", subset)
        self.assertNotIn("route_waypoint", subset)
        self.assertNotIn("takeoff_gate", subset)
        self.assertNotIn("landing_gate", subset)
