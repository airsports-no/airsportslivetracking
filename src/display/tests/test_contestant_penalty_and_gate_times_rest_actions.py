"""
Tests for ContestantViewSet's apply_quarantine_penalty/remove_score_log_entry/gate_times/
playing_cards/assign_playing_card/remove_playing_card REST actions - the API equivalents of the
classic apply_contestant_quarantine_penalty, delete_score_item, ContestantGateTimesView,
contestant_cards_list, and contestant_card_remove views (views.py), added as part of migrating
navigationtask_detail.html to the React SPA.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework.test import APITestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    Crew,
    EditableRoute,
    GateCumulativeScore,
    NavigationTask,
    Person,
    PlayingCard,
    Scorecard,
    ScoreLogEntry,
    Team,
)
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestantPenaltyAndGateTimesRestActions(APITestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Penalty REST test", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)
        self.contest = Contest.objects.create(
            name="Penalty REST Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        self.navigation_task = NavigationTask.create(
            name="Penalty REST Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Penalty", last_name="Rest"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-PREST"))
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="penalty-rest-test",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )
        self.manager = get_user_model().objects.create(email="penalty-rest-manager@example.com")
        assign_perm("view_contest", self.manager, self.contest)
        assign_perm("change_contest", self.manager, self.contest)
        self.client.force_login(user=self.manager)

    def _url(self, action, **extra_kwargs):
        kwargs = {
            "contest_pk": self.contest.pk,
            "navigationtask_pk": self.navigation_task.pk,
            "pk": self.contestant.pk,
        }
        kwargs.update(extra_kwargs)
        return reverse(f"contestants-{action}", kwargs=kwargs)

    @patch("display.models.scoring_models.ScoreLogEntry.push")
    @patch("display.models.scoring_models.TrackAnnotation.push")
    def test_apply_quarantine_penalty_creates_entry_and_updates_score(self, *args):
        response = self.client.post(
            self._url("apply-quarantine-penalty"),
            {"points": 35, "reason": "late exit from quarantine", "category": "quarantine"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.contestant.contestanttrack.refresh_from_db()
        self.assertEqual(self.contestant.contestanttrack.score, 35.0)
        entry = ScoreLogEntry.objects.get(contestant=self.contestant, gate="ADMIN-QUAR")
        self.assertEqual(entry.message, "late exit from quarantine")
        self.assertEqual(response.data["id"], entry.pk)

    @patch("display.models.scoring_models.ScoreLogEntry.push")
    @patch("display.models.scoring_models.TrackAnnotation.push")
    def test_apply_quarantine_penalty_defaults_reason_from_category(self, *args):
        response = self.client.post(self._url("apply-quarantine-penalty"), {"category": "fuel"}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        entry = ScoreLogEntry.objects.get(contestant=self.contestant, gate="ADMIN-FUEL")
        self.assertEqual(entry.message, "fuel-check breach")
        self.assertEqual(entry.points, 100.0)

    def test_apply_quarantine_penalty_rejects_unknown_category(self, *args):
        response = self.client.post(self._url("apply-quarantine-penalty"), {"category": "bogus"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_apply_quarantine_penalty_requires_change_contest_permission(self, *args):
        viewer = get_user_model().objects.create(email="penalty-rest-viewer@example.com")
        assign_perm("view_contest", viewer, self.contest)
        self.client.force_login(user=viewer)
        response = self.client.post(self._url("apply-quarantine-penalty"), {"category": "quarantine"}, format="json")
        self.assertEqual(response.status_code, 403)

    @patch("display.models.scoring_models.ScoreLogEntry.push")
    @patch("display.models.scoring_models.TrackAnnotation.push")
    def test_remove_score_log_entry_reverses_score(self, *args):
        create_response = self.client.post(
            self._url("apply-quarantine-penalty"),
            {"points": 20, "reason": "x", "category": "quarantine"},
            format="json",
        )
        entry_pk = create_response.data["id"]
        self.contestant.contestanttrack.refresh_from_db()
        self.assertEqual(self.contestant.contestanttrack.score, 20.0)

        response = self.client.post(self._url("remove-score-log-entry", entry_pk=entry_pk))

        self.assertEqual(response.status_code, 204, response.content)
        self.assertFalse(ScoreLogEntry.objects.filter(pk=entry_pk).exists())
        self.contestant.contestanttrack.refresh_from_db()
        self.assertEqual(self.contestant.contestanttrack.score, 0.0)

    def test_remove_score_log_entry_404_for_other_contestants_entry(self, *args):
        other_crew = Crew.objects.create(
            member1=Person.objects.create(first_name="Other", last_name="Rest", email="other-rest@example.com")
        )
        other_team = Team.objects.create(crew=other_crew, aeroplane=Aeroplane.objects.create(registration="LN-OTHR"))
        other_contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=other_team,
            takeoff_time=self.contestant.takeoff_time + datetime.timedelta(minutes=10),
            tracker_start_time=self.contestant.tracker_start_time + datetime.timedelta(minutes=10),
            finished_by_time=self.contestant.finished_by_time + datetime.timedelta(minutes=10),
            tracker_device_id="other-rest-test",
            contestant_number=2,
        )
        GateCumulativeScore.objects.create(contestant=other_contestant, gate="ADMIN-QUAR", points=5.0)
        other_entry = ScoreLogEntry.objects.create(
            contestant=other_contestant,
            time=datetime.datetime.now(datetime.timezone.utc),
            gate="ADMIN-QUAR",
            type="anomaly",
            message="belongs to someone else",
            points=5.0,
            planned=None,
            actual=None,
            offset_string="",
            string="",
            times_string="",
        )

        response = self.client.post(self._url("remove-score-log-entry", entry_pk=other_entry.pk))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(ScoreLogEntry.objects.filter(pk=other_entry.pk).exists())

    def test_gate_times_returns_waypoints_and_penalty_metadata(self, *args):
        response = self.client.get(self._url("gate-times"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["rendered_waypoints"][0], "SP")
        self.assertEqual(response.data["rendered_waypoints"][-1], "FP")
        self.assertGreater(response.data["total_distance"], 0)
        self.assertTrue(response.data["can_apply_quarantine_penalty"])
        self.assertIn("quarantine", response.data["administrative_penalty_categories"])
        self.assertEqual(response.data["log"], {})
        self.assertEqual(response.data["actual_times"], {})

    def test_gate_times_hidden_from_user_without_view_contest_permission(self, *args):
        outsider = get_user_model().objects.create(email="penalty-rest-outsider@example.com")
        self.client.force_login(user=outsider)
        response = self.client.get(self._url("gate-times"))
        # No view_contest permission means the contestant isn't even in the outsider's
        # queryset - a 404 (object hidden), not a 403, matching how the DRF permission stack
        # for this viewset treats every other unauthorized GET.
        self.assertEqual(response.status_code, 404)

    def test_gate_times_visible_but_cannot_apply_quarantine_penalty_for_viewer(self, *args):
        viewer = get_user_model().objects.create(email="penalty-rest-viewer@example.com")
        assign_perm("view_contest", viewer, self.contest)
        self.client.force_login(user=viewer)
        response = self.client.get(self._url("gate-times"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.data["can_apply_quarantine_penalty"])

    def test_playing_cards_empty_by_default(self, *args):
        response = self.client.get(self._url("playing-cards"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["cards"], [])

    def test_assign_and_remove_playing_card(self, *args):
        response = self.client.post(
            self._url("assign-playing-card"), {"waypoint_index": 0, "card": "As"}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)
        card = PlayingCard.objects.get(contestant=self.contestant, card="As")
        self.assertEqual(card.waypoint_name, "SP")

        list_response = self.client.get(self._url("playing-cards"))
        self.assertEqual(len(list_response.data["cards"]), 1)

        remove_response = self.client.post(self._url("remove-playing-card", card_pk=card.pk))
        self.assertEqual(remove_response.status_code, 204, remove_response.content)
        self.assertFalse(PlayingCard.objects.filter(pk=card.pk).exists())

    def test_assign_playing_card_rejects_out_of_range_waypoint(self, *args):
        response = self.client.post(
            self._url("assign-playing-card"), {"waypoint_index": 9999, "card": "As"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
