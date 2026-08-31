"""
Regression test for flight-order module finding #13 (2026-08-28 review): the flight-order zip
archive built each entry's name as f"{order.contestant}.pdf", which interpolates free-text crew
first/last names via Contestant.__str__. A crew member named e.g. "../../.." produces a
path-traversal entry in the downloaded zip (zip-slip, CWE-22).
"""

import datetime
import zipfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, Crew, EmailMapLink, NavigationTask, Person, Route, Team


class TestFlightOrderZipSlip(TestCase):
    def setUp(self):
        self.contest = Contest.objects.create(
            name="Zip Slip Contest",
            is_public=False,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="Zip Slip Task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )

        def make_contestant(number, first_name, registration):
            crew = Crew.objects.create(
                member1=Person.objects.create(first_name=first_name, last_name="B", email=f"zipslip{number}@example.com")
            )
            team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration=registration))
            contestant = Contestant.objects.create(
                team=team,
                navigation_task=self.navigation_task,
                takeoff_time=now + datetime.timedelta(hours=1),
                finished_by_time=now + datetime.timedelta(hours=2),
                tracker_start_time=now + datetime.timedelta(minutes=30),
                tracker_device_id=f"device{number}",
                contestant_number=number,
            )
            EmailMapLink.objects.create(contestant=contestant, orders=f"%PDF-{number}".encode())
            return contestant

        self.malicious_contestant = make_contestant(1, "../../../../etc/evil", "LN-ZS1")
        self.other_contestant = make_contestant(2, "Normal", "LN-ZS2")

        self.viewer = get_user_model().objects.create(email="zipslip-viewer@example.com")
        assign_perm("view_contest", self.viewer, self.contest)
        self.client.force_login(user=self.viewer)

    def test_zip_entries_contain_no_path_traversal(self):
        url = reverse("navigationtask_downloadflightorders", kwargs={"pk": self.navigation_task.pk})
        response = self.client.get(
            url, {"contestant_pks": f"{self.malicious_contestant.pk},{self.other_contestant.pk}"}
        )
        self.assertEqual(response.status_code, 200)
        zf = zipfile.ZipFile(BytesIO(response.content))
        names = zf.namelist()
        self.assertEqual(len(names), 2)
        for name in names:
            self.assertNotIn("/", name)
            self.assertNotIn("\\", name)
            self.assertNotIn("..", name)
