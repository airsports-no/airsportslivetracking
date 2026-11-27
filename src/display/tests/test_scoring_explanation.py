"""
The plain-language explanation of how a task is scored (display.services.scoring_explanation, slice S20b) and the API
that serves it. The text is generated from the task type registry and the scorecard, so these tests change the scorecard
and check that the text follows.
"""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from display.calculators.tests.test_score_message_kinds import MessageTestCase
from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Scorecard
from display.tests.test_task_scoring import TaskScoringTestCase
from display.services.scoring_explanation import (
    explain_scoring,
    explain_task_type,
    offered_qmax_policies,
    parse_preview_overrides,
)
from display.utilities.task_types import (
    ANR_CATALOGUE,
    CIRCLE,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    DURATION,
    KNOWN_CIRCUIT,
    LEGACY_ANR_CORRIDOR,
    LEGACY_POKER,
    LEGACY_PRECISION,
    LIMITED_FUEL_TURNPOINT_HUNT,
    PRECISION_NAVIGATION,
    QMAX_ABSOLUTE,
    QMAX_BEST_IN_TASK,
    QMAX_THEORETICAL,
    TASK_TYPE_REGISTRY,
    TURNPOINT_HUNT,
    UNKNOWN_LEGS,
    get_task_type,
)

CIMA_TYPES = [definition.key for definition in TASK_TYPE_REGISTRY.values() if definition.catalogue_code]
# Words of the engine that an organiser must never meet in the text
INTERNAL_NAMES = (
    "qmax_policy",
    "best_in_task",
    "scoring_model",
    "score_type",
    "task_value",
    "gate_deficit",
    "theoretical",
)


def whole_text(explanation: dict) -> str:
    """Every sentence of an explanation in one string."""
    parts = [explanation["headline"], explanation["task_score"], explanation["provisional"]["text"]]
    parts += explanation["raw_points"] + explanation["relative_terms"] + explanation["percentage_penalties"]
    parts += [option["description"] for option in explanation["qmax"]["options"]]
    return "\n".join(parts)


class ExplanationTestCase(TestCase):
    def setUp(self):
        create_scorecards()

    def original(self, shortcut_name: str) -> Scorecard:
        return Scorecard.get_originals().get(shortcut_name=shortcut_name)

    def explain(self, key: str, **config) -> dict:
        definition = get_task_type(key)
        scorecard = self.original(definition.scorecard_shortcut_name or "FAI Precision")
        scorecard.config.update(config)
        return explain_scoring(definition, scorecard)


class TestEveryCimaTaskType(ExplanationTestCase):
    def test_every_cima_task_type_explains_itself_on_its_default_scorecard(self):
        for key in CIMA_TYPES:
            with self.subTest(task_type=key):
                explanation = self.explain(key)
                self.assertEqual("quality", explanation["scoring_model"])
                self.assertEqual(1000, explanation["task_value"])
                self.assertIn(get_task_type(key).catalogue_code, explanation["headline"])
                self.assertTrue(explanation["raw_points"], "says what the raw result is made of")
                if key != CIRCLE:  # the circle's raw points are the task score
                    self.assertIn("1000", explanation["task_score"])
                self.assertTrue(explanation["percentage_penalties"])
                self.assertTrue(explanation["provisional"]["short"])
                self.assertTrue(explanation["creation_note"])
                json.dumps(explanation)
                text = whole_text(explanation)
                for name in INTERNAL_NAMES:
                    self.assertNotIn(name, text.replace("theoretical maximum", ""), f"'{name}' is an internal name")

    def test_the_default_policy_of_the_task_type_is_preselected(self):
        for key in CIMA_TYPES:
            with self.subTest(task_type=key):
                definition = get_task_type(key)
                qmax = self.explain(key)["qmax"]
                self.assertEqual(definition.qmax_policy, qmax["selected"])
                self.assertEqual(definition.qmax_policy, qmax["default"])
                selected = [option for option in qmax["options"] if option["is_selected"]]
                self.assertEqual([definition.qmax_policy], [option["value"] for option in selected])
                self.assertTrue(selected[0]["is_default"])

    def test_the_default_cima_task_depends_on_the_best_pilot_and_says_scores_can_fall_after_landing(self):
        for key in (CURVE_NAVIGATION_TIME_ESTIMATION, PRECISION_NAVIGATION, KNOWN_CIRCUIT, TURNPOINT_HUNT, DURATION):
            with self.subTest(task_type=key):
                explanation = self.explain(key)
                self.assertTrue(explanation["depends_on_other_pilots"])
                self.assertIn("best pilot in the task", explanation["headline"])
                self.assertIn("fall after landing", explanation["provisional"]["text"])
                self.assertIn("can change until everyone has flown", explanation["creation_note"])
                self.assertIn("final when all flights are finished", explanation["provisional"]["short"])

    def test_the_fixed_scale_tasks_do_not_depend_on_the_other_pilots(self):
        for key in (CIRCLE, ANR_CATALOGUE):
            with self.subTest(task_type=key):
                explanation = self.explain(key)
                self.assertFalse(explanation["depends_on_other_pilots"])
                self.assertEqual(QMAX_ABSOLUTE, explanation["qmax_policy"])
                self.assertIn("does not depend on the other pilots", explanation["task_score"])

    def test_2a1_says_how_its_hidden_gates_and_time_gates_score(self):
        text = "\n".join(self.explain(CURVE_NAVIGATION_TIME_ESTIMATION)["raw_points"])
        self.assertIn("The hidden gates share 1000 points equally", text)
        self.assertIn("Each timed turn point is worth 180 points, less 1 point for every second", text)
        self.assertIn("at most 180 points can be lost", text)
        self.assertIn("counts as not crossed", text)

    def test_2a3_says_what_the_declared_points_are_and_that_they_follow_the_best_pilot(self):
        explanation = self.explain(CONTRACT_NAVIGATION_TIME_CONTROLS)
        terms = "\n".join(explanation["relative_terms"])
        self.assertIn("called V", terms)
        self.assertIn("1000 times their V divided by the best V in the task", terms)
        self.assertIn("starting point, middle point and finish point", "\n".join(explanation["raw_points"]))

    def test_2a4_names_the_speed_term_only_when_the_scorecard_gives_it_a_value(self):
        without = self.explain(KNOWN_CIRCUIT)
        self.assertIn("not used in this task", "\n".join(without["relative_terms"]))
        with_term = self.explain(KNOWN_CIRCUIT, speed_term_value=150)
        terms = "\n".join(with_term["relative_terms"])
        self.assertIn("fastest pilot in the task gets 150 points", terms)
        self.assertIn("150 times their S divided by the best S", terms)

    def test_2a2_2a5_2b2_have_no_term_that_follows_the_best_pilot_apart_from_the_scaling(self):
        for key in (PRECISION_NAVIGATION, UNKNOWN_LEGS, LIMITED_FUEL_TURNPOINT_HUNT):
            with self.subTest(task_type=key):
                self.assertEqual([], self.explain(key)["relative_terms"])

    def test_the_duration_task_has_no_perfect_flight_to_compare_with(self):
        qmax = self.explain(DURATION)["qmax"]
        self.assertEqual([QMAX_BEST_IN_TASK], [option["value"] for option in qmax["options"]])
        self.assertFalse(qmax["offered"])

    def test_the_circle_and_the_anr_task_use_numbers_of_the_scorecard(self):
        circle = "\n".join(self.explain(CIRCLE)["raw_points"])
        self.assertIn("A perfect circle scores 250 points", circle)
        self.assertIn("between 200 and 750 metres", circle)
        anr = "\n".join(self.explain(ANR_CATALOGUE)["raw_points"])
        self.assertIn("starts with 2000 points", anr)
        self.assertIn("fixed scale", self.explain(ANR_CATALOGUE)["task_score"])
        self.assertIn("1000 times the pilot's raw points divided by 2000", self.explain(ANR_CATALOGUE)["task_score"])

    def test_the_task_score_of_the_circle_says_the_task_value_is_not_used(self):
        self.assertIn("task value is not used", self.explain(CIRCLE)["task_score"])


class TestTheTextFollowsTheScorecard(ExplanationTestCase):
    def test_the_task_value(self):
        explanation = self.explain(PRECISION_NAVIGATION, task_value=1250)
        self.assertEqual(1250, explanation["task_value"])
        self.assertIn("1250 times", explanation["task_score"])
        self.assertIn("full 1250 points", explanation["task_score"])
        self.assertNotIn("1000", explanation["task_score"])

    def test_the_qmax_policy_changes_the_text(self):
        best = self.explain(PRECISION_NAVIGATION)
        theoretical = self.explain(PRECISION_NAVIGATION, qmax_policy=QMAX_THEORETICAL)
        self.assertEqual(QMAX_THEORETICAL, theoretical["qmax_policy"])
        self.assertIn("divided by the raw points of the best pilot in the task", best["task_score"])
        self.assertIn("perfect flight", theoretical["task_score"])
        self.assertNotIn("best pilot in the task", theoretical["task_score"])
        self.assertTrue(best["depends_on_other_pilots"])
        self.assertFalse(theoretical["depends_on_other_pilots"])
        self.assertIn("fixed when they land", theoretical["provisional"]["text"])
        self.assertNotEqual(best["headline"], theoretical["headline"])

    def test_the_three_policies_read_differently_and_each_is_described_for_the_choice(self):
        best = self.explain(PRECISION_NAVIGATION)["qmax"]["options"]
        self.assertEqual([QMAX_BEST_IN_TASK, QMAX_THEORETICAL], [option["value"] for option in best])
        absolute = self.explain(ANR_CATALOGUE)["qmax"]["options"]
        self.assertEqual([QMAX_ABSOLUTE], [option["value"] for option in absolute])
        descriptions = {option["value"]: option["description"] for option in best + absolute}
        self.assertEqual(3, len(set(descriptions.values())))
        self.assertIn("go down after landing", descriptions[QMAX_BEST_IN_TASK])
        self.assertIn("fixed when they land", descriptions[QMAX_THEORETICAL])
        self.assertIn("never depends on the other pilots", descriptions[QMAX_ABSOLUTE])
        self.assertTrue(self.explain(PRECISION_NAVIGATION)["qmax"]["offered"])

    def test_the_backtracking_percentage(self):
        default = self.explain(PRECISION_NAVIGATION)["percentage_penalties"]
        self.assertIn("each backtrack costs 50% of the task score", default[0])
        changed = self.explain(PRECISION_NAVIGATION, backtracking_penalty_percentage=25)["percentage_penalties"]
        self.assertIn("each backtrack costs 25% of the task score", changed[0])
        flat = self.explain(PRECISION_NAVIGATION, backtracking_penalty_percentage=0)
        self.assertNotIn("each backtrack costs", "\n".join(flat["percentage_penalties"]))
        self.assertIn("Backtracking costs 200 points each time", "\n".join(flat["raw_points"]))

    def test_emax_and_the_time_cost(self):
        scorecard = self.original("CIMA Precision")
        for gate_type in ("tp", "secret", "sp", "fp"):
            scorecard.config["gates"][gate_type]["maximum_penalty"] = 120
            scorecard.config["gates"][gate_type]["penalty_per_second"] = 2
            scorecard.config["gates"][gate_type]["graceperiod_after"] = 3
        text = "\n".join(explain_scoring(get_task_type(CURVE_NAVIGATION_TIME_ESTIMATION), scorecard)["raw_points"])
        self.assertIn("Each timed turn point is worth 120 points, less 2 points for every second", text)
        self.assertIn("at most 120 points can be lost", text)
        self.assertIn("up to 3 seconds cost nothing", text)

    def test_the_hunt_numbers(self):
        text = "\n".join(
            self.explain(TURNPOINT_HUNT, turnpoint_hunt_sequence_bonus=300, maximum_task_duration_minutes=90)[
                "raw_points"
            ]
        )
        self.assertIn("A bonus of 300 points", text)
        self.assertIn("maximum task duration of 90 minutes", text)
        self.assertIn("worth 200 points", text)
        free_order = "\n".join(self.explain(LIMITED_FUEL_TURNPOINT_HUNT)["raw_points"])
        self.assertNotIn("bonus", free_order)
        self.assertIn("fuel endurance costs 100 points", free_order)

    def test_the_circle_penalty_and_the_landing_penalty_are_the_scorecards(self):
        circle = self.explain(CIRCLE, circle_altitude_penalty_percent=30, circle_altitude_band_ft=150)
        self.assertIn("30% of the task score is lost", "\n".join(circle["percentage_penalties"]))
        self.assertIn("150 feet", "\n".join(circle["percentage_penalties"]))
        duration = self.explain(DURATION, duration_landing_area_penalty_percent=40)
        self.assertIn("costs 40% of the task score", "\n".join(duration["percentage_penalties"]))

    def test_the_organisers_own_penalties_and_the_summing_rule_are_always_mentioned(self):
        text = "\n".join(self.explain(PRECISION_NAVIGATION)["percentage_penalties"])
        self.assertIn("100% for a breach of quarantine", text)
        self.assertIn("add up (at most 100%)", text)

    def test_a_task_with_a_stored_penalty_model_is_explained_as_penalties(self):
        explanation = self.explain(PRECISION_NAVIGATION, scoring_model="penalties")
        self.assertEqual("penalties", explanation["scoring_model"])
        self.assertFalse(explanation["depends_on_other_pilots"])

    def test_the_preview_overrides_do_not_change_the_stored_scorecard(self):
        scorecard = self.original("CIMA Precision")
        preview = explain_task_type(
            PRECISION_NAVIGATION, scorecard, {"qmax_policy": QMAX_THEORETICAL, "task_value": 700}
        )
        self.assertEqual(QMAX_THEORETICAL, preview["qmax_policy"])
        self.assertEqual(700, preview["task_value"])
        self.assertIsNone(self.original("CIMA Precision").qmax_policy)
        self.assertIsNone(explain_task_type("no_such_type", scorecard))

    def test_overrides_are_parsed_and_checked(self):
        self.assertEqual(
            {"qmax_policy": "theoretical", "task_value": 900.0, "speed_term_value": None},
            parse_preview_overrides({"qmax_policy": "theoretical", "task_value": "900", "speed_term_value": ""}),
        )
        self.assertEqual({}, parse_preview_overrides({"unrelated": "x"}))
        for params in ({"qmax_policy": "nonsense"}, {"scoring_model": "x"}, {"task_value": "many"}):
            with self.assertRaises(ValueError):
                parse_preview_overrides(params)


class TestThePolicyChoice(ExplanationTestCase):
    def test_what_is_offered_follows_the_task_type(self):
        self.assertEqual(
            [QMAX_BEST_IN_TASK, QMAX_THEORETICAL], offered_qmax_policies(get_task_type(PRECISION_NAVIGATION))
        )
        self.assertEqual([QMAX_BEST_IN_TASK, QMAX_THEORETICAL], offered_qmax_policies(get_task_type(TURNPOINT_HUNT)))
        self.assertEqual([QMAX_BEST_IN_TASK], offered_qmax_policies(get_task_type(DURATION)))
        self.assertEqual([QMAX_ABSOLUTE], offered_qmax_policies(get_task_type(CIRCLE)))
        self.assertEqual([QMAX_ABSOLUTE], offered_qmax_policies(get_task_type(ANR_CATALOGUE)))
        self.assertEqual([], offered_qmax_policies(get_task_type(LEGACY_PRECISION)))

    def test_theoretical_keeps_the_relative_terms_relative(self):
        for key, config in ((CONTRACT_NAVIGATION_TIME_CONTROLS, {}), (KNOWN_CIRCUIT, {"speed_term_value": 100})):
            with self.subTest(task_type=key):
                explanation = self.explain(key, qmax_policy=QMAX_THEORETICAL, **config)
                self.assertTrue(explanation["depends_on_other_pilots"])
                self.assertIn("shared against the best pilot", explanation["provisional"]["text"])
                self.assertIn(
                    "are still shared against the best pilot", explanation["qmax"]["options"][1]["description"]
                )
                self.assertIn("Only the shared terms below follow the best pilot", explanation["headline"])

    def test_theoretical_without_a_relative_term_is_fixed_at_landing(self):
        explanation = self.explain(PRECISION_NAVIGATION, qmax_policy=QMAX_THEORETICAL)
        self.assertFalse(explanation["depends_on_other_pilots"])
        self.assertNotIn("shared against", explanation["qmax"]["options"][1]["description"])


class TestLegacyTasks(ExplanationTestCase):
    def test_a_legacy_precision_task_is_penalty_points_where_the_lowest_total_wins(self):
        explanation = explain_scoring(get_task_type(LEGACY_PRECISION), self.original("FAI Precision"))
        self.assertEqual("penalties", explanation["scoring_model"])
        self.assertEqual(
            "Penalty points are added up; the lowest total wins. Scores do not depend on the other pilots.",
            explanation["headline"],
        )
        self.assertFalse(explanation["depends_on_other_pilots"])
        self.assertIsNone(explanation["task_value"])
        self.assertFalse(explanation["qmax"]["offered"])
        self.assertEqual([], explanation["relative_terms"])
        self.assertIsNone(explanation["creation_note"])
        for name in INTERNAL_NAMES:
            self.assertNotIn(name, whole_text(explanation))

    def test_a_legacy_task_with_a_descending_scorecard_says_points_are_taken_off(self):
        scorecard = self.original("FAI Precision")
        scorecard.score_sorting_direction = "desc"
        scorecard.initial_score = 1000
        explanation = explain_scoring(get_task_type(LEGACY_ANR_CORRIDOR), scorecard)
        self.assertIn("highest score wins", explanation["headline"])
        self.assertIn("starts with 1000 points", explanation["raw_points"][0])

    def test_a_poker_run_is_not_called_penalty_points(self):
        explanation = explain_scoring(get_task_type(LEGACY_POKER), self.original("FAI Precision"))
        self.assertNotIn("Penalty points", explanation["headline"])
        self.assertIn("playing cards", explanation["raw_points"][0])


class TestRouteNumbers(MessageTestCase):
    """With a task the number of hidden gates is counted from its route."""

    def test_the_hidden_gates_of_the_route_are_counted(self):
        from types import SimpleNamespace

        from display.services.scoring_explanation import explain_navigation_task
        from display.utilities.gate_definitions import FINISHPOINT, SECRETPOINT, STARTINGPOINT, TURNPOINT

        cima = Scorecard.get_originals().get(shortcut_name="CIMA Precision")
        task = self.make_task(CURVE_NAVIGATION_TIME_ESTIMATION, original_scorecard=cima)

        def gate(name, gate_type, time_check=True, gate_check=True):
            return SimpleNamespace(name=name, type=gate_type, time_check=time_check, gate_check=gate_check)

        task.route.waypoints = [
            gate("SP", STARTINGPOINT),
            gate("TP1", TURNPOINT),
            *[gate(f"HG{n}", SECRETPOINT, time_check=False) for n in range(1, 8)],
            gate("FP", FINISHPOINT),
        ]
        explanation = explain_navigation_task(task)
        self.assertTrue(explanation["route_used"])
        self.assertIn("The route's 7 hidden gates share 1000 points: 142.9 points", explanation["raw_points"][0])
        task.scorecard.config["task_value"] = 800
        self.assertEqual(800, explain_navigation_task(task)["task_value"])
        # Without hidden gates in the route the text stays general
        task.route.waypoints = [gate("SP", STARTINGPOINT), gate("FP", FINISHPOINT)]
        general = explain_navigation_task(task)
        self.assertIn("The hidden gates share 1000 points equally", general["raw_points"][0])

    def test_a_legacy_task_is_named_by_its_family_default(self):
        from display.services.scoring_explanation import explain_navigation_task

        task = self.make_task(None)
        explanation = explain_navigation_task(task)
        self.assertEqual("penalties", explanation["scoring_model"])
        self.assertEqual(LEGACY_PRECISION, explanation["task_type"])


class TestScoringExplanationApi(MessageTestCase):
    def setUp(self):
        super().setUp()
        self.cima = Scorecard.get_originals().get(shortcut_name="CIMA Precision")
        self.task = self.make_task(PRECISION_NAVIGATION, original_scorecard=self.cima)
        self.superuser = get_user_model().objects.create_superuser("s20b-admin@example.com", "pw")
        self.stranger = get_user_model().objects.create(email="s20b-stranger@example.com")

    def client_for(self, user=None) -> APIClient:
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    def task_kwargs(self):
        return {"contest_pk": self.contest.pk, "pk": self.task.pk}

    def test_the_navigation_task_payload_carries_the_explanation(self):
        response = self.client_for(self.superuser).get(reverse("navigationtasks-detail", kwargs=self.task_kwargs()))
        self.assertEqual(200, response.status_code, response.content)
        explanation = response.json()["scoring_explanation"]
        self.assertEqual("quality", explanation["scoring_model"])
        self.assertIn("2.A2", explanation["headline"])
        self.assertTrue(explanation["provisional"]["short"])

    def test_the_task_endpoint_explains_the_task_and_previews_unsaved_values(self):
        url = reverse("navigationtasks-scoring-explanation", kwargs=self.task_kwargs())
        client = self.client_for(self.superuser)
        stored = client.get(url)
        self.assertEqual(200, stored.status_code, stored.content)
        self.assertEqual(QMAX_BEST_IN_TASK, stored.json()["qmax_policy"])
        preview = client.get(url, {"qmax_policy": "theoretical", "task_value": "800"}).json()
        self.assertEqual(QMAX_THEORETICAL, preview["qmax_policy"])
        self.assertEqual(800, preview["task_value"])
        self.task.scorecard.refresh_from_db()
        self.assertEqual(QMAX_BEST_IN_TASK, client.get(url).json()["qmax_policy"])
        self.assertEqual(400, client.get(url, {"qmax_policy": "nonsense"}).status_code)

    def test_a_private_task_is_not_explained_to_a_stranger_or_an_anonymous_visitor(self):
        url = reverse("navigationtasks-scoring-explanation", kwargs=self.task_kwargs())
        self.assertIn(self.client_for(None).get(url).status_code, (401, 403, 404))
        self.assertIn(self.client_for(self.stranger).get(url).status_code, (403, 404))

    def test_a_legacy_task_is_explained_too(self):
        legacy = self.make_task(None)
        response = self.client_for(self.superuser).get(
            reverse("navigationtasks-scoring-explanation", kwargs={"contest_pk": self.contest.pk, "pk": legacy.pk})
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("penalties", response.json()["scoring_model"])

    def test_the_pair_endpoint_explains_a_task_type_before_a_task_exists(self):
        url = reverse("scorecards-explanation")
        client = self.client_for(self.superuser)
        response = client.get(url, {"task_subtype": CURVE_NAVIGATION_TIME_ESTIMATION})
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertIn("2.A1", body["headline"])
        self.assertFalse(body["route_used"])
        self.assertEqual([QMAX_BEST_IN_TASK, QMAX_THEORETICAL], [option["value"] for option in body["qmax"]["options"]])
        previewed = client.get(url, {"task_subtype": PRECISION_NAVIGATION, "qmax_policy": "theoretical"}).json()
        self.assertEqual(QMAX_THEORETICAL, previewed["qmax_policy"])
        legacy = client.get(url, {"task_subtype": LEGACY_PRECISION, "scorecard": "FAI Precision"}).json()
        self.assertEqual("penalties", legacy["scoring_model"])

    def test_the_pair_endpoint_checks_its_input_and_the_user(self):
        url = reverse("scorecards-explanation")
        self.assertIn(self.client_for(None).get(url, {"task_subtype": DURATION}).status_code, (401, 403))
        client = self.client_for(self.superuser)
        self.assertEqual(400, client.get(url).status_code)
        self.assertEqual(400, client.get(url, {"task_subtype": "nonsense"}).status_code)
        self.assertEqual(404, client.get(url, {"task_subtype": DURATION, "scorecard": "No such card"}).status_code)
        self.assertEqual(400, client.get(url, {"task_subtype": DURATION, "task_value": "x"}).status_code)


class TestChoosingTheQmaxPolicyAtCreation(MessageTestCase):
    """The creation flow stores the organiser's choice in the task's own copy of the scorecard."""

    def validate(self, subtype, policy):
        from display.serialisers import NavigationTaskEditableRoutReferenceSerialiser

        return NavigationTaskEditableRoutReferenceSerialiser().validate(
            {"task_subtype": subtype, "qmax_policy": policy}
        )

    def test_the_serialiser_accepts_only_what_the_task_type_offers(self):
        from rest_framework.exceptions import ValidationError

        self.assertEqual(QMAX_THEORETICAL, self.validate(PRECISION_NAVIGATION, QMAX_THEORETICAL)["qmax_policy"])
        self.assertEqual(QMAX_BEST_IN_TASK, self.validate(TURNPOINT_HUNT, QMAX_BEST_IN_TASK)["qmax_policy"])
        self.assertEqual(QMAX_ABSOLUTE, self.validate(ANR_CATALOGUE, QMAX_ABSOLUTE)["qmax_policy"])
        for subtype, policy in (
            (PRECISION_NAVIGATION, QMAX_ABSOLUTE),
            (DURATION, QMAX_THEORETICAL),
            (CIRCLE, QMAX_BEST_IN_TASK),
            (LEGACY_PRECISION, QMAX_THEORETICAL),
            (None, QMAX_THEORETICAL),
        ):
            with self.subTest(subtype=subtype, policy=policy), self.assertRaises(ValidationError):
                self.validate(subtype, policy)

    def create(self, policy):
        from unittest.mock import MagicMock, patch

        from display.models import Route
        from display.serialisers import NavigationTaskEditableRoutReferenceSerialiser

        from display.models import EditableRoute

        editable_route = EditableRoute.objects.create(name="created", route={"features": []})
        created_route = Route.objects.create(name="route-created")
        user = get_user_model().objects.create_superuser("s20b-creator@example.com", "pw")
        request = MagicMock()
        request.user = user
        data = {
            "name": "created",
            "original_scorecard": Scorecard.get_originals().get(shortcut_name="CIMA Precision"),
            "editable_route": editable_route,
            "task_subtype": PRECISION_NAVIGATION,
            "start_time": self.contest.start_time,
            "finish_time": self.contest.finish_time,
        }
        if policy:
            data["qmax_policy"] = policy
        serialiser = NavigationTaskEditableRoutReferenceSerialiser(
            context={"request": request, "contest": self.contest}
        )
        with (
            patch("display.serialisers.assert_can_add_navigation_task"),
            patch("display.serialisers.assign_perm"),
            patch.object(EditableRoute, "create_route", return_value=created_route),
            patch.object(EditableRoute, "get_validation_errors", return_value=[]),
        ):
            return serialiser.create(data)

    def test_the_choice_is_written_to_the_scorecard_copy_and_not_to_the_original(self):
        task = self.create(QMAX_THEORETICAL)
        task.scorecard.refresh_from_db()
        self.assertEqual(QMAX_THEORETICAL, task.scorecard.config["qmax_policy"])
        self.assertEqual(QMAX_THEORETICAL, explain_navigation_task_policy(task))
        self.assertIsNone(Scorecard.get_originals().get(shortcut_name="CIMA Precision").qmax_policy)

    def test_without_a_choice_the_default_of_the_rules_is_stored(self):
        task = self.create(None)
        task.scorecard.refresh_from_db()
        self.assertEqual(QMAX_BEST_IN_TASK, task.scorecard.config["qmax_policy"])


def explain_navigation_task_policy(task) -> str:
    from display.services.scoring_explanation import explain_navigation_task

    return explain_navigation_task(task)["qmax_policy"]


class TestResultsPayload(TaskScoringTestCase):
    """The contest results carry what the results table needs to show a quality task like the live map does."""

    def results(self) -> dict:
        user = get_user_model().objects.create_superuser("s20b-results@example.com", "pw")
        client = APIClient()
        client.force_authenticate(user)
        response = client.get(reverse("contests-results-details", kwargs={"pk": self.contest.pk}))
        self.assertEqual(200, response.status_code, response.content)
        return response.json()

    def linked_tests(self, results: dict, task) -> list[dict]:
        return [
            test
            for result_task in results["task_set"]
            for test in result_task["tasktest_set"]
            if test["navigation_task"] == task.pk
        ]

    def test_a_quality_test_says_how_its_score_is_made_who_did_not_fly_and_that_it_is_provisional(self):
        a, b, c = self.contestants
        self.fly(a, 1200)
        self.fly(b, 1200, {"points": -300})
        (test,) = self.linked_tests(self.results(), self.task)
        scoring = test["scoring"]
        self.assertEqual("quality", scoring["scoring_model"])
        self.assertEqual(1000, scoring["task_value"])
        self.assertEqual(QMAX_BEST_IN_TASK, scoring["qmax_policy"])
        self.assertTrue(scoring["scores_provisional"])
        self.assertIn("final when all flights are finished", scoring["provisional_explanation"])
        self.assertEqual([c.team_id], scoring["not_flown_team_ids"])

    def test_a_circle_test_is_never_provisional_and_is_out_of_250(self):
        from display.utilities.task_types import CIRCLE

        circle = self.make_task(CIRCLE)
        self.make_contestant(circle, 1)  # a flight that is not finished
        (test,) = self.linked_tests(self.results(), circle)
        self.assertFalse(test["scoring"]["scores_provisional"])
        self.assertEqual(250, test["scoring"]["score_scale"])

    def test_the_test_is_final_when_every_flight_is_finished(self):
        from display.models import ContestantTrack

        a, *_ = self.contestants
        self.fly(a, 1200)
        ContestantTrack.objects.filter(contestant__navigation_task=self.task).update(calculator_finished=True)
        (test,) = self.linked_tests(self.results(), self.task)
        self.assertFalse(test["scoring"]["scores_provisional"])

    def test_a_penalty_test_is_marked_as_one_and_a_test_without_a_task_has_no_scoring(self):
        from display.models import Task, TaskTest

        legacy = self.make_task(None)
        self.make_contestant(legacy)
        manual = Task.objects.create(contest=self.contest, name="Manual", heading="Manual")
        TaskTest.objects.create(task=manual, name="Manual test", heading="Manual", index=0)
        results = self.results()
        (legacy_test,) = self.linked_tests(results, legacy)
        self.assertEqual({"scoring_model": "penalties"}, legacy_test["scoring"])
        manual_tests = [
            test for task in results["task_set"] if task["id"] == manual.pk for test in task["tasktest_set"]
        ]
        self.assertIsNone(manual_tests[0]["scoring"])
