"""
Regression tests for a destructive-before-validating pattern found in two places (2026-08-28
review: REST API finding #13, GDL90/playback-tools finding #1) plus the root cause shared by
both: validate_gpx_file raised a bare AttributeError (not its own InvalidGpxTimeFormatException)
on a GPX point with no <time> element at all, so any caller wrapping it in a broad
`except Exception` still hit the destructive path they were trying to guard against.

- ContestantViewSet.gpx_track (viewsets.py) called contestant.reset_track_and_score() before
  checking track_file was even present, and never invoked GpxTrackSerialiser's base64 validation.
- upload_gpx_track_for_contesant (views.py, the GUI import form) called reset_track_and_score()
  before validate_gpx_file() - an invalid GPX destroyed the contestant's positions/score log and
  left only a form error, with nothing to fall back to.
"""

import base64
import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework.test import APITestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Route, Team
from playback_tools.playback import InvalidGpxTimeFormatException, validate_gpx_file
from utilities.mock_utilities import TraccarMock

GPX_TIMELESS_POINT = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test">
  <trk><trkseg>
    <trkpt lat="60.0" lon="11.0"></trkpt>
  </trkseg></trk>
</gpx>"""

GPX_NAIVE_TIME = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test">
  <trk><trkseg>
    <trkpt lat="60.0" lon="11.0"><time>2026-01-01T10:00:00</time></trkpt>
  </trkseg></trk>
</gpx>"""

GPX_VALID_TZ_AWARE = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test">
  <trk><trkseg>
    <trkpt lat="60.0" lon="11.0"><time>2026-01-01T10:00:00Z</time></trkpt>
    <trkpt lat="60.001" lon="11.001"><time>2026-01-01T10:00:05Z</time></trkpt>
  </trkseg></trk>
</gpx>"""


class TestValidateGpxFile(TestCase):
    def test_timeless_point_raises_invalid_gpx_time_exception_not_attributeerror(self):
        with self.assertRaises(InvalidGpxTimeFormatException):
            validate_gpx_file(GPX_TIMELESS_POINT)

    def test_naive_time_raises_invalid_gpx_time_exception(self):
        with self.assertRaises(InvalidGpxTimeFormatException):
            validate_gpx_file(GPX_NAIVE_TIME)


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestGpxTrackRestActionValidatesBeforeDestroying(APITestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="GPX Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="GPX Task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="A", last_name="B", email="gpx@example.com"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-GPX"))
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1,
        )
        self.manager = get_user_model().objects.create(email="manager@example.com")
        assign_perm("view_contest", self.manager, self.contest)
        assign_perm("change_contest", self.manager, self.contest)
        self.client.force_login(user=self.manager)
        self.url = reverse(
            "contestants-gpx-track",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk, "pk": self.contestant.pk},
        )

    def test_missing_track_file_does_not_reset_track(self, *args):
        track_version_before = self.contestant.track_version
        response = self.client.post(self.url, data={}, format="json")
        self.assertEqual(response.status_code, 400)
        self.contestant.refresh_from_db()
        self.assertEqual(self.contestant.track_version, track_version_before)

    def test_invalid_base64_does_not_reset_track(self, *args):
        track_version_before = self.contestant.track_version
        response = self.client.post(self.url, data={"track_file": "not valid base64!!!"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.contestant.refresh_from_db()
        self.assertEqual(self.contestant.track_version, track_version_before)

    @patch("display.viewsets.import_gpx_track")
    def test_valid_track_file_resets_track_and_dispatches_import(self, mock_import, *args):
        track_version_before = self.contestant.track_version
        encoded = base64.b64encode(GPX_NAIVE_TIME.encode("utf-8")).decode("utf-8")
        response = self.client.post(self.url, data={"track_file": encoded}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.contestant.refresh_from_db()
        self.assertEqual(self.contestant.track_version, track_version_before + 1)
        mock_import.apply_async.assert_called_once()


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestGpxUploadFormValidatesBeforeDestroying(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="GPX Form Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="GPX Form Task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="A", last_name="B", email="gpxform@example.com"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-GPXF"))
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1,
        )
        self.manager = get_user_model().objects.create(email="formmanager@example.com")
        assign_perm("view_contest", self.manager, self.contest)
        assign_perm("change_contest", self.manager, self.contest)
        self.client.force_login(user=self.manager)
        self.url = reverse("contestant_uploadgpxtrack", kwargs={"pk": self.contestant.pk})

    def test_timeless_gpx_upload_does_not_reset_track(self, *args):
        track_version_before = self.contestant.track_version
        response = self.client.post(
            self.url, data={"track_file": SimpleUploadedFile("track.gpx", GPX_TIMELESS_POINT.encode("utf-8"))}
        )
        self.assertEqual(response.status_code, 200)
        self.contestant.refresh_from_db()
        self.assertEqual(self.contestant.track_version, track_version_before)

    @patch("display.views.import_gpx_track")
    def test_valid_gpx_upload_resets_track_and_dispatches_import(self, mock_import, *args):
        track_version_before = self.contestant.track_version
        response = self.client.post(
            self.url, data={"track_file": SimpleUploadedFile("track.gpx", GPX_VALID_TZ_AWARE.encode("utf-8"))}
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.contestant.refresh_from_db()
        self.assertEqual(self.contestant.track_version, track_version_before + 1)
        mock_import.apply_async.assert_called_once()
