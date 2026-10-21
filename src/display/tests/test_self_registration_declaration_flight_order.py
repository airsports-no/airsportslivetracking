import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    ContestTeam,
    Crew,
    EditableRoute,
    NavigationTask,
    Person,
    Scorecard,
    Team,
)
from display.utilities.cima_task_type_definitions import CONTRACT_NAVIGATION_TIME_CONTROLS
from utilities.mock_utilities import TraccarMock

DECLARATION = {"declared_before_mp": ["A"], "declared_after_mp": ["C"], "declared_t_seconds": 82}


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
@patch("display.viewsets._assert_can_reserve_task_slot")
@patch("display.viewsets.assert_can_self_register_contestant")
@patch("display.tasks.generate_and_maybe_notify_flight_order.apply_async")
class TestSelfRegistrationDeclarationFlightOrder(TestCase):
    """
    A pilot booking a flight in a task requiring a declaration gets the flight order when the declaration is saved, not at
    booking (it shows the declared route). A flight added by a manager never gets one automatically.
    """

    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *_args):
        create_scorecards()
        self.user = get_user_model().objects.create(email="declaring-pilot@example.com", first_name="Declaring")
        pilot = Person.objects.create(first_name="Declaring", last_name="Pilot", email=self.user.email)
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Declaration route", file.readlines()[1:])
            route = editable_route.create_precision_route(True, scorecard)
        start = datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc)
        finish = datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc)
        self.contest = Contest.objects.create(
            name="Declaration contest",
            time_zone="Europe/Oslo",
            start_time=start,
            finish_time=finish,
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)
        self.navigation_task = NavigationTask.create(
            name="Contract navigation",
            contest=self.contest,
            route=route,
            original_scorecard=scorecard,
            start_time=start,
            finish_time=finish,
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            task_config={"contract_time_seconds": 600},
            allow_self_management=True,
        )
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Declaration primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "cat-2", "name": "MP", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.25, 60.25]}},
                    {"type": "Feature", "properties": {"id": "cat-3", "name": "C", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                ],
            },
        )
        self.navigation_task.save(update_fields=["editable_route"])
        team = Team.objects.create(crew=Crew.objects.create(member1=pilot), aeroplane=Aeroplane.objects.create(registration="LN-DEC"))
        self.contest_team = ContestTeam.objects.create(contest=self.contest, team=team, air_speed=70)
        self.client.force_login(self.user)

    def _self_register(self) -> Contestant:
        response = self.client.post(
            reverse(
                "navigationtasks-contestant-self-registration",
                kwargs={"contest_pk": self.contest.pk, "pk": self.navigation_task.pk},
            ),
            {
                "starting_point_time": "2026-08-01T10:00:00Z",
                "contest_team": self.contest_team.pk,
                "adaptive_start": False,
                "wind_speed": 0,
                "wind_direction": 0,
                "flight_mode": "real",
            },
            content_type="application/json",
        )
        self.assertEqual(201, response.status_code, response.content)
        return Contestant.objects.get(pk=response.json()["id"])

    def _manager_adds(self) -> Contestant:
        response = self.client.post(
            reverse("contestants-list", kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk}),
            {
                "contestant_number": 1,
                "team": self.contest_team.team.pk,
                "tracking_service": str(self.contest_team.tracking_service),
                "tracking_device": self.contest_team.tracking_device or "",
                "tracker_device_id": "",
                "takeoff_time": "2026-08-01T09:55:00Z",
                "adaptive_start": False,
                "tracker_start_time": "2026-08-01T09:45:00Z",
                "finished_by_time": "2026-08-01T11:30:00Z",
                "minutes_to_starting_point": 5,
                "air_speed": 70,
                "wind_direction": 0,
                "wind_speed": 0,
            },
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        return Contestant.objects.get(pk=response.json()["id"])

    def _save_declaration(self, contestant: Contestant, declaration: dict):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                reverse(
                    "contestants-detail",
                    kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk, "pk": contestant.pk},
                ),
                {"declaration_payload": declaration},
                content_type="application/json",
            )
        self.assertEqual(200, response.status_code, response.content)

    def test_self_registration_waits_for_declaration_then_sends_flight_order(self, flight_order, *_args):
        contestant = self._self_register()
        self.assertTrue(contestant.self_registered)
        flight_order.assert_not_called()

        self._save_declaration(contestant, DECLARATION)
        flight_order.assert_called_once_with((contestant.pk, self.user.email, "Declaring", True))

    def test_invalid_declaration_sends_no_flight_order(self, flight_order, *_args):
        contestant = self._self_register()
        self._save_declaration(contestant, {})
        flight_order.assert_not_called()

    def test_manager_added_contestant_gets_no_flight_order_at_declaration(self, flight_order, *_args):
        contestant = self._manager_adds()
        self.assertFalse(contestant.self_registered)
        self._save_declaration(contestant, DECLARATION)
        flight_order.assert_not_called()

    def test_self_registration_without_required_declaration_sends_flight_order_at_once(self, flight_order, *_args):
        self.navigation_task.task_subtype = ""
        self.navigation_task.save(update_fields=["task_subtype"])
        contestant = self._self_register()
        flight_order.assert_called_once_with((contestant.pk, self.user.email, "Declaring", True))
