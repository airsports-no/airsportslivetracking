"""
Regression test for REST API finding #6 (2026-08-28 review): create_with_team/update_with_team
called super().create()/super().update() directly, bypassing this class's own overridden
create()/update() (the ones that actually run _assert_can_reserve_task_slot), letting a contest
at its pilot limit add unlimited contestants through these two @action wrappers. Also covers the
related gap noted in the same finding: assert_can_register_team was imported in serialisers.py
but never called, so ContestViewSet.signup had no team-registration capacity check at all.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, ContestTeam, Contestant, EditableRoute, MyUser, Person, Team, Crew, Aeroplane
from utilities.mock_utilities import TraccarMock

EDITABLE_ROUTE_DATA = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"featureType": "route_path"},
            "geometry": {"type": "LineString", "coordinates": [[11, 60], [11.1, 60.1]]},
        },
        {
            "type": "Feature",
            "properties": {
                "id": "6900ce4c-11df-4edf-9a4f-770a57b00092",
                "name": "SP",
                "pointType": "sp",
                "featureType": "route_waypoint",
                "width": 1852,
                "isTiming": True,
                "isPassing": True,
                "sequence": 0,
            },
            "geometry": {"type": "Point", "coordinates": [11, 60]},
        },
        {
            "type": "Feature",
            "properties": {
                "id": "9d525739-b2db-424a-99b8-7c83d20a3e85",
                "name": "FP",
                "pointType": "fp",
                "featureType": "route_waypoint",
                "width": 1852,
                "isTiming": True,
                "isPassing": True,
                "sequence": 1,
            },
            "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
        },
    ],
}

NAVIGATION_TASK_DATA = lambda editable_route: {
    "name": "Task",
    "start_time": datetime.datetime.now(datetime.timezone.utc),
    "finish_time": datetime.datetime.now(datetime.timezone.utc),
    "original_scorecard": "FAI Precision",
    "editable_route": editable_route,
}

CONTESTANT_DATA = {
    "team": {
        "aeroplane": {"registration": "LN-CAP1"},
        "crew": {"member1": {"first_name": "Guest", "last_name": "Pilot", "email": "guest-pilot@example.com"}},
        "country": "NO",
    },
    "gate_times": {},
    "takeoff_time": datetime.datetime.now(datetime.timezone.utc),
    "minutes_to_starting_point": 5,
    "finished_by_time": datetime.datetime.now(datetime.timezone.utc),
    "air_speed": 70,
    "contestant_number": 1,
    "tracker_device_id": "tracker",
    "tracker_start_time": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
    "wind_speed": 10,
    "wind_direction": 0,
}


@override_settings(ACCESS_ENFORCEMENT_MODE="enforce", DEFAULT_FREE_CONTESTANT_LIMIT=0)
@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestCreateWithTeamCapacityEnforcement(APITestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.owner = get_user_model().objects.create(email="owner@example.com")
        self.owner.user_permissions.add(Permission.objects.get(codename="add_contest"))
        self.client.force_login(user=self.owner)
        result = self.client.post(
            reverse("contests-list"),
            data={
                "name": "Capacity Contest",
                "is_public": False,
                "start_time": datetime.datetime.now(datetime.timezone.utc),
                "time_zone": "Europe/Oslo",
                "finish_time": datetime.datetime.now(datetime.timezone.utc),
                "location": "60, 11",
            },
        )
        self.contest_id = result.json()["id"]
        self.contest = Contest.objects.get(pk=self.contest_id)
        editable_route = EditableRoute.objects.create(name="test", route=EDITABLE_ROUTE_DATA)
        from guardian.shortcuts import assign_perm

        assign_perm("display.view_editableroute", self.owner, editable_route)
        assign_perm("display.change_editableroute", self.owner, editable_route)
        result = self.client.post(
            reverse("navigationtasks-list", kwargs={"contest_pk": self.contest_id}),
            data=NAVIGATION_TASK_DATA(editable_route.pk),
            format="json",
        )
        self.navigation_task_id = result.json()["id"]

    def test_create_with_team_is_rejected_at_zero_capacity(self, *args):
        # DEFAULT_FREE_CONTESTANT_LIMIT=0 and no token/grant assigned - the contest
        # resolves to a free tier with zero guest capacity, so any non-owner
        # contestant creation should be rejected.
        result = self.client.post(
            reverse(
                "contestants-create-with-team",
                kwargs={"contest_pk": self.contest_id, "navigationtask_pk": self.navigation_task_id},
            ),
            data=CONTESTANT_DATA,
            format="json",
        )
        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST, result.content)
        self.assertFalse(Contestant.objects.filter(team__crew__member1__email="guest-pilot@example.com").exists())


@override_settings(ACCESS_ENFORCEMENT_MODE="enforce", DEFAULT_FREE_CONTESTANT_LIMIT=0)
class TestSignupCapacityEnforcement(APITestCase):
    def setUp(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(
            name="Signup Capacity Contest",
            is_public=True,
            is_featured=True,
            start_time=now,
            finish_time=now + datetime.timedelta(hours=1),
            location="60.0,11.0",
        )
        self.person = Person.objects.create(first_name="Signup", last_name="Pilot", email="signup-pilot@example.com")
        self.user = MyUser.objects.create(email=self.person.email)
        self.client.force_login(user=self.user)

    def test_signup_is_rejected_at_zero_capacity(self):
        url = reverse("contests-signup", kwargs={"pk": self.contest.pk})
        response = self.client.post(
            url,
            data={"aircraft_registration": "LN-SIGNUP", "club_name": "Test Club", "airspeed": 70, "copilot_id": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertFalse(ContestTeam.objects.filter(contest=self.contest).exists())
