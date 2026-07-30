import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from unittest.mock import patch

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import (
    Aeroplane,
    Contest,
    ContestTeam,
    Crew,
    EditableRoute,
    NavigationTask,
    Person,
    Team,
    Scorecard,
)
from display.utilities.cima_task_type_definitions import CONTRACT_NAVIGATION_TIME_CONTROLS
from utilities.mock_utilities import TraccarMock


class TestContractNavigationQuickAddUI(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.user = get_user_model().objects.create(email="quickadd-organizer@example.com")
        Person.objects.create(first_name="Quick", last_name="Organizer", email=self.user.email)
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Quick add declaration UI", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)

        self.contest = Contest.objects.create(
            name="Quick Add Declaration Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)

        self.navigation_task = NavigationTask.create(
            name="Quick Add Declaration Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            task_config={"contract_time_seconds": 600},
        )
        self.editable_route = EditableRoute.objects.create(
            name="Quick Add Declaration primitives",
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
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="Quick", email="pilot-quick@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-QDECL"),
        )
        self.contest_team = ContestTeam.objects.create(contest=self.contest, team=team, air_speed=70)
        self.quick_add_url = reverse("contestant_quick_create", kwargs={"navigationtask_pk": self.navigation_task.pk})

    def test_quick_add_view_does_not_render_contract_declaration_controls(self):
        self.client.force_login(self.user)
        response = self.client.get(self.quick_add_url)
        self.assertEqual(200, response.status_code)
        self.assertNotContains(response, 'id="id_declared_before_mp_1"')
        self.assertNotContains(response, 'id="id_declared_after_mp_1"')
        self.assertNotContains(response, 'id="add-before-mp-slot"')
        self.assertNotContains(response, 'id="remove-before-mp-slot"')
        self.assertNotContains(response, 'id="add-after-mp-slot"')
        self.assertNotContains(response, 'id="remove-after-mp-slot"')
        self.assertNotContains(response, "Task-specific declaration")

    def test_quick_add_persists_empty_contract_declaration(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.quick_add_url,
            {
                "contest_team": self.contest_team.pk,
                "starting_point_time": "2026-08-01T10:00",
                "adaptive_start": False,
            },
        )
        self.assertEqual(302, response.status_code)
        contestant = self.navigation_task.contestant_set.get(team=self.contest_team.team)
        self.assertEqual(contestant.contestanttaskconfiguration.declaration_payload, {})
