from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import EditableRoute, Scorecard
from display.utilities.cima_task_type_definitions import (
    ANR_CATALOGUE,
    CIMA_ANR_SCORECARD,
    CIMA_PRECISION_SCORECARD,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    DURATION,
)
from display.utilities.gate_definitions import FINISHPOINT, STARTINGPOINT, TURNPOINT
from display.utilities.navigation_task_type_definitions import ANR_CORRIDOR, PRECISION


class TestCimaScorecards(TestCase):
    """
    CIMA tasks are created from their own scorecards: no procedure turns (the catalogue has none), the catalogue's time
    gate scoring, and points out of 1000 with the highest winning.
    """

    def setUp(self):
        create_scorecards()
        self.client.force_login(get_user_model().objects.create(email="cima-organiser@example.com"))

    def _choices(self, **params) -> list[str]:
        response = self.client.get(reverse("scorecards-choices"), params)
        self.assertEqual(200, response.status_code, response.content)
        return [item["shortcut_name"] for item in response.json()]

    def test_cima_precision_has_no_procedure_turns_and_catalogue_timing(self):
        scorecard = Scorecard.get_originals().get(shortcut_name=CIMA_PRECISION_SCORECARD)
        self.assertFalse(scorecard.use_procedure_turns)
        self.assertEqual("desc", scorecard.score_sorting_direction)
        self.assertEqual(1000, scorecard.initial_score)
        for gate_type in (STARTINGPOINT, TURNPOINT, FINISHPOINT):
            gate = scorecard.get_gate_scorecard(gate_type)
            self.assertEqual(0, gate.missed_procedure_turn_penalty)
            self.assertEqual((1, 180, 180), (gate.penalty_per_second, gate.maximum_penalty, gate.missed_penalty))
            self.assertEqual((0, 0), (gate.graceperiod_before, gate.graceperiod_after))

    def test_cima_anr_is_fai_anr_scored_out_of_1000(self):
        fai_anr = Scorecard.get_originals().get(shortcut_name="FAI ANR")
        cima_anr = Scorecard.get_originals().get(shortcut_name=CIMA_ANR_SCORECARD)
        self.assertEqual(("asc", 0), (fai_anr.score_sorting_direction, fai_anr.initial_score))
        self.assertEqual(("desc", 1000), (cima_anr.score_sorting_direction, cima_anr.initial_score))
        self.assertEqual(fai_anr.config["gates"], cima_anr.config["gates"])
        self.assertEqual(400, cima_anr.backtracking_maximum_penalty)
        self.assertEqual(ANR_CORRIDOR, cima_anr.calculator)

    def test_a_cima_subtype_is_offered_only_its_own_scorecard(self):
        self.assertEqual(
            [CIMA_PRECISION_SCORECARD],
            self._choices(task_type=PRECISION, task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS),
        )
        self.assertEqual([CIMA_ANR_SCORECARD], self._choices(task_type=ANR_CORRIDOR, task_subtype=ANR_CATALOGUE))

    def test_legacy_tasks_and_subtypes_without_a_scorecard_are_not_offered_cima_scorecards(self):
        for params in ({"task_type": PRECISION}, {"task_type": PRECISION, "task_subtype": DURATION}):
            choices = self._choices(**params)
            self.assertIn("FAI Precision", choices)
            self.assertNotIn(CIMA_PRECISION_SCORECARD, choices)
        self.assertNotIn(CIMA_ANR_SCORECARD, self._choices(task_type=ANR_CORRIDOR))

    def test_route_from_cima_precision_has_no_procedure_turns(self):
        scorecard = Scorecard.get_originals().get(shortcut_name=CIMA_PRECISION_SCORECARD)
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("CIMA route", file.readlines()[1:])
        route = editable_route.create_route(
            PRECISION, scorecard, None, None, task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS
        )
        self.assertFalse(route.use_procedure_turns)
        self.assertFalse(any(waypoint.is_procedure_turn for waypoint in route.waypoints))
