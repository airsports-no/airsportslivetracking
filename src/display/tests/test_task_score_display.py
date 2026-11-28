"""
What the front ends are given to show the task score of a quality task (slice S10): the payloads of the live map's
websocket, the score data, the flight summary facts and the sort direction. Tasks of the penalty model are pinned to
the shapes they always had.
"""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from display.models import ContestantTrack, ScoreLogEntry
from display.services.flight_summaries import flight_facts
from display.services.task_scoring import task_scores_are_provisional
from display.tests.test_task_scoring import TaskScoringTestCase
from display.utilities.task_types import SCORING_PENALTIES, SCORING_QUALITY
from display.viewsets import generate_score_data
from websocket_channels import serialize_contestant_track, serialize_score_log_entry


class TestLiveMapPayloads(TaskScoringTestCase):
    def test_the_log_entry_carries_its_kind_and_score_type(self):
        a, _, _ = self.contestants
        entry = self.log(a, -12, kind="penalty", score_type="backtracking")
        payload = serialize_score_log_entry(entry)
        self.assertEqual("penalty", payload["score_kind"])
        self.assertEqual("backtracking", payload["score_type"])

    def test_the_track_carries_the_raw_values_so_the_map_can_show_the_arithmetic(self):
        a, _, _ = self.contestants
        self.fly(a, 1200, {"points": -300}, {"points": 50, "kind": "percentage_penalty", "score_type": "backtracking"})
        payload = serialize_contestant_track(self.track(a))
        self.assertEqual(900, payload["raw_quality"])
        self.assertEqual(1200, payload["quality_start"])
        self.assertEqual(1200, payload["quality_theoretical_maximum"])
        self.assertEqual(50, payload["percentage_penalty"])
        self.assertEqual({"gate_score": -300.0}, payload["quality_breakdown"])
        # What was always there stays
        for key in ("score", "current_state", "calculator_started", "calculator_finished", "passed_starting_gate"):
            self.assertIn(key, payload)

    def test_a_flight_that_changes_the_score_of_another_contestant_pushes_that_contestants_track(self):
        a, b, _ = self.contestants
        self.fly(a, 1200, {"points": -300})  # a is the best: 1000
        pushed = []

        def capture(facade, contestant):
            track = ContestantTrack.objects.get(contestant=contestant)
            pushed.append((contestant.pk, serialize_contestant_track(track)))

        with patch("websocket_channels.WebsocketFacade.transmit_basic_information", capture):
            self.fly(b, 1200)  # b is the new best: a falls to 750
        by_contestant = dict(pushed)
        self.assertIn(a.pk, by_contestant, "the contestant whose score fell is pushed too")
        self.assertEqual(750, by_contestant[a.pk]["score"])
        self.assertEqual(900, by_contestant[a.pk]["raw_quality"])
        self.assertEqual(1000, by_contestant[b.pk]["score"])

    def test_the_score_data_has_the_same_additions(self):
        a, _, _ = self.contestants
        self.fly(a, 1200, {"points": -300})
        ScoreLogEntry.objects.filter(contestant=a).update(type="anomaly")  # the map's log holds the anomalies
        data = generate_score_data(a.pk)
        self.assertEqual(900, data["contestant_track"]["raw_quality"])
        self.assertEqual("penalty", data["score_log_entries"][0]["score_kind"])

    def test_the_task_is_provisional_until_all_flights_are_finished(self):
        a, _, _ = self.contestants
        self.fly(a, 1200, finished=False)
        self.assertTrue(task_scores_are_provisional(self.task))


class TestSortDirection(TaskScoringTestCase):
    def test_a_quality_task_sorts_highest_first_whatever_the_scorecard_says(self):
        self.task.scorecard.score_sorting_direction = "asc"
        self.task.scorecard.save(update_fields=["score_sorting_direction"])
        self.assertEqual("desc", self.task.score_sorting_direction)

    def test_a_penalty_task_keeps_the_direction_of_its_scorecard(self):
        legacy = self.make_task(None)
        self.assertEqual(legacy.scorecard.score_sorting_direction, legacy.score_sorting_direction)
        self.assertEqual("asc", legacy.score_sorting_direction)


class TestFlightFacts(TaskScoringTestCase):
    def test_a_quality_flight_is_a_whole_number_out_of_the_task_value_and_says_how_to_read_the_log(self):
        a, b, _ = self.contestants
        self.fly(a, 1200)
        self.fly(
            b,
            1200,
            {"points": -325},
            {"points": 20, "kind": "percentage_penalty", "score_type": "altitude"},
            finished=False,
        )
        facts = flight_facts(type(b).objects.get(pk=b.pk))
        # 1000 x 875/1200 = 729.17, less 20% = 583.3 -> 583
        self.assertEqual(583, facts["final_score"])
        self.assertIsInstance(facts["final_score"], int)
        self.assertEqual("higher is better", facts["score_sorting"])
        self.assertEqual(1000, facts["task_value"])
        self.assertTrue(facts["scores_provisional"])
        self.assertIn("out of 1000", facts["scoring_note"])
        self.assertIn("provisional", facts["scoring_note"])
        kinds = [event["kind"] for event in facts["events"]]
        self.assertTrue(any(kind.startswith("percentage penalty") for kind in kinds))
        ContestantTrack.objects.filter(contestant__in=[a, b]).update(calculator_finished=True)
        ContestantTrack.objects.exclude(contestant__in=[a, b]).update(calculator_finished=True)
        facts = flight_facts(type(b).objects.get(pk=b.pk))
        self.assertEqual(2, facts["rank"])
        self.assertFalse(facts["scores_provisional"])
        self.assertNotIn("provisional", facts["scoring_note"])

    def test_a_penalty_flight_has_none_of_it(self):
        legacy = self.make_task(None)
        contestant = self.make_contestant(legacy)
        facts = flight_facts(contestant)
        for key in ("task_value", "scores_provisional", "scoring_note"):
            self.assertNotIn(key, facts)
        self.assertEqual("lower is better", facts["score_sorting"])


class TestPenaltyEndpointsAndTaskData(TaskScoringTestCase):
    def _client(self):
        from rest_framework.test import APIClient

        user = get_user_model().objects.create_superuser("s10@example.com", "pw")
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_the_gate_times_response_tells_the_scoring_of_the_task(self):
        a, _, _ = self.contestants
        self.fly(a, 1200, {"points": -300})
        response = self._client().get(
            reverse(
                "contestants-gate-times",
                kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.task.pk, "pk": a.pk},
            )
        )
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(SCORING_QUALITY, body["scoring_model"])
        self.assertEqual(1000, body["task_value"])
        entry = body["log"]["TP1"][0]
        self.assertEqual(-300, entry["points"])
        self.assertEqual("penalty", entry["score_kind"])

    def test_the_gate_times_response_of_a_penalty_task(self):
        legacy = self.make_task(None)
        contestant = self.make_contestant(legacy)
        response = self._client().get(
            reverse(
                "contestants-gate-times",
                kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": legacy.pk, "pk": contestant.pk},
            )
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(SCORING_PENALTIES, response.json()["scoring_model"])
        json.dumps(response.json())


class TestScorecardEditorData(TaskScoringTestCase):
    def _scorecard(self, task):
        from rest_framework.test import APIClient

        user = get_user_model().objects.create_superuser(f"editor{task.pk}@example.com", "pw")
        client = APIClient()
        client.force_authenticate(user)
        response = client.get(
            reverse("navigationtasks-scorecard", kwargs={"contest_pk": self.contest.pk, "pk": task.pk})
        )
        self.assertEqual(200, response.status_code, response.content)
        return response.json()

    def test_a_quality_task_type_can_use_the_quality_model_and_says_what_it_uses_now(self):
        data = self._scorecard(self.task)
        self.assertTrue(data["can_use_quality_scoring"])
        self.assertEqual("quality", data["effective_scoring_model"])
        self.assertEqual(1000, data["effective_task_value"])
        self.assertIn("qmax_policy", data)

    def test_a_penalty_task_type_cannot(self):
        legacy = self.make_task(None)
        data = self._scorecard(legacy)
        self.assertFalse(data["can_use_quality_scoring"])
        self.assertEqual("penalties", data["effective_scoring_model"])


class TestManagerEmailScore(TaskScoringTestCase):
    def test_a_quality_score_reads_out_of_the_task_value_and_a_penalty_score_as_before(self):
        from display.services.manager_notifications import _score_text

        a, _, _ = self.contestants
        self.fly(a, 1200, {"points": -300})
        self.assertEqual("1000 of 1000", _score_text(self.track(a), self.task))
        legacy = self.make_task(None)
        contestant = self.make_contestant(legacy)
        ContestantTrack.objects.filter(contestant=contestant).update(score=17.5)
        self.assertEqual("17.5", _score_text(self.track(contestant), legacy))
