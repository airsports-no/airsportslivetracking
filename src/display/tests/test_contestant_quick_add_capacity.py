import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase
from guardian.shortcuts import assign_perm
from django.core.exceptions import ValidationError

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, NavigationTask, Route, Scorecard, ContestTeam, Team, Crew, Person, Aeroplane, Contestant, EditableRoute
from display.utilities.cima_task_type_definitions import CONTRACT_NAVIGATION_TIME_CONTROLS


class TestContestantQuickAddCapacity(TestCase):
    def setUp(self):
        create_scorecards()
        self.user = get_user_model().objects.create(email="quickadd-owner@example.com")
        self.owner_person = Person.objects.create(first_name="Owner", last_name="Pilot", email=self.user.email)
        self.contest = Contest.objects.create(
            name="Quick Add Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)
        self.navigation_task = NavigationTask.objects.create(
            name="Quick Add Task",
            contest=self.contest,
            route=Route.objects.create(name="Quick Add Route"),
            original_scorecard=Scorecard.objects.create(name="Quick Add Card", shortcut_name="quickadd-card"),
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            wind_speed=0,
            wind_direction=0,
            minutes_to_starting_point=5,
            minutes_to_landing=5,
        )
        guest_person = Person.objects.create(first_name="Guest", last_name="Pilot", email="guest-quickadd@example.com")
        guest_team = Team.objects.create(
            crew=Crew.objects.create(member1=guest_person),
            aeroplane=Aeroplane.objects.create(registration="LN-QADD"),
        )
        self.contest_team = ContestTeam.objects.create(contest=self.contest, team=guest_team, air_speed=70)
        self.url = reverse("contestant_quick_create", kwargs={"navigationtask_pk": self.navigation_task.pk})
        self.create_url = reverse("contestant_create", kwargs={"navigationtask_pk": self.navigation_task.pk})
        self.editable_route = EditableRoute.objects.create(
            name="Quick Add Capacity primitives",
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

    @patch("display.views._assert_can_reserve_task_slot")
    def test_quick_add_calls_reservation_guard(self, mock_guard):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {
                "contest_team": self.contest_team.pk,
                "starting_point_time": "2026-08-01T10:00",
                "adaptive_start": False,
            },
        )

        self.assertEqual(302, response.status_code)
        mock_guard.assert_called_once()

    @patch("display.views._assert_can_reserve_task_slot", side_effect=ValidationError("capacity blocked"))
    def test_quick_add_is_blocked_when_reservation_guard_rejects(self, _mock_guard):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {
                "contest_team": self.contest_team.pk,
                "starting_point_time": "2026-08-01T10:00",
                "adaptive_start": False,
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "capacity blocked")
        self.assertFalse(Contestant.objects.filter(navigation_task=self.navigation_task, team=self.contest_team.team).exists())

    def test_quick_add_is_blocked_when_contest_capacity_is_full_across_other_tasks(self):
        self.client.force_login(self.user)
        other_task = NavigationTask.objects.create(
            name="Other Task",
            contest=self.contest,
            route=Route.objects.create(name="Other Route"),
            original_scorecard=Scorecard.objects.create(name="Other Card", shortcut_name="other-card"),
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            wind_speed=0,
            wind_direction=0,
            minutes_to_starting_point=5,
            minutes_to_landing=5,
        )
        reserved_pilot = Person.objects.create(first_name="Reserved", last_name="Pilot", email="reserved-quickadd@example.com")
        reserved_team = Team.objects.create(
            crew=Crew.objects.create(member1=reserved_pilot),
            aeroplane=Aeroplane.objects.create(registration="LN-QRES"),
        )
        Contestant.objects.create(
            team=reserved_team,
            navigation_task=other_task,
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

        with patch("display.views.resolve_contest_access") as mock_resolve:
            mock_resolve.return_value = type("Resolution", (), {"contestant_limit": 1, "contestants_used": 0, "enforcement_mode": "enforce"})()
            response = self.client.post(
                self.url,
                {
                    "contest_team": self.contest_team.pk,
                    "starting_point_time": "2026-08-01T10:00",
                    "adaptive_start": False,
                },
            )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "active pilot capacity")
        self.assertFalse(Contestant.objects.filter(navigation_task=self.navigation_task, team=self.contest_team.team).exists())

    def test_full_create_form_is_blocked_when_contest_capacity_is_full_across_other_tasks(self):
        self.client.force_login(self.user)
        other_task = NavigationTask.objects.create(
            name="Other Task 2",
            contest=self.contest,
            route=Route.objects.create(name="Other Route 2"),
            original_scorecard=Scorecard.objects.create(name="Other Card 2", shortcut_name="other-card-2"),
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            wind_speed=0,
            wind_direction=0,
            minutes_to_starting_point=5,
            minutes_to_landing=5,
        )
        reserved_pilot = Person.objects.create(first_name="Reserved2", last_name="Pilot", email="reserved2-create@example.com")
        reserved_team = Team.objects.create(
            crew=Crew.objects.create(member1=reserved_pilot),
            aeroplane=Aeroplane.objects.create(registration="LN-QRES2"),
        )
        Contestant.objects.create(
            team=reserved_team,
            navigation_task=other_task,
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

        with patch("display.views.resolve_contest_access") as mock_resolve:
            mock_resolve.return_value = type("Resolution", (), {"contestant_limit": 1, "contestants_used": 0, "enforcement_mode": "enforce"})()
            response = self.client.post(
                self.create_url,
                {
                    "contestant_number": 1,
                    "team": self.contest_team.team.pk,
                    "tracking_service": str(self.contest_team.tracking_service),
                    "tracking_device": self.contest_team.tracking_device or "",
                    "tracker_device_id": self.contest_team.tracker_device_id or "",
                    "takeoff_time": "2026-08-01T09:55",
                    "adaptive_start": False,
                    "tracker_start_time": "2026-08-01T09:45",
                    "finished_by_time": "2026-08-01T11:00",
                    "minutes_to_starting_point": 5,
                    "air_speed": 70,
                    "wind_direction": 0,
                    "wind_speed": 0,
                },
            )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "active pilot capacity")
        self.assertFalse(Contestant.objects.filter(navigation_task=self.navigation_task, team=self.contest_team.team).exists())

    def test_quick_add_keeps_contract_declaration_empty_until_dedicated_editor_is_used(self):
        self.navigation_task.task_subtype = CONTRACT_NAVIGATION_TIME_CONTROLS
        self.navigation_task.task_config = {"contract_time_seconds": 600}
        self.navigation_task.editable_route = self.editable_route
        self.navigation_task.save(update_fields=["task_subtype", "task_config", "editable_route"])

        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {
                "contest_team": self.contest_team.pk,
                "starting_point_time": "2026-08-01T10:00",
                "adaptive_start": False,
            },
        )

        self.assertEqual(302, response.status_code)
        contestant = Contestant.objects.get(navigation_task=self.navigation_task, team=self.contest_team.team)
        self.assertEqual(contestant.contestanttaskconfiguration.declaration_payload, {})
