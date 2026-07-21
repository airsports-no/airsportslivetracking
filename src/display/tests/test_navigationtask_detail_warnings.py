from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from guardian.shortcuts import assign_perm
import datetime

from display.models import Contest, NavigationTask, Route, Scorecard, Team, Crew, Person, Aeroplane, ContestUsageLedger


@override_settings(DEFAULT_FREE_CONTESTANT_LIMIT=1)
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
            team=self.guest_team_1,
            kind=ContestUsageLedger.TASK_TEAM_STARTED,
        )

    def test_navigation_task_detail_shows_warning_when_created_guests_exceed_supported_capacity(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("navigationtask_detail", kwargs={"pk": self.navigation_task.pk}))

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Contestant capacity warning")
        self.assertContains(response, "More guest contestants have been created for this task than are guaranteed to be supported if they all take off")
