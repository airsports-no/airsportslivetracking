"""
Pilots edit their contest registration in place (PUT contests-signup) instead of withdrawing and
re-registering, which fails once they have a future flight. The update path must only ever touch
the caller's own registration in this contest.
"""

import datetime

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Contest, ContestTeam, MyUser, Person


class TestSignupUpdateRegistration(APITestCase):
    def setUp(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(
            name="Update Registration Contest",
            is_public=True,
            is_featured=True,
            start_time=now,
            finish_time=now + datetime.timedelta(hours=1),
            location="60.0,11.0",
        )
        self.url = reverse("contests-signup", kwargs={"pk": self.contest.pk})
        self.person = Person.objects.create(first_name="Anna", last_name="Pilot", email="anna@example.com")
        self.user = MyUser.objects.create(email=self.person.email)
        self.other_person = Person.objects.create(first_name="Bo", last_name="Other", email="bo@example.com")
        self.other_user = MyUser.objects.create(email=self.other_person.email)

    def _register(self, user, registration, airspeed=70):
        self.client.force_login(user=user)
        response = self.client.post(
            self.url,
            data={"aircraft_registration": registration, "club_name": "Club", "airspeed": airspeed, "copilot_id": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        return response.json()["id"]

    def test_pilot_can_change_aircraft_in_place(self):
        contest_team_id = self._register(self.user, "LN-AAA")
        response = self.client.put(
            self.url,
            data={
                "contest_team": contest_team_id,
                "aircraft_registration": "LN-BBB",
                "club_name": "Club",
                "airspeed": 80,
                "copilot_id": None,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        contest_teams = ContestTeam.objects.filter(contest=self.contest)
        self.assertEqual(contest_teams.count(), 1)
        self.assertEqual(contest_teams.get().team.aeroplane.registration, "LN-BBB")
        self.assertEqual(contest_teams.get().air_speed, 80)

    def test_cannot_update_someone_elses_registration(self):
        other_id = self._register(self.other_user, "LN-OTH")
        self.client.force_login(user=self.user)
        response = self.client.put(
            self.url,
            data={
                "contest_team": other_id,
                "aircraft_registration": "LN-HIJ",
                "club_name": "Club",
                "airspeed": 70,
                "copilot_id": None,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertEqual(ContestTeam.objects.get(pk=other_id).team.aeroplane.registration, "LN-OTH")

    def test_update_requires_contest_team(self):
        self._register(self.user, "LN-AAA")
        response = self.client.put(
            self.url,
            data={"aircraft_registration": "LN-BBB", "club_name": "Club", "airspeed": 70, "copilot_id": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
