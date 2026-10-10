"""
Pilots edit their contest registration in place (PUT contests-signup) instead of withdrawing and
re-registering, which fails once they have a future flight. The update path must only ever touch
the caller's own registration in this contest.
"""

import datetime
from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Contest, ContestTeam, MyUser, Person
from display.utilities.tracking_definitions import TRACKING_COPILOT, TRACKING_PILOT_AND_COPILOT


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

    def test_failure_while_moving_the_team_rolls_the_whole_update_back(self):
        # replace_team deletes the registration and then re-points contestants and scores. If a later
        # step fails the pilot must keep their original registration, not end up with none.
        contest_team_id = self._register(self.user, "LN-AAA")
        exploding_scores = MagicMock()
        exploding_scores.objects.filter.return_value.update.side_effect = RuntimeError("boom")
        self.client.raise_request_exception = False
        with patch("display.models.TeamTestScore", exploding_scores):
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
        self.assertEqual(response.status_code, 500)
        contest_team = ContestTeam.objects.get(contest=self.contest)
        self.assertEqual(contest_team.pk, contest_team_id)
        self.assertEqual(contest_team.team.aeroplane.registration, "LN-AAA")

    def test_removing_the_copilot_resets_copilot_only_tracking(self):
        # A registration tracking only the co-pilot's phone is invalid once the co-pilot is gone
        # (ContestTeam.clean rejects it and get_tracker_id would dereference a missing member2).
        copilot = Person.objects.create(first_name="Co", last_name="Pilot", email="copilot@example.com")
        self.client.force_login(user=self.user)
        response = self.client.post(
            self.url,
            data={"aircraft_registration": "LN-AAA", "club_name": "Club", "airspeed": 70, "copilot_id": copilot.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        contest_team = ContestTeam.objects.get(contest=self.contest)
        contest_team.tracking_device = TRACKING_COPILOT
        contest_team.save()

        response = self.client.put(
            self.url,
            data={
                "contest_team": contest_team.pk,
                "aircraft_registration": "LN-AAA",
                "club_name": "Club",
                "airspeed": 70,
                "copilot_id": None,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        updated = ContestTeam.objects.get(contest=self.contest)
        self.assertIsNone(updated.team.crew.member2)
        self.assertEqual(updated.tracking_device, TRACKING_PILOT_AND_COPILOT)
        updated.clean()  # no longer an invalid combination
