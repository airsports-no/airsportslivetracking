"""A route has one photo of a name. The photos are made when they are first asked for, which takes long, so two requests at
once used to make two of each: the next request then failed for good ("returned more than one Photo"), and with it the
photos of the live map."""

import datetime
import importlib
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from guardian.shortcuts import assign_perm
from rest_framework.test import APIClient

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, EditableRoute, NavigationTask, Photo
from display.services.photo_management import sync_navigation_task_photo_targets
from display.utilities.route_building_utilities import create_precision_route_from_gpx

UTC = datetime.timezone.utc


def make_task(name="Photo Cup") -> NavigationTask:
    with open(os.path.join(os.path.dirname(__file__), "demo_contests", "2017_WPFC", "Route-1-Blue.gpx"), "r") as file:
        route = create_precision_route_from_gpx(file, True)
    now = datetime.datetime.now(UTC)
    contest = Contest.objects.create(name=name, start_time=now, finish_time=now, is_public=True)
    return NavigationTask.create(
        name="Photo day",
        original_scorecard=get_default_scorecard(),
        start_time=now,
        finish_time=now + datetime.timedelta(hours=8),
        route=route,
        contest=contest,
        is_public=True,
    )


class PhotoUniquePerRouteTest(TestCase):
    def setUp(self):
        # The pictures are satellite images fetched over the network
        patcher = patch.object(Photo, "generate_image", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.task = make_task()

    def test_the_database_refuses_a_second_photo_of_a_name_on_a_route(self):
        Photo.objects.create(name="Obs 1", route=self.task.route, latitude=60, longitude=11)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Photo.objects.create(name="Obs 1", route=self.task.route, latitude=61, longitude=12)
        # Another route may have a photo of the same name
        other = make_task("Other Cup")
        Photo.objects.create(name="Obs 1", route=other.route, latitude=60, longitude=11)

    def test_asking_for_the_photos_again_makes_no_more_of_them(self):
        first = sync_navigation_task_photo_targets(self.task)
        second = sync_navigation_task_photo_targets(self.task)
        self.assertGreater(len(first), 0)
        self.assertEqual([photo.pk for photo in first], [photo.pk for photo in second])
        self.assertEqual(Photo.objects.filter(route=self.task.route).count(), len(first))

    def test_a_request_that_loses_the_race_for_a_photo_gets_the_one_the_other_made(self):
        # The other request makes the photo after this one has looked for it and before it makes it
        existing = Photo.objects.create(name="SP", route=self.task.route, latitude=60, longitude=11)
        real_get = Photo.objects.get
        lookups = []

        def get(*args, **kwargs):
            lookups.append(kwargs)
            if len(lookups) == 1:
                raise Photo.DoesNotExist()
            return real_get(*args, **kwargs)

        with patch.object(Photo.objects, "get", side_effect=get):
            photos = sync_navigation_task_photo_targets(self.task)
        self.assertIn(existing.pk, [photo.pk for photo in photos])
        self.assertEqual(Photo.objects.filter(route=self.task.route, name="SP").count(), 1)

    def test_two_markers_of_one_name_on_a_route_are_one_photo(self):
        editable_route = EditableRoute.objects.create(
            name="Markers",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"id": f"obs-{n}", "name": "Obs 1", "featureType": "observation_photo"},
                        "geometry": {"type": "Point", "coordinates": [11.0 + n / 100, 60.0]},
                    }
                    for n in range(2)
                ],
            },
        )
        route = make_task("Marker Cup").route
        editable_route.amend_route_with_additional_features(route)
        self.assertEqual(Photo.objects.filter(route=route, name="Obs 1").count(), 1)

    def test_the_photos_endpoint_answers_every_time(self):
        manager = get_user_model().objects.create(email="manager@example.com")
        assign_perm("change_contest", manager, self.task.contest)
        assign_perm("view_contest", manager, self.task.contest)
        client = APIClient()
        client.force_authenticate(manager)
        url = f"/api/v1/contests/{self.task.contest_id}/navigationtasks/{self.task.pk}/photos/"
        first = client.get(url)
        second = client.get(url)
        self.assertEqual((first.status_code, second.status_code), (200, 200), second.content)
        self.assertEqual(len(first.json()), len(second.json()))
        self.assertGreater(len(first.json()), 0)


class MergeDuplicatePhotosTest(TestCase):
    """Which copy of a photo stays when the migration merges duplicates (see 0216_photo_unique_name_per_route)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migration = importlib.import_module("display.migrations.0216_photo_unique_name_per_route")

    def photo(self, pk, file=None, uploaded=False, is_decoy=False):
        return SimpleNamespace(pk=pk, file=file, uploaded=uploaded, is_decoy=is_decoy)

    def keep(self, *photos):
        return self.migration.choose_photo_to_keep(list(photos)).pk

    def test_the_oldest_stays_when_the_copies_are_alike(self):
        self.assertEqual(self.keep(self.photo(7), self.photo(3), self.photo(5)), 3)

    def test_one_with_a_picture_before_one_without(self):
        self.assertEqual(self.keep(self.photo(1), self.photo(2, file="a.png")), 2)

    def test_the_organisers_own_upload_before_a_generated_picture(self):
        self.assertEqual(self.keep(self.photo(1, file="gen.png"), self.photo(2, file="own.png", uploaded=True)), 2)

    def test_a_real_photo_before_a_decoy(self):
        self.assertEqual(self.keep(self.photo(1, file="a.png", uploaded=True, is_decoy=True), self.photo(2)), 2)
