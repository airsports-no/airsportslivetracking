import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, NavigationTask, Route, Scorecard, Team, Crew, Person, Aeroplane, ContestUsageLedger, Contestant, ContestTeam, EditableRoute
from utilities.mock_utilities import TraccarMock


@override_settings(DEFAULT_FREE_CONTESTANT_LIMIT=3)
class TestNavigationTaskDetailWarnings(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="task-owner@example.com")
        self.owner_person = Person.objects.create(first_name="Owner", last_name="Pilot", email=self.user.email)
        self.contest = Contest.objects.create(
            name="Warning Contest",
            time_zone="Europe/Oslo",
            start_time="2026-08-01T09:00:00+00:00",
            finish_time="2026-08-01T17:00:00+00:00",
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)
        self.navigation_task = NavigationTask.objects.create(
            name="Warning Task",
            contest=self.contest,
            route=Route.objects.create(name="Warning route"),
            original_scorecard=Scorecard.objects.create(name="Warning card", shortcut_name="warn-card"),
            start_time="2026-08-01T09:00:00+00:00",
            finish_time="2026-08-01T17:00:00+00:00",
        )
        self.owner_team = Team.objects.create(
            crew=Crew.objects.create(member1=self.owner_person),
            aeroplane=Aeroplane.objects.create(registration="LN-OWNER-WARN"),
        )
        self.guest_team_1 = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Guest", last_name="One", email="guest1@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-GUEST1"),
        )
        self.guest_team_2 = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Guest", last_name="Two", email="guest2@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-GUEST2"),
        )
        self.navigation_task.contestant_set.create(
            team=self.owner_team,
            contestant_number=1,
            takeoff_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            tracker_start_time=datetime.datetime(2026, 8, 1, 8, 50, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2026, 8, 1, 11, 0, tzinfo=datetime.timezone.utc),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )
        self.navigation_task.contestant_set.create(
            team=self.guest_team_1,
            contestant_number=2,
            takeoff_time=datetime.datetime(2026, 8, 1, 9, 5, tzinfo=datetime.timezone.utc),
            tracker_start_time=datetime.datetime(2026, 8, 1, 8, 55, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2026, 8, 1, 11, 5, tzinfo=datetime.timezone.utc),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )
        self.navigation_task.contestant_set.create(
            team=self.guest_team_2,
            contestant_number=3,
            takeoff_time=datetime.datetime(2026, 8, 1, 9, 10, tzinfo=datetime.timezone.utc),
            tracker_start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2026, 8, 1, 11, 10, tzinfo=datetime.timezone.utc),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )
        ContestUsageLedger.objects.create(
            contest=self.contest,
            navigation_task=self.navigation_task,
            pilot=self.guest_team_1.crew.member1,
            kind=ContestUsageLedger.TASK_PILOT_STARTED,
        )

    def test_navigation_task_detail_shows_capacity_status_below_limit(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("navigationtask_detail", kwargs={"pk": self.navigation_task.pk}))

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Pilot capacity status")
        self.assertContains(response, "2 / 3 guest pilot slots are reserved on this task")
        self.assertContains(response, "The contest owner is exempt.")


class TestNavigationTaskDetailTurnpointDeclarationLink(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *_args):
        create_scorecards()
        self.user = get_user_model().objects.create(email="turnpoint-detail@example.com")
        self.person = Person.objects.create(first_name="Detail", last_name="User", email=self.user.email)
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.contest = Contest.objects.create(
            name="Turnpoint Detail Contest",
            time_zone="Europe/Oslo",
            start_time="2026-08-01T09:00:00+00:00",
            finish_time="2026-08-01T17:00:00+00:00",
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Turnpoint detail route", file.readlines()[1:])
            route = editable_route.create_precision_route(True, self.scorecard)
        self.navigation_task = NavigationTask.create(
            name="Turnpoint Detail Task",
            contest=self.contest,
            route=route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype="turnpoint_hunt",
        )
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Turnpoint detail primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "cat-2", "name": "B", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.3, 60.3]}},
                    {"type": "Feature", "properties": {"id": "kt-1", "name": "CP1", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.25, 60.25]}},
                    {"type": "Feature", "properties": {"id": "kt-2", "name": "CP2", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                    {"type": "Feature", "properties": {"id": "kt-3", "name": "CP3", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.45, 60.45]}},
                    {"type": "Feature", "properties": {"id": "obs-1", "name": "A", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.5, 60.5]}},
                    {"type": "Feature", "properties": {"id": "obs-2", "name": "B", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.51, 60.51]}},
                ],
            },
        )
        self.navigation_task.save(update_fields=["editable_route"])
        team = Team.objects.create(
            crew=Crew.objects.create(member1=self.person),
            aeroplane=Aeroplane.objects.create(registration="LN-DETAIL"),
        )
        ContestTeam.objects.create(contest=self.contest, team=team, air_speed=70)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            contestant_number=1,
            takeoff_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            tracker_start_time=datetime.datetime(2026, 8, 1, 8, 50, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2026, 8, 1, 11, 0, tzinfo=datetime.timezone.utc),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )

    def test_navigation_task_detail_shows_turnpoint_hunt_declaration_link(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("navigationtask_detail", kwargs={"pk": self.navigation_task.pk}))
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Edit declaration")
        self.assertContains(
            response,
            f"/contestant-declaration/{self.contest.pk}/{self.navigation_task.pk}/{self.contestant.pk}",
        )
