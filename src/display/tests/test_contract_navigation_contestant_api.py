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


class TestContractNavigationContestantApi(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *_args):
        create_scorecards()
        self.user = get_user_model().objects.create(email="contestant-api@example.com")
        Person.objects.create(first_name="Contestant", last_name="Api", email=self.user.email)
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Contestant API route", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)

        self.contest = Contest.objects.create(
            name="Contestant API Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)

        self.navigation_task = NavigationTask.create(
            name="Contestant API Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            task_config={"contract_time_seconds": 600},
        )
        self.editable_route = EditableRoute.objects.create(
            name="Contestant API primitives",
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
        self.navigation_task.editable_route = self.editable_route
        self.navigation_task.save(update_fields=["editable_route"])

        team = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="One", email="pilot-api@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-CAPI"),
        )
        self.contest_team = ContestTeam.objects.create(contest=self.contest, team=team, air_speed=70)
        self.client.force_login(self.user)
        self.url = reverse(
            "contestants-list",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk},
        )

    @patch("display.viewsets._assert_can_reserve_task_slot")
    def test_contestant_api_create_persists_contract_declaration_payload(self, _mock_guard):
        response = self.client.post(
            self.url,
            {
                "contestant_number": 1,
                "team": self.contest_team.team.pk,
                "tracking_service": str(self.contest_team.tracking_service),
                "tracking_device": self.contest_team.tracking_device or "",
                "tracker_device_id": self.contest_team.tracker_device_id or "",
                "takeoff_time": "2026-08-01T09:55:00Z",
                "adaptive_start": False,
                "tracker_start_time": "2026-08-01T09:45:00Z",
                "finished_by_time": "2026-08-01T11:30:00Z",
                "minutes_to_starting_point": 5,
                "air_speed": 70,
                "wind_direction": 0,
                "wind_speed": 0,
                "declaration_payload": {
                    "declared_before_mp": ["A"],
                    "declared_after_mp": ["C"],
                    "declared_t_seconds": 82,
                },
            },
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)
        self.assertEqual(
            contestant.contestanttaskconfiguration.declaration_payload,
            {"declared_sequence": ["A", "MP", "C", "FP"], "declared_t_seconds": 82},
        )

    @patch("display.viewsets._assert_can_reserve_task_slot")
    def test_contestant_detail_exposes_contract_declaration_payload(self, _mock_guard):
        create_response = self.client.post(
            self.url,
            {
                "contestant_number": 1,
                "team": self.contest_team.team.pk,
                "tracking_service": str(self.contest_team.tracking_service),
                "tracking_device": self.contest_team.tracking_device or "",
                "tracker_device_id": self.contest_team.tracker_device_id or "",
                "takeoff_time": "2026-08-01T09:55:00Z",
                "adaptive_start": False,
                "tracker_start_time": "2026-08-01T09:45:00Z",
                "finished_by_time": "2026-08-01T11:30:00Z",
                "minutes_to_starting_point": 5,
                "air_speed": 70,
                "wind_direction": 0,
                "wind_speed": 0,
                "declaration_payload": {
                    "declared_before_mp": ["A"],
                    "declared_after_mp": ["C"],
                    "declared_t_seconds": 82,
                },
            },
            content_type="application/json",
        )
        self.assertEqual(200, create_response.status_code, create_response.content)

        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)
        detail_url = reverse(
            "contestants-detail",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk, "pk": contestant.pk},
        )
        detail_response = self.client.get(detail_url)

        self.assertEqual(200, detail_response.status_code, detail_response.content)
        self.assertEqual(
            detail_response.json().get("declaration_payload"),
            {"declared_sequence": ["A", "MP", "C", "FP"], "declared_t_seconds": 82},
        )
