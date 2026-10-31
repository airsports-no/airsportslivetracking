import datetime
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    ContestantTrack,
    Crew,
    FlightSummary,
    MyUser,
    NavigationTask,
    Person,
    Route,
    Team,
)
from display.utilities.tracking_definitions import TRACKING_PILOT
from utilities.mock_utilities import TraccarMock

UTC = datetime.timezone.utc
URL = "/api/v1/admin/user-flights/"


class AdminUserFlightsTest(TestCase):
    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        now = datetime.datetime.now(UTC)
        self.person = Person.objects.create(first_name="Ada", last_name="Pilot", email="ada@example.com")
        MyUser.objects.create(username="ada", email="ada@example.com")
        other = Person.objects.create(first_name="Bo", last_name="Other", email="bo@example.com")
        aeroplane = Aeroplane.objects.create(registration="LN-ADA")
        self.flights = []
        # A public contest flown as pilot yesterday, and a private one as co-pilot today
        for name, is_public, crew, days_ago in (
            ("Open Cup", True, Crew.objects.create(member1=self.person, member2=other), 1),
            ("Secret Cup", False, Crew.objects.create(member1=other, member2=self.person), 0),
        ):
            start = now - datetime.timedelta(days=days_ago)
            contest = Contest.objects.create(name=name, start_time=start, finish_time=start, is_public=is_public)
            task = NavigationTask.create(
                name=f"{name} day",
                original_scorecard=get_default_scorecard(),
                start_time=start - datetime.timedelta(hours=6),
                finish_time=start + datetime.timedelta(hours=6),
                route=Route.objects.create(name="Route"),
                contest=contest,
                is_public=is_public,
            )
            contestant = Contestant.objects.create(
                team=Team.objects.create(crew=crew, aeroplane=aeroplane),
                navigation_task=task,
                tracking_device=TRACKING_PILOT,
                contestant_number=7,
                tracker_start_time=start - datetime.timedelta(hours=2),
                takeoff_time=start - datetime.timedelta(hours=1),
                finished_by_time=start,
            )
            ContestantTrack.objects.update_or_create(
                contestant=contestant, defaults={"calculator_started": True, "calculator_finished": True, "score": 42}
            )
            self.flights.append(contestant)
        # Someone else's flight is not listed
        Contestant.objects.create(
            team=Team.objects.create(crew=Crew.objects.create(member1=other), aeroplane=aeroplane),
            navigation_task=self.flights[0].navigation_task,
            tracking_device=TRACKING_PILOT,
            contestant_number=8,
            tracker_start_time=now,
            takeoff_time=now,
            finished_by_time=now,
        )
        self.admin = MyUser.objects.create(username="admin", email="admin@example.com", is_superuser=True)
        self.client = APIClient()

    def get(self, user, person_id):
        self.client.force_authenticate(user)
        return self.client.get(URL, {"person": person_id})

    def test_every_flight_as_pilot_or_co_pilot_newest_first_whatever_the_contest(self):
        data = self.get(self.admin, self.person.pk).json()
        self.assertEqual(
            data["person"], {"id": self.person.pk, "name": "Ada Pilot", "email": "ada@example.com", "has_account": True}
        )
        self.assertEqual(
            [(f["contest_name"], f["role"], f["partner"]) for f in data["flights"]],
            [("Secret Cup", "co-pilot", "Bo Other"), ("Open Cup", "pilot", "Bo Other")],
        )
        flight = data["flights"][0]
        self.assertEqual(flight["aeroplane"], "LN-ADA")
        self.assertEqual(flight["score"], 42)
        self.assertTrue(flight["calculator_finished"])

    def test_a_flight_not_scored_yet_has_no_score(self):
        # The track holds the scorecard's initial score until scoring starts
        ContestantTrack.objects.filter(contestant=self.flights[1]).update(calculator_started=False)
        flights = {f["id"]: f for f in self.get(self.admin, self.person.pk).json()["flights"]}
        self.assertIsNone(flights[self.flights[1].pk]["score"])
        self.assertEqual(flights[self.flights[0].pk]["score"], 42)

    def test_the_ai_summaries_of_the_current_scores_are_listed(self):
        flight = self.flights[0]
        for style, track_version in (("pundit", flight.track_version), ("comedy", flight.track_version - 1)):
            FlightSummary.objects.create(
                contestant=flight,
                track_version=track_version,
                score_version=flight.score_version,
                prompt_version=1,
                style=style,
                status=FlightSummary.STATUS_DONE,
                requested_at=datetime.datetime.now(UTC),
            )
        flights = {f["id"]: f for f in self.get(self.admin, self.person.pk).json()["flights"]}
        # The comedy one is of scores since replaced
        self.assertEqual(flights[flight.pk]["summary_styles"], ["pundit"])
        self.assertEqual(flights[self.flights[1].pk]["summary_styles"], [])

    def test_only_superusers(self):
        ada = MyUser.objects.get(username="ada")
        self.assertEqual(self.get(ada, self.person.pk).status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(URL, {"person": self.person.pk}).status_code, (401, 403))

    def test_a_missing_or_unknown_person(self):
        self.assertEqual(self.get(self.admin, "").status_code, 400)
        self.assertEqual(self.get(self.admin, 999999).status_code, 404)
