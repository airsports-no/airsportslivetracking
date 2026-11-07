"""A route has one photo of a name. The photos are made when they are first asked for, which takes long, so two requests at
once used to make two of each: the next request then failed for good ("returned more than one Photo"), and with it the
photos of the live map."""

import datetime
import importlib
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from guardian.shortcuts import assign_perm
from rest_framework.test import APIClient

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, EditableRoute, NavigationTask, Photo
from display.serialisers import EditableRouteSerialiser
from display.services.photo_management import observation_photo_name_problems, sync_navigation_task_photo_targets
from rest_framework.exceptions import ValidationError as DRFValidationError
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


def observation(name, n=0):
    return {
        "type": "Feature",
        "properties": {"id": f"obs-{name}-{n}", "name": name, "featureType": "observation_photo"},
        "geometry": {"type": "Point", "coordinates": [11.0 + n / 100, 60.0]},
    }


def waypoint(name, point_type="tp", sequence=1):
    return {
        "type": "Feature",
        "properties": {
            "id": f"wp-{name}",
            "name": name,
            "featureType": "route_waypoint",
            "pointType": point_type,
            "sequence": sequence,
            "width": 1852,
        },
        "geometry": {"type": "Point", "coordinates": [11.0, 60.1]},
    }


def editable(*features) -> EditableRoute:
    return EditableRoute(name="Names", route={"type": "FeatureCollection", "features": list(features)})


class ObservationPhotoNamesTest(TestCase):
    """A photo is its name, so the observation photos of a route cannot share one, or have the name of a point with a photo."""

    def test_names_of_their_own_are_fine(self):
        route = editable(observation("Obs 1"), observation("Obs 2", 1), waypoint("TP 1"))
        self.assertEqual(observation_photo_name_problems(route), [])

    def test_two_observation_photos_of_one_name(self):
        route = editable(observation("Obs 3"), observation("Obs 3", 1), observation("Obs 4", 2))
        self.assertEqual(
            observation_photo_name_problems(route),
            ['More than one observation photo is named "Obs 3". Give each its own name.'],
        )

    def test_an_observation_photo_named_like_a_point_that_has_a_photo(self):
        route = editable(waypoint("TP 1"), observation("TP 1"))
        self.assertEqual(
            observation_photo_name_problems(route),
            ['An observation photo is named "TP 1", like a point of the route. Give the photo another name.'],
        )

    def test_a_point_without_a_photo_does_not_count(self):
        # The hidden gates have no picture, so the name is free
        route = editable(waypoint("Secret 1", "secret"), observation("Secret 1"))
        self.assertEqual(observation_photo_name_problems(route), [])

    def test_a_route_is_not_saved_with_such_names(self):
        serialiser = EditableRouteSerialiser()
        good = {"type": "FeatureCollection", "features": [observation("Obs 1"), observation("Obs 2", 1)]}
        self.assertEqual(serialiser.validate_route(good), good)
        bad = {"type": "FeatureCollection", "features": [observation("Obs 1"), observation("Obs 1", 1)]}
        with self.assertRaises(DRFValidationError) as caught:
            serialiser.validate_route(bad)
        self.assertIn('named "Obs 1"', str(caught.exception.detail))

    def test_no_task_is_made_from_such_a_route(self):
        route = editable(observation("Obs 1"), observation("Obs 1", 1))
        with self.assertRaisesMessage(DjangoValidationError, 'named "Obs 1"'):
            route.create_route("precision", get_default_scorecard(), False, 0.5)

    def test_such_a_route_is_not_loaded_into_a_task_either(self):
        task = make_task("Reload Cup")
        task.editable_route = EditableRoute.objects.create(
            name="Clash",
            route={"type": "FeatureCollection", "features": [observation("Obs 1"), observation("Obs 1", 1)]},
        )
        task.save(update_fields=["editable_route"])
        old_route = task.route
        with self.assertRaisesMessage(DjangoValidationError, 'named "Obs 1"'):
            task.refresh_editable_route()
        task.refresh_from_db()
        self.assertEqual(task.route_id, old_route.pk)


class MovedPhotoPictureTest(TestCase):
    """A photo that has moved (its marker was moved, or two photos of one name were merged) must not keep a picture of the old place."""

    def setUp(self):
        self.task = make_task("Moved Cup")
        self.sp = self.task.route.waypoints[0]
        self.generated = []

        def generate_image(photo, force=False):
            # A new satellite picture, as the real one is saved
            self.generated.append((photo.name, force))
            photo.file.save(f"new_{len(self.generated)}.png", ContentFile(b"new picture"), save=True)
            return True

        patcher = patch.object(Photo, "generate_image", generate_image)
        patcher.start()
        self.addCleanup(patcher.stop)

    def photo_of_sp(self, latitude=None, longitude=None, uploaded=False) -> Photo:
        """The photo of the starting point, with a picture, at the given place (the waypoint's own by default)."""
        photo = Photo.objects.create(
            name=self.sp.name,
            route=self.task.route,
            latitude=self.sp.latitude if latitude is None else latitude,
            longitude=self.sp.longitude if longitude is None else longitude,
            uploaded=uploaded,
        )
        photo.file.save("old.png", ContentFile(b"old picture"), save=True)
        self.generated.clear()
        return photo

    def sync_sp(self) -> Photo:
        sync_navigation_task_photo_targets(self.task)
        return Photo.objects.get(route=self.task.route, name=self.sp.name)

    def pictures_made_for_sp(self) -> list:
        """The sync also makes the photos of the route's other points, which are new: only the starting point's matter here."""
        return [made for made in self.generated if made[0] == self.sp.name]

    def test_a_photo_that_has_moved_gets_a_new_picture_and_the_old_file_goes(self):
        photo = self.photo_of_sp(latitude=self.sp.latitude + 0.01)
        old_name = photo.file.name
        photo = self.sync_sp()
        self.assertEqual(photo.latitude, self.sp.latitude)
        self.assertEqual(self.pictures_made_for_sp(), [(self.sp.name, True)])
        self.assertEqual(photo.file.read(), b"new picture")
        self.assertFalse(photo.file.storage.exists(old_name))

    def test_a_photo_that_has_not_moved_keeps_its_picture(self):
        self.photo_of_sp()
        photo = self.sync_sp()
        self.assertEqual(self.pictures_made_for_sp(), [])
        self.assertEqual(photo.file.read(), b"old picture")

    def test_a_move_of_less_than_a_metre_is_the_same_place(self):
        self.photo_of_sp(latitude=self.sp.latitude + 5e-6)
        photo = self.sync_sp()
        self.assertEqual(photo.latitude, self.sp.latitude)
        self.assertEqual(self.pictures_made_for_sp(), [])
        self.assertEqual(photo.file.read(), b"old picture")

    def test_the_organisers_own_picture_stays_when_the_photo_moves(self):
        self.photo_of_sp(latitude=self.sp.latitude + 0.01, uploaded=True)
        photo = self.sync_sp()
        self.assertEqual(photo.latitude, self.sp.latitude)
        self.assertEqual(self.pictures_made_for_sp(), [])
        self.assertEqual(photo.file.read(), b"old picture")

    def test_a_picture_that_cannot_be_made_is_removed_and_made_at_the_next_request(self):
        photo = self.photo_of_sp(longitude=self.sp.longitude + 0.01)
        old_name = photo.file.name
        with patch.object(Photo, "generate_image", return_value=False):
            photo = self.sync_sp()
        # No picture of the wrong place
        self.assertFalse(photo.file)
        self.assertFalse(photo.file.storage.exists(old_name))
        photo = self.sync_sp()
        self.assertEqual(photo.file.read(), b"new picture")
