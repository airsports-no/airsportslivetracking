"""
The route requirements of every task type: a minimal route that satisfies each task type, a route that breaks exactly one
requirement at a time, and that the route editor's compatibility check, the task creation check and TaskCompiler's
validation all reach the same verdict.
"""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from display.calculators.tests.flight_simulator import (
    circle_route_geojson,
    contract_route_geojson,
    hunt_route_geojson,
    landing_area_feature,
    precision_route_geojson,
    runway_gate_feature,
)
from display.models import EditableRoute
from display.services.route_compatibility import (
    ROUTE_COMPATIBILITY_RULESET_VERSION,
    assert_route_compatible_with_task_type,
    evaluate_route_requirements,
    extract_route_primitives,
    get_blocking_reasons,
    get_compatible_task_subtypes,
    get_unmet_requirements,
    no_compatible_routes_message,
)
from display.services.task_compiler import TaskCompiler
from display.utilities import route_requirements as rr
from display.utilities.task_types import (
    ANR_CATALOGUE,
    ANR_CORRIDOR,
    CIRCLE,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    DURATION,
    KNOWN_CIRCUIT,
    LEGACY_AIRSPORT_CHALLENGE,
    LEGACY_AIRSPORTS,
    LEGACY_ANR_CORRIDOR,
    LEGACY_LANDING,
    LEGACY_POKER,
    LEGACY_PRECISION,
    LIMITED_FUEL_TURNPOINT_HUNT,
    PRECISION,
    PRECISION_NAVIGATION,
    TASK_TYPE_REGISTRY,
    TURNPOINT_HUNT,
    UNKNOWN_LEGS,
)

START = (60.0, 11.0)
EXTENSION = {"TP1": [(0.0, 3000.0)]}


def features_of(geojson: dict) -> list[dict]:
    return copy.deepcopy(geojson["features"])


def collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def without(geojson: dict, *, feature_type: str | None = None, name: str | None = None, **properties) -> dict:
    """The route without the features of [feature_type] (and [name], and the given property values)."""

    def matches(feature):
        props = feature.get("properties", {})
        return (
            (feature_type is None or props.get("featureType") == feature_type)
            and (name is None or props.get("name") == name)
            and all(props.get(key) == value for key, value in properties.items())
        )

    return collection([feature for feature in features_of(geojson) if not matches(feature)])


def with_features(geojson: dict, *extra: dict) -> dict:
    return collection(features_of(geojson) + [copy.deepcopy(item) for item in extra])


def with_properties(geojson: dict, waypoint: str, **properties) -> dict:
    """The route where the waypoint named [waypoint] has the given properties changed."""
    features = features_of(geojson)
    for feature in features:
        if (
            feature["properties"].get("name") == waypoint
            and feature["properties"].get("featureType") == "route_waypoint"
        ):
            feature["properties"].update(properties)
            return collection(features)
    raise AssertionError(f"No waypoint {waypoint}")


def circle_marker(feature_type: str) -> dict:
    return next(
        feature
        for feature in circle_route_geojson(START)["features"]
        if feature["properties"]["featureType"] == feature_type
    )


def waypoint_copy(geojson: dict, name: str, new_name: str, sequence: int, **properties) -> dict:
    feature = copy.deepcopy(
        next(
            f
            for f in geojson["features"]
            if f["properties"].get("name") == name and f["properties"].get("featureType") == "route_waypoint"
        )
    )
    feature["properties"].update(name=new_name, id=f"copy-{sequence}", sequence=sequence, **properties)
    return feature


PRECISION_ROUTE = precision_route_geojson()
HIDDEN_GATE_ROUTE = precision_route_geojson(hidden_gates={1: [0.5]})
# Only SP and FP: no timed turn point, hidden gate or photo.
BARE_ROUTE = precision_route_geojson(legs=((90.0, 6000.0),))
# Turn points that are not time gates.
UNTIMED_TURN_POINTS_ROUTE = precision_route_geojson(untimed=("TP1", "TP2"))
# Hidden gate and nothing else besides SP and FP.
BARE_HIDDEN_GATE_ROUTE = precision_route_geojson(legs=((90.0, 6000.0),), hidden_gates={0: [0.5]})
# SP, one turn point that is not timed, FP: the turn point counts once it is timed.
BARE_ROUTE_WITH_TP = precision_route_geojson(legs=((90.0, 6000.0), (160.0, 5000.0)), untimed=("TP1",))
CURVED_ROUTE = precision_route_geojson(curved=["TP1"])
CONTRACT_ROUTE = contract_route_geojson(catalogue={"A": (5000.0, 1000.0)})
UNKNOWN_LEGS_ROUTE = precision_route_geojson(unknown_legs=EXTENSION)
HUNT_ROUTE = hunt_route_geojson(
    compulsory={"CP1": (2000.0, 0.0), "CP2": (4000.0, 0.0), "CP3": (6000.0, 0.0)},
    catalogue={"A": (3000.0, 1000.0, None)},
)
CIRCLE_ROUTE = circle_route_geojson(START)
DURATION_ROUTE = collection([landing_area_feature(START, (17000, 19000), (-500, 500))])
LANDING_ROUTE = collection([runway_gate_feature("landing", START, 5000.0)])
TRACK = next(f for f in PRECISION_ROUTE["features"] if f["properties"]["featureType"] == "route_path")


def hunt_without_gate(geojson: dict) -> dict:
    return without(geojson, feature_type="known_time_gate", name="CP3")


def hunt_with_four_gates() -> dict:
    return with_features(HUNT_ROUTE, hunt_route_geojson(compulsory={"CP4": (8000.0, 0.0)})["features"][0])


def circle_without(feature_type: str) -> dict:
    return without(CIRCLE_ROUTE, feature_type=feature_type)


def circle_with_two(feature_type: str) -> dict:
    return with_features(CIRCLE_ROUTE, circle_marker(feature_type))


def with_dummy_waypoint() -> dict:
    return with_features(PRECISION_ROUTE, waypoint_copy(PRECISION_ROUTE, "TP1", "DUMMY1", 10, pointType="dummy"))


def contract_with_extra_waypoint() -> dict:
    return with_features(CONTRACT_ROUTE, waypoint_copy(CONTRACT_ROUTE, "MP", "WP 2", 5, pointType="tp"))


def unknown_legs_with_two_waypoints() -> dict:
    features = [
        f
        for f in features_of(UNKNOWN_LEGS_ROUTE)
        if f["properties"].get("name") not in ("TP2", "FP") or f["properties"]["featureType"] == "route_path"
    ]
    return collection(features)


def precision_with_two_waypoints() -> dict:
    return without(without(HIDDEN_GATE_ROUTE, name="TP1"), name="TP2")


def with_dummy_branch_removed() -> dict:
    return without(UNKNOWN_LEGS_ROUTE, feature_type="dummy_branch_waypoint")


# For every task type: a route that satisfies all its requirements, and for every requirement key the routes that
# break that requirement and no other.
CASES = {
    LEGACY_PRECISION: (
        PRECISION_ROUTE,
        {
            "route_path": [without(PRECISION_ROUTE, feature_type="route_path")],
            "route_waypoint": [without(PRECISION_ROUTE, feature_type="route_waypoint")],
        },
    ),
    LEGACY_POKER: (
        PRECISION_ROUTE,
        {
            "route_path": [without(PRECISION_ROUTE, feature_type="route_path")],
            "route_waypoint": [without(PRECISION_ROUTE, feature_type="route_waypoint")],
        },
    ),
    LEGACY_LANDING: (LANDING_ROUTE, {"landing_gate": [without(LANDING_ROUTE, feature_type="landing_gate")]}),
    CURVE_NAVIGATION_TIME_ESTIMATION: (
        CURVED_ROUTE,
        {
            "route_path": [without(CURVED_ROUTE, feature_type="route_path")],
            "route_waypoint": [without(CURVED_ROUTE, feature_type="route_waypoint")],
            "curved_leg": [PRECISION_ROUTE, with_properties(CURVED_ROUTE, "TP1", controlLat=None, controlLng=None)],
        },
    ),
    PRECISION_NAVIGATION: (
        HIDDEN_GATE_ROUTE,
        {
            "route_path": [without(HIDDEN_GATE_ROUTE, feature_type="route_path")],
            "route_waypoints": [
                without(HIDDEN_GATE_ROUTE, feature_type="route_waypoint"),
                without(precision_with_two_waypoints(), name="HG1"),
            ],
            "hidden_gate": [PRECISION_ROUTE, without(HIDDEN_GATE_ROUTE, name="HG1")],
            "route_waypoint_order": [
                with_properties(HIDDEN_GATE_ROUTE, "FP", pointType="tp"),
                with_properties(HIDDEN_GATE_ROUTE, "SP", pointType="tp"),
            ],
        },
    ),
    CONTRACT_NAVIGATION_TIME_CONTROLS: (
        CONTRACT_ROUTE,
        {
            "route_path": [without(CONTRACT_ROUTE, feature_type="route_path")],
            "route_waypoints": [contract_with_extra_waypoint(), without(CONTRACT_ROUTE, name="MP")],
            "route_waypoint_order": [with_properties(CONTRACT_ROUTE, "MP", name="M2")],
            "catalogue_turnpoint": [without(CONTRACT_ROUTE, feature_type="catalogue_turnpoint")],
        },
    ),
    KNOWN_CIRCUIT: (
        HIDDEN_GATE_ROUTE,
        {
            "route_path": [without(HIDDEN_GATE_ROUTE, feature_type="route_path")],
            "route_waypoint": [without(HIDDEN_GATE_ROUTE, feature_type="route_waypoint")],
            "known_circuit_evidence": [BARE_ROUTE, UNTIMED_TURN_POINTS_ROUTE],
        },
    ),
    UNKNOWN_LEGS: (
        UNKNOWN_LEGS_ROUTE,
        {
            "route_path": [without(UNKNOWN_LEGS_ROUTE, feature_type="route_path")],
            "route_waypoints": [unknown_legs_with_two_waypoints()],
            "route_waypoint_order": [with_properties(UNKNOWN_LEGS_ROUTE, "FP", pointType="tp")],
            "unknown_leg": [PRECISION_ROUTE],
            "unknown_leg_extension": [with_dummy_branch_removed()],
        },
    ),
    TURNPOINT_HUNT: (
        HUNT_ROUTE,
        {
            "route_path": [with_features(HUNT_ROUTE, TRACK)],
            "known_time_gate": [hunt_without_gate(HUNT_ROUTE), hunt_with_four_gates()],
            "catalogue_turnpoint": [without(HUNT_ROUTE, feature_type="catalogue_turnpoint")],
        },
    ),
    CIRCLE: (
        CIRCLE_ROUTE,
        {
            "circle_start_marker": [circle_without("circle_start_marker"), circle_with_two("circle_start_marker")],
            "circle_center_marker": [circle_without("circle_center_marker"), circle_with_two("circle_center_marker")],
            "circle_entry_marker": [circle_without("circle_entry_marker"), circle_with_two("circle_entry_marker")],
            "circle_exit_marker": [circle_without("circle_exit_marker"), circle_with_two("circle_exit_marker")],
        },
    ),
    ANR_CATALOGUE: (
        PRECISION_ROUTE,
        {
            "route_path": [without(PRECISION_ROUTE, feature_type="route_path")],
            "route_waypoint": [without(PRECISION_ROUTE, feature_type="route_waypoint")],
        },
    ),
    LIMITED_FUEL_TURNPOINT_HUNT: (
        HUNT_ROUTE,
        {
            "route_path": [with_features(HUNT_ROUTE, TRACK)],
            "known_time_gate": [hunt_without_gate(HUNT_ROUTE), hunt_with_four_gates()],
            "catalogue_turnpoint": [without(HUNT_ROUTE, feature_type="catalogue_turnpoint")],
        },
    ),
    DURATION: (DURATION_ROUTE, {"duration_landing_area": [collection([]), collection([TRACK])]}),
}
for _legacy_corridor in (LEGACY_ANR_CORRIDOR, LEGACY_AIRSPORTS, LEGACY_AIRSPORT_CHALLENGE):
    CASES[_legacy_corridor] = (
        PRECISION_ROUTE,
        {
            "route_path": [without(PRECISION_ROUTE, feature_type="route_path")],
            "route_waypoint": [without(PRECISION_ROUTE, feature_type="route_waypoint")],
            "dummy_waypoint": [with_dummy_waypoint()],
            "unknown_leg": [UNKNOWN_LEGS_ROUTE],
        },
    )


# A route without waypoints has no curved leg either: for these the requirement cannot be broken on its own.
# The hidden gates of 2.A2 are route waypoints too: without waypoints there is no hidden gate either.
ALSO_UNMET = {
    (CURVE_NAVIGATION_TIME_ESTIMATION, "route_waypoint"): {"curved_leg"},
    (PRECISION_NAVIGATION, "route_waypoints"): {"hidden_gate"},
    # The hidden gate of the minimal known circuit is a route waypoint too.
    (KNOWN_CIRCUIT, "route_waypoint"): {"known_circuit_evidence"},
}


def route_of(geojson: dict) -> EditableRoute:
    return EditableRoute.objects.create(name="Requirements route", route=copy.deepcopy(geojson))


def unmet_keys(route: EditableRoute, task_type: str) -> set[str]:
    return {result.key for result in get_unmet_requirements(route, task_type)}


def compile_verdict(route: EditableRoute, task_type: str) -> list[str]:
    """The validation errors TaskCompiler gives a task of [task_type] built on [route]."""
    task = SimpleNamespace(effective_task_subtype=task_type, editable_route=route)
    return TaskCompiler(task)._validate_primitives(extract_route_primitives(route))


class TestEveryTaskTypeHasCases(TestCase):
    def test_every_task_type_and_every_requirement_is_covered(self):
        self.assertEqual(set(CASES), set(TASK_TYPE_REGISTRY))
        for key, definition in TASK_TYPE_REGISTRY.items():
            requirement_keys = [requirement.key for requirement in definition.route_requirements]
            self.assertEqual(len(requirement_keys), len(set(requirement_keys)), f"{key} repeats a requirement key")
            # An optional requirement is always satisfied, so no route breaks it.
            breakable = [
                requirement.key for requirement in definition.route_requirements if not requirement.is_optional
            ]
            self.assertEqual(set(CASES[key][1]), set(breakable), key)
            for requirement in definition.route_requirements:
                for dependency in requirement.depends_on:
                    self.assertIn(dependency, requirement_keys[: requirement_keys.index(requirement.key)])


class TestMinimalRoutesSatisfyTheirTaskType(TestCase):
    def test_the_minimal_route_meets_every_requirement(self):
        for key, (valid, _violations) in CASES.items():
            with self.subTest(task_type=key):
                route = route_of(valid)
                self.assertEqual(get_unmet_requirements(route, key), [])
                self.assertEqual(get_blocking_reasons(extract_route_primitives(route), key, route), [])
                self.assertIn(key, get_compatible_task_subtypes(route))
                assert_route_compatible_with_task_type(route, TASK_TYPE_REGISTRY[key].coarse_family, key)
                self.assertEqual(compile_verdict(route, key), [])


class TestEachRequirementIsEnforcedOnItsOwn(TestCase):
    def test_a_route_breaking_one_requirement_names_exactly_that_requirement(self):
        for key, (_valid, violations) in CASES.items():
            for requirement_key, routes in violations.items():
                for index, geojson in enumerate(routes):
                    with self.subTest(task_type=key, requirement=requirement_key, variant=index):
                        route = route_of(geojson)
                        self.assertEqual(
                            unmet_keys(route, key), {requirement_key} | ALSO_UNMET.get((key, requirement_key), set())
                        )
                        self.assertNotIn(key, get_compatible_task_subtypes(route))

    def test_unmet_requirement_reports_what_was_found_and_what_is_required(self):
        route = route_of(circle_with_two("circle_entry_marker"))
        (unmet,) = get_unmet_requirements(route, CIRCLE)
        self.assertEqual(
            (unmet.key, unmet.found, unmet.minimum, unmet.maximum, unmet.satisfied),
            ("circle_entry_marker", 2, 1, 1, False),
        )
        self.assertTrue(unmet.label)
        self.assertTrue(unmet.message)


class TestCompatibilityAndCompilerAgree(TestCase):
    def test_every_route_gets_the_same_verdict_from_the_editor_check_creation_and_the_compiler(self):
        for key, (valid, violations) in CASES.items():
            routes = [valid] + [geojson for routes in violations.values() for geojson in routes]
            for index, geojson in enumerate(routes):
                with self.subTest(task_type=key, route=index):
                    route = route_of(geojson)
                    reasons = get_blocking_reasons(extract_route_primitives(route), key, route)
                    self.assertEqual(compile_verdict(route, key), reasons)
                    self.assertEqual(not reasons, key in get_compatible_task_subtypes(route))
                    family = TASK_TYPE_REGISTRY[key].coarse_family
                    if reasons:
                        with self.assertRaises(ValidationError):
                            assert_route_compatible_with_task_type(route, family, key)
                    else:
                        assert_route_compatible_with_task_type(route, family, key)


class TestTheGapsThisSliceCloses(TestCase):
    def test_a_route_without_a_curved_leg_is_not_curve_navigation(self):
        straight = route_of(PRECISION_ROUTE)
        compatible = get_compatible_task_subtypes(straight)
        for key in (LEGACY_PRECISION, ANR_CATALOGUE):
            self.assertIn(key, compatible)
        # A known circuit needs a timed turn point, a hidden gate or a photo: the precision route has timed turn points.
        self.assertIn(KNOWN_CIRCUIT, compatible)
        self.assertNotIn(KNOWN_CIRCUIT, get_compatible_task_subtypes(route_of(BARE_ROUTE)))
        self.assertIn(KNOWN_CIRCUIT, get_compatible_task_subtypes(route_of(HIDDEN_GATE_ROUTE)))
        self.assertNotIn(PRECISION_NAVIGATION, compatible)
        self.assertIn(PRECISION_NAVIGATION, get_compatible_task_subtypes(route_of(HIDDEN_GATE_ROUTE)))
        self.assertNotIn(CURVE_NAVIGATION_TIME_ESTIMATION, compatible)
        self.assertIn(CURVE_NAVIGATION_TIME_ESTIMATION, get_compatible_task_subtypes(route_of(CURVED_ROUTE)))

    def test_a_curve_is_a_curved_leg_with_a_control_point_that_does_not_start_the_route(self):
        route = route_of(CURVED_ROUTE)
        self.assertEqual([item["properties"]["name"] for item in route.get_curved_leg_waypoints()], ["TP1"])
        # The first waypoint ends no leg, so a curve flag on it counts for nothing.
        self.assertEqual(
            route_of(
                with_properties(PRECISION_ROUTE, "SP", segmentType="curved", controlLat=60.0, controlLng=11.0)
            ).get_curved_leg_waypoints(),
            [],
        )

    def test_the_circle_needs_exactly_one_of_each_marker(self):
        self.assertIn(CIRCLE, get_compatible_task_subtypes(route_of(CIRCLE_ROUTE)))
        for feature_type in (
            "circle_start_marker",
            "circle_center_marker",
            "circle_entry_marker",
            "circle_exit_marker",
        ):
            self.assertNotIn(CIRCLE, get_compatible_task_subtypes(route_of(circle_with_two(feature_type))))

    def test_duration_needs_a_landing_area_and_nothing_else(self):
        self.assertNotIn(DURATION, get_compatible_task_subtypes(route_of(PRECISION_ROUTE)))
        self.assertNotIn(DURATION, get_compatible_task_subtypes(route_of(collection([]))))
        self.assertEqual(get_compatible_task_subtypes(route_of(DURATION_ROUTE)), [DURATION])
        with_gates = with_features(
            DURATION_ROUTE, runway_gate_feature("takeoff", START, 0.0), runway_gate_feature("landing", START, 18000.0)
        )
        self.assertIn(DURATION, get_compatible_task_subtypes(route_of(with_gates)))
        self.assertIn(
            DURATION,
            get_compatible_task_subtypes(route_of(with_features(PRECISION_ROUTE, DURATION_ROUTE["features"][0]))),
        )

    def test_the_structure_of_precision_navigation_and_unknown_legs_is_checked_by_the_compatibility_check(self):
        # These two rules used to run only when the task was compiled.
        wrong_end = route_of(with_properties(PRECISION_ROUTE, "FP", pointType="tp"))
        self.assertNotIn(PRECISION_NAVIGATION, get_compatible_task_subtypes(wrong_end))
        self.assertIn(
            "Precision navigation route waypoints must start at SP and finish at FP.",
            get_blocking_reasons(extract_route_primitives(wrong_end), PRECISION_NAVIGATION, wrong_end),
        )
        no_extension = route_of(with_dummy_branch_removed())
        self.assertNotIn(UNKNOWN_LEGS, get_compatible_task_subtypes(no_extension))
        self.assertIn(
            "Unknown legs requires at least one extension waypoint after each unknown-leg point.",
            get_blocking_reasons(extract_route_primitives(no_extension), UNKNOWN_LEGS, no_extension),
        )

    def test_a_count_failure_is_not_reported_a_second_time_as_a_wrong_order(self):
        route = route_of(contract_with_extra_waypoint())
        self.assertEqual(
            get_blocking_reasons(extract_route_primitives(route), CONTRACT_NAVIGATION_TIME_CONTROLS, route),
            ["Contract navigation requires exactly three route waypoints: SP, MP, and FP."],
        )

    def test_other_routes_keep_meeting_the_requirements_of_the_legacy_types(self):
        # Legacy types keep exactly their old rules: a track and a waypoint, nothing about curves or structure.
        route = route_of(with_properties(PRECISION_ROUTE, "FP", pointType="tp"))
        for key in (
            LEGACY_PRECISION,
            LEGACY_ANR_CORRIDOR,
            LEGACY_AIRSPORTS,
            LEGACY_POKER,
            ANR_CATALOGUE,
        ):
            self.assertIn(key, get_compatible_task_subtypes(route))


class TestCompilerValidationMessages(TestCase):
    def test_compiler_reports_the_requirement_messages(self):
        route = route_of(circle_without("circle_center_marker"))
        self.assertEqual(compile_verdict(route, CIRCLE), ["Missing required route feature: circle_center_marker"])


class TestRulesetVersion(TestCase):
    def test_stored_compatibility_is_recomputed_when_it_was_computed_under_an_older_ruleset(self):
        route = route_of(PRECISION_ROUTE)
        self.assertEqual(route.compatibility_ruleset_version, ROUTE_COMPATIBILITY_RULESET_VERSION)
        self.assertNotIn(CURVE_NAVIGATION_TIME_ESTIMATION, route.compatible_task_types)
        # What an older ruleset stored: every precision route was suitable for curve navigation (and duration).
        EditableRoute.objects.filter(pk=route.pk).update(
            compatible_task_types=[CURVE_NAVIGATION_TIME_ESTIMATION, DURATION], compatibility_ruleset_version=2
        )
        route = EditableRoute.objects.get(pk=route.pk)
        updated_at = route.updated_at
        self.assertEqual(route.get_current_compatible_task_types(), get_compatible_task_subtypes(route))
        stored = EditableRoute.objects.get(pk=route.pk)
        self.assertEqual(stored.compatibility_ruleset_version, ROUTE_COMPATIBILITY_RULESET_VERSION)
        self.assertEqual(stored.compatible_task_types, get_compatible_task_subtypes(route))
        self.assertEqual(stored.updated_at, updated_at)

    def test_the_api_serves_the_recomputed_compatibility_of_a_route_saved_under_an_older_ruleset(self):
        user = get_user_model().objects.create(email="route-requirements-stale@example.com")
        route = route_of(PRECISION_ROUTE)
        EditableRoute.objects.filter(pk=route.pk).update(
            compatible_task_types=[DURATION], compatibility_ruleset_version=2
        )
        from guardian.shortcuts import assign_perm

        for permission in ("view_editableroute", "change_editableroute"):
            assign_perm(permission, user, route)
        user.user_permissions.add(Permission.objects.get(codename="add_editableroute"))
        client = APIClient()
        client.force_authenticate(user)
        payload = client.get(f"/api/v1/editableroutes/{route.pk}/").json()
        self.assertEqual(payload["compatible_task_types"], get_compatible_task_subtypes(route))
        self.assertNotIn(DURATION, payload["compatible_task_types"])


class TestTaskCompatibilityApiRequirements(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="route-requirements-api@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="add_editableroute"))
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def post(self, geojson: dict) -> dict:
        response = self.client.post("/api/v1/editableroutes/task_compatibility/", {"route": geojson}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        return {entry["key"]: entry for entry in response.json()["subtypes"]}

    def test_every_task_type_lists_its_requirements_with_what_the_route_has(self):
        subtypes = self.post(CIRCLE_ROUTE)
        self.assertEqual(set(subtypes), set(TASK_TYPE_REGISTRY))
        for key, entry in subtypes.items():
            self.assertEqual(
                [requirement["key"] for requirement in entry["requirements"]],
                [requirement.key for requirement in TASK_TYPE_REGISTRY[key].route_requirements],
            )
            self.assertEqual(
                entry["compatible"], all(requirement["satisfied"] for requirement in entry["requirements"])
            )
            self.assertEqual(entry["compatible"], not entry["missing_reasons"])
        self.assertTrue(subtypes[CIRCLE]["compatible"])
        self.assertEqual(
            subtypes[CIRCLE]["requirements"][0],
            {
                "key": "circle_start_marker",
                "label": "Circle start marker (SP)",
                "minimum": 1,
                "maximum": 1,
                "found": 1,
                "satisfied": True,
                "message": "Missing required route feature: circle_start_marker",
                "required": True,
                "help": TASK_TYPE_REGISTRY[CIRCLE].route_requirements[0].help,
                "tool": "circle_start",
                "other_tools": [],
            },
        )

    def test_an_unmet_requirement_is_flagged_with_the_count_found(self):
        subtypes = self.post(PRECISION_ROUTE)
        by_key = {
            requirement["key"]: requirement
            for requirement in subtypes[CURVE_NAVIGATION_TIME_ESTIMATION]["requirements"]
        }
        self.assertFalse(subtypes[CURVE_NAVIGATION_TIME_ESTIMATION]["compatible"])
        self.assertEqual(
            by_key["curved_leg"],
            {
                "key": "curved_leg",
                "label": "Curved legs",
                "minimum": 1,
                "maximum": None,
                "found": 0,
                "satisfied": False,
                "message": "Curve navigation requires at least one curved leg.",
                "required": True,
                "help": by_key["curved_leg"]["help"],
                "tool": "curved_leg",
                "other_tools": [],
            },
        )
        self.assertTrue(by_key["curved_leg"]["help"])
        self.assertEqual(
            subtypes[CURVE_NAVIGATION_TIME_ESTIMATION]["missing_reasons"],
            ["Curve navigation requires at least one curved leg."],
        )
        self.assertTrue(by_key["route_path"]["satisfied"])

    def test_an_optional_requirement_is_listed_as_not_required_and_is_always_satisfied(self):
        subtypes = self.post(PRECISION_ROUTE)
        by_key = {requirement["key"]: requirement for requirement in subtypes[DURATION]["requirements"]}
        for key in ("takeoff_gate", "landing_gate"):
            entry = by_key[key]
            self.assertEqual((entry["required"], entry["satisfied"], entry["found"]), (False, True, 0))
        self.assertTrue(by_key["duration_landing_area"]["required"])
        self.assertFalse(by_key["duration_landing_area"]["satisfied"])

    def test_the_flags_come_with_each_subtype(self):
        subtypes = self.post(PRECISION_ROUTE)
        for key, entry in subtypes.items():
            self.assertEqual(entry["flags"], TASK_TYPE_REGISTRY[key].route_editor_flags)
        self.assertEqual(
            {key for key, entry in subtypes.items() if entry["flags"]["three_point_backbone"]},
            {CONTRACT_NAVIGATION_TIME_CONTROLS},
        )
        self.assertEqual(
            {key for key, entry in subtypes.items() if entry["flags"]["standalone_timed_turnpoints"]},
            {TURNPOINT_HUNT, LIMITED_FUEL_TURNPOINT_HUNT},
        )
        self.assertEqual({key for key, entry in subtypes.items() if entry["flags"]["circle_markers"]}, {CIRCLE})
        self.assertEqual(
            {key for key, entry in subtypes.items() if entry["flags"]["curve_required"]},
            {CURVE_NAVIGATION_TIME_ESTIMATION},
        )
        self.assertEqual(
            {key for key, entry in subtypes.items() if entry["flags"]["extension_waypoints"]}, {UNKNOWN_LEGS}
        )

    def test_the_known_circuit_lists_the_tools_that_satisfy_its_evidence_requirement(self):
        subtypes = self.post(BARE_ROUTE)
        evidence = {requirement["key"]: requirement for requirement in subtypes[KNOWN_CIRCUIT]["requirements"]}[
            "known_circuit_evidence"
        ]
        self.assertEqual((evidence["required"], evidence["satisfied"], evidence["found"]), (True, False, 0))
        self.assertEqual((evidence["tool"], evidence["other_tools"]), ("hidden_gate", ["route_waypoint", "photo"]))
        self.assertFalse(subtypes[KNOWN_CIRCUIT]["compatible"])
        self.assertTrue(self.post(BARE_HIDDEN_GATE_ROUTE)[KNOWN_CIRCUIT]["compatible"])
        self.assertTrue(self.post(PRECISION_ROUTE)[KNOWN_CIRCUIT]["compatible"])

    def test_unsaved_route_without_features_is_not_compatible_with_duration(self):
        subtypes = self.post({"type": "FeatureCollection", "features": []})
        self.assertFalse(subtypes[DURATION]["compatible"])
        self.assertEqual(subtypes[DURATION]["requirements"][0]["found"], 0)
        self.assertIn(PRECISION, {entry["coarse_family"] for entry in subtypes.values()})
        self.assertIn(ANR_CORRIDOR, {entry["coarse_family"] for entry in subtypes.values()})


class TestRequirementKeysSharedWithTheRouteEditor(TestCase):
    # The route editor wizard maps every requirement key to a step or shows it generically
    # (react_vite/src/features/route-editor/taskRequirements.ts). The keys are listed in
    # react_vite/src/features/route-editor/routeRequirementKeys.json, which the vitest taskRequirements.test.ts checks
    # the mapping against; this list must match that file. The test container may not mount react_vite/, so the
    # registry is always checked against this constant and the file only when it can be read.
    WIZARD_REQUIREMENT_KEYS = {
        "catalogue_turnpoint",
        "circle_center_marker",
        "circle_entry_marker",
        "circle_exit_marker",
        "circle_start_marker",
        "curved_leg",
        "dummy_waypoint",
        "duration_landing_area",
        "hidden_gate",
        "known_circuit_evidence",
        "known_time_gate",
        "landing_gate",
        "observation_photo",
        "route_path",
        "route_waypoint",
        "route_waypoint_order",
        "route_waypoints",
        "takeoff_gate",
        "unknown_leg",
        "unknown_leg_extension",
    }
    FIXTURE_LOCATIONS = (
        Path(__file__).resolve().parents[3] / "react_vite/src/features/route-editor/routeRequirementKeys.json",
        Path("/workspace/react_vite/src/features/route-editor/routeRequirementKeys.json"),
    )

    def test_every_requirement_key_of_the_registry_is_known_to_the_wizard(self):
        produced = {
            requirement.key
            for definition in TASK_TYPE_REGISTRY.values()
            for requirement in definition.route_requirements
        }
        self.assertEqual(
            produced,
            self.WIZARD_REQUIREMENT_KEYS,
            "Add the key to WIZARD_REQUIREMENT_KEYS here, to routeRequirementKeys.json and map it in "
            "taskRequirements.ts (or let the wizard show it as a generic row).",
        )

    def test_the_list_matches_the_json_file_shared_with_the_route_editor(self):
        fixture = next((path for path in self.FIXTURE_LOCATIONS if path.exists()), None)
        if fixture is None:
            self.skipTest("react_vite/ is not visible from this environment")
        self.assertEqual(set(json.loads(fixture.read_text())["requirementKeys"]), self.WIZARD_REQUIREMENT_KEYS)


class TestGuideFieldsOfTheRegistry(TestCase):
    """What the route editor's guide reads from each requirement: a help text and the tool that satisfies it."""

    def requirements(self):
        return [
            (key, requirement)
            for key, definition in TASK_TYPE_REGISTRY.items()
            for requirement in definition.route_requirements
        ]

    def test_every_required_or_optional_requirement_has_a_help_text(self):
        for key, requirement in self.requirements():
            if requirement.is_required or requirement.is_optional:
                with self.subTest(task_type=key, requirement=requirement.key):
                    self.assertTrue(requirement.help.strip())
                    self.assertTrue(requirement.help.endswith("."))

    def test_tools_are_from_the_enumeration(self):
        for key, requirement in self.requirements():
            with self.subTest(task_type=key, requirement=requirement.key):
                for tool in (requirement.tool, *requirement.other_tools):
                    self.assertTrue(tool is None or tool in rr.TOOLS)
                if requirement.other_tools:
                    self.assertIsNotNone(requirement.tool)
                # A requirement that no tool satisfies is not something the guide can start a tool for.
                if requirement.is_required and requirement.ordering is None:
                    self.assertIsNotNone(requirement.tool)
        self.assertEqual(len(rr.TOOLS), len(set(rr.TOOLS)))

    def test_a_requirement_without_a_tool_is_an_ordering_or_a_forbidden_feature(self):
        for key, requirement in self.requirements():
            if requirement.tool is None:
                with self.subTest(task_type=key, requirement=requirement.key):
                    self.assertTrue(requirement.ordering is not None or requirement.maximum == 0)

    def test_hidden_gate_texts_do_not_send_the_user_to_view_mode(self):
        for key, requirement in self.requirements():
            self.assertNotIn("View mode", requirement.help, f"{key} {requirement.key}")
            if requirement.tool == rr.TOOL_HIDDEN_GATE:
                self.assertIn(
                    "Hidden gate tool and click a leg of the route where the gate should be.", requirement.help
                )

    def test_the_optional_steps_of_the_guide_are_optional_requirements(self):
        optional = {
            key: {requirement.key for requirement in definition.route_requirements if requirement.is_optional}
            for key, definition in TASK_TYPE_REGISTRY.items()
        }
        self.assertEqual(optional[CURVE_NAVIGATION_TIME_ESTIMATION], {"hidden_gate"})
        self.assertEqual(optional[CONTRACT_NAVIGATION_TIME_CONTROLS], {"observation_photo"})
        self.assertEqual(optional[UNKNOWN_LEGS], {"hidden_gate", "observation_photo"})
        self.assertEqual(optional[TURNPOINT_HUNT], {"observation_photo"})
        self.assertEqual(optional[LIMITED_FUEL_TURNPOINT_HUNT], {"observation_photo"})
        self.assertEqual(optional[DURATION], {"takeoff_gate", "landing_gate"})
        self.assertEqual({key for key, found in optional.items() if found}, set(optional) - {
            LEGACY_PRECISION, LEGACY_ANR_CORRIDOR, LEGACY_AIRSPORTS, LEGACY_AIRSPORT_CHALLENGE, LEGACY_POKER,
            LEGACY_LANDING, PRECISION_NAVIGATION, KNOWN_CIRCUIT, CIRCLE, ANR_CATALOGUE,
        })

    def test_an_optional_requirement_never_changes_the_outcome(self):
        # Every route that is compatible with a task type stays so with the optional requirements removed, and the other
        # way round: they are always satisfied.
        for key, (valid, violations) in CASES.items():
            definition = TASK_TYPE_REGISTRY[key]
            for geojson in [valid] + [route for routes in violations.values() for route in routes]:
                route = route_of(geojson)
                primitives = extract_route_primitives(route)
                results = evaluate_route_requirements(primitives, definition, route)
                for requirement, result in zip(definition.route_requirements, results):
                    if requirement.is_optional:
                        self.assertTrue(result.satisfied)
                self.assertEqual(
                    [result.message for result in results if not result.satisfied],
                    get_blocking_reasons(primitives, key, route),
                )

    def test_any_of_counts_the_sum_of_its_facts(self):
        requirement = TASK_TYPE_REGISTRY[KNOWN_CIRCUIT].route_requirements[-1]
        self.assertEqual(requirement.fact, (rr.TIMED_TURN_POINT, rr.HIDDEN_GATE, rr.OBSERVATION_PHOTO))
        photo = {
            "type": "Feature",
            "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"},
            "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
        }
        time_gate = hunt_route_geojson(compulsory={"CP1": (2000.0, 0.0)})["features"][0]
        for geojson, expected in (
            (BARE_ROUTE, False),
            # A standalone known time gate is not part of the scored route.
            (with_features(BARE_ROUTE, time_gate), False),
            # A turn point that is not a time gate does not count.
            (UNTIMED_TURN_POINTS_ROUTE, False),
            (PRECISION_ROUTE, True),
            (BARE_ROUTE_WITH_TP, False),
            (with_properties(BARE_ROUTE_WITH_TP, "TP1", isTiming=True), True),
            (BARE_HIDDEN_GATE_ROUTE, True),
            (with_features(BARE_ROUTE, photo), True),
        ):
            route = route_of(geojson)
            self.assertEqual(KNOWN_CIRCUIT in get_compatible_task_subtypes(route), expected)
        reasons = get_blocking_reasons(extract_route_primitives(route_of(BARE_ROUTE)), KNOWN_CIRCUIT)
        self.assertEqual(
            reasons,
            [
                "A known circuit needs at least one timed turn point, hidden gate or photo: without one there is "
                "nothing to score besides the start and finish."
            ],
        )

    def test_the_task_creation_check_gives_the_same_message(self):
        route = route_of(BARE_ROUTE)
        with self.assertRaisesMessage(ValidationError, "A known circuit needs at least one timed turn point"):
            assert_route_compatible_with_task_type(route, PRECISION, KNOWN_CIRCUIT)

    def test_the_no_route_message_still_reads_right_with_optional_requirements(self):
        message = no_compatible_routes_message(DURATION)
        self.assertIn("requires: duration_landing_area", message)
        self.assertNotIn("takeoff_gate", message)
        self.assertIn("known_circuit_evidence", no_compatible_routes_message(KNOWN_CIRCUIT))


class TestRouteEditorFlags(TestCase):
    def flagged(self, flag: str) -> set[str]:
        return {key for key, definition in TASK_TYPE_REGISTRY.items() if getattr(definition, flag)}

    def test_each_flag_is_set_for_the_task_types_the_route_editor_used_to_name_by_id(self):
        self.assertEqual(self.flagged("three_point_backbone"), {CONTRACT_NAVIGATION_TIME_CONTROLS})
        self.assertEqual(self.flagged("standalone_timed_turnpoints"), {TURNPOINT_HUNT, LIMITED_FUEL_TURNPOINT_HUNT})
        self.assertEqual(self.flagged("circle_markers"), {CIRCLE})
        self.assertEqual(self.flagged("curve_required"), {CURVE_NAVIGATION_TIME_ESTIMATION})
        self.assertEqual(self.flagged("extension_waypoints"), {UNKNOWN_LEGS})

    def test_the_flags_agree_with_the_facts_they_are_derived_from(self):
        for key, definition in TASK_TYPE_REGISTRY.items():
            self.assertEqual(definition.circle_markers, definition.scores_circle, key)
            self.assertEqual(definition.extension_waypoints, definition.has_unknown_legs, key)
            if definition.standalone_timed_turnpoints:
                self.assertFalse(definition.has_backbone, key)
        self.assertEqual(
            set(TASK_TYPE_REGISTRY[CIRCLE].route_editor_flags),
            {
                "three_point_backbone",
                "standalone_timed_turnpoints",
                "circle_markers",
                "curve_required",
                "extension_waypoints",
            },
        )
