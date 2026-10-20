"""GitHub #23: duplicate a navigation task with a new name, route and time window, into the same or another contest."""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, Crew, EditableRoute, NavigationTask, Person, Team
from display.utilities.tracking_definitions import TRACKING_PILOT
from utilities.mock_utilities import TraccarMock

START = datetime.datetime(2026, 4, 1, 9, 0, tzinfo=datetime.timezone.utc)
FINISH = datetime.datetime(2026, 4, 1, 17, 0, tzinfo=datetime.timezone.utc)


def make_contest(name):
    return Contest.objects.create(
        name=name, time_zone="Europe/Oslo", start_time=START, finish_time=FINISH, location="60.0,11.0"
    )


def make_route(user, name):
    with open("display/tests/NM.csv", "r") as file:
        editable_route, _ = EditableRoute.create_from_csv(name, file.readlines()[1:])
    for permission in ("view_editableroute", "change_editableroute", "delete_editableroute"):
        assign_perm(permission, user, editable_route)
    return editable_route


def manage(user, contest):
    for permission in ("view_contest", "change_contest"):
        assign_perm(permission, user, contest)


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestTaskDuplication(APITestCase):
    def setUp(self):
        create_scorecards()
        self.user = get_user_model().objects.create(email="organiser@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="add_contest"))
        self.client.force_login(self.user)
        self.contest = make_contest("Cup round 1")
        self.contest.make_public()
        manage(self.user, self.contest)
        self.source_route = make_route(self.user, "Round 1 route")
        self.new_route = make_route(self.user, "Round 2 route")
        scorecard = get_default_scorecard()
        self.source = NavigationTask.create(
            name="Precision",
            original_scorecard=scorecard,
            contest=self.contest,
            route=self.source_route.create_precision_route(True, scorecard),
            editable_route=self.source_route,
            start_time=START,
            finish_time=FINISH,
            wind_speed=12,
            wind_direction=270,
            minutes_to_starting_point=9,
            allow_self_management=True,
            calculation_delay_minutes=15,
            notify_managers_on_finish=True,
            is_public=True,
        )
        # Changes the organiser has made to the task's own scorecard and flight order configuration
        self.source.scorecard.initial_score = 42
        self.source.scorecard.save()
        self.source.flightorderconfiguration.map_zoom_level = 14
        self.source.flightorderconfiguration.map_dpi = 250
        self.source.flightorderconfiguration.save()
        self.url = f"/api/v1/contests/{self.contest.pk}/navigationtasks/{self.source.pk}/"

    def duplicate(self, **fields):
        body = {"contest": self.contest.pk, "name": "Precision round 2", "editable_route": self.new_route.pk, **fields}
        return self.client.post(f"{self.url}duplicate/", body, format="json")

    def test_the_copy_has_its_own_name_route_and_times_and_the_settings_of_the_original(self, *_):
        start = START + datetime.timedelta(days=7)
        result = self.duplicate(
            start_time=start.isoformat(), finish_time=(start + datetime.timedelta(hours=6)).isoformat()
        )
        self.assertEqual(result.status_code, status.HTTP_201_CREATED, result.content)
        copy = NavigationTask.objects.get(pk=result.json()["id"])
        self.assertEqual(copy.name, "Precision round 2")
        self.assertEqual(copy.editable_route, self.new_route)
        self.assertNotEqual(copy.route_id, self.source.route_id)
        self.assertEqual((copy.start_time, copy.finish_time), (start, start + datetime.timedelta(hours=6)))
        for field in (
            "wind_speed",
            "wind_direction",
            "minutes_to_starting_point",
            "allow_self_management",
            "calculation_delay_minutes",
            "notify_managers_on_finish",
            "original_scorecard_id",
            "task_subtype",
        ):
            self.assertEqual(getattr(copy, field), getattr(self.source, field), field)
        self.assertFalse(copy.is_public, "a copy starts private")
        self.assertEqual(copy.contestant_set.count(), 0)

    def test_the_copy_keeps_the_scorecard_changes_in_a_scorecard_of_its_own(self, *_):
        copy = NavigationTask.objects.get(pk=self.duplicate().json()["id"])
        self.assertNotEqual(copy.scorecard_id, self.source.scorecard_id)
        self.assertEqual(copy.scorecard.initial_score, 42)
        self.assertEqual(copy.scorecard.config, self.source.scorecard.config)
        self.assertFalse(copy.scorecard.original)
        copy.scorecard.initial_score = 7
        copy.scorecard.save()
        self.source.scorecard.refresh_from_db()
        self.assertEqual(self.source.scorecard.initial_score, 42, "changing the copy leaves the original alone")

    def test_the_copy_keeps_the_flight_order_configuration(self, *_):
        copy = NavigationTask.objects.get(pk=self.duplicate().json()["id"])
        self.assertEqual(copy.flightorderconfiguration.map_zoom_level, 14)
        self.assertEqual(copy.flightorderconfiguration.map_dpi, 250)
        self.assertNotEqual(copy.flightorderconfiguration.pk, self.source.flightorderconfiguration.pk)

    def test_the_time_window_defaults_to_that_of_the_original(self, *_):
        copy = NavigationTask.objects.get(pk=self.duplicate().json()["id"])
        self.assertEqual((copy.start_time, copy.finish_time), (START, FINISH))

    def test_contestants_are_not_copied(self, *_):
        person = Person.objects.create(first_name="Pi", last_name="Lot", email="pilot@example.com")
        team = Team.objects.create(
            crew=Crew.objects.create(member1=person), aeroplane=Aeroplane.objects.create(registration="LN-X")
        )
        Contestant.objects.create(
            team=team,
            navigation_task=self.source,
            tracking_device=TRACKING_PILOT,
            contestant_number=1,
            tracker_start_time=START,
            takeoff_time=START,
            finished_by_time=FINISH,
        )
        copy = NavigationTask.objects.get(pk=self.duplicate().json()["id"])
        self.assertEqual(copy.contestant_set.count(), 0)

    def test_the_copy_can_go_into_another_contest_the_user_manages(self, *_):
        other = make_contest("Cup round 2")
        manage(self.user, other)
        result = self.duplicate(contest=other.pk, name="Precision")
        self.assertEqual(result.status_code, status.HTTP_201_CREATED, result.content)
        self.assertEqual(NavigationTask.objects.get(pk=result.json()["id"]).contest, other)

    def test_change_permission_on_both_contests_is_needed(self, *_):
        viewed_only = make_contest("Somebody else's")
        assign_perm("view_contest", self.user, viewed_only)
        self.assertEqual(self.duplicate(contest=viewed_only.pk).status_code, status.HTTP_403_FORBIDDEN)
        # Only viewing the source contest is not enough either, even into a contest the user manages
        mine = make_contest("Mine")
        manage(self.user, mine)
        viewer = get_user_model().objects.create(email="viewer@example.com")
        assign_perm("view_contest", viewer, self.contest)
        manage(viewer, mine)
        self.client.force_login(viewer)
        self.assertEqual(self.duplicate(contest=mine.pk).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(NavigationTask.objects.count(), 1)

    def test_a_name_already_used_in_the_contest_is_refused(self, *_):
        result = self.duplicate(name="Precision")
        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", result.json())

    def test_a_route_that_does_not_fit_the_task_type_is_refused(self, *_):
        unfit = EditableRoute.objects.create(
            name="Just a line",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]},
                    },
                ],
            },
        )
        assign_perm("change_editableroute", self.user, unfit)
        result = self.duplicate(editable_route=unfit.pk)
        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST, result.content)
        self.assertIn("editable_route", result.json())

    def test_somebody_elses_route_cannot_be_used(self, *_):
        stranger = get_user_model().objects.create(email="stranger@example.com")
        theirs = make_route(stranger, "Their route")
        self.assertEqual(self.duplicate(editable_route=theirs.pk).status_code, status.HTTP_403_FORBIDDEN)

    def test_a_co_manager_may_reuse_the_route_of_the_original_without_edit_rights_on_it(self, *_):
        co_manager = get_user_model().objects.create(email="co-manager@example.com")
        manage(co_manager, self.contest)
        self.client.force_login(co_manager)
        result = self.duplicate(editable_route=self.source_route.pk)
        self.assertEqual(result.status_code, status.HTTP_201_CREATED, result.content)
        # Any other route of somebody else's is still refused
        self.assertEqual(
            self.duplicate(name="Precision round 3", editable_route=self.new_route.pk).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_the_finish_must_come_after_the_start(self, *_):
        result = self.duplicate(start_time=FINISH.isoformat(), finish_time=START.isoformat())
        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST)

    def test_the_options_list_the_managed_contests_and_mark_the_routes_that_fit(self, *_):
        EditableRoute.objects.create(name="Just a line", route={"type": "FeatureCollection", "features": []})
        unfit = EditableRoute.objects.get(name="Just a line")
        assign_perm("change_editableroute", self.user, unfit)
        make_contest("Not mine")
        options = self.client.get(f"{self.url}duplicate_options/").json()
        self.assertEqual(options["name"], "Precision (copy)")
        self.assertEqual(options["contest"], self.contest.pk)
        self.assertEqual([contest["name"] for contest in options["contests"]], ["Cup round 1"])
        routes = {route["name"]: route for route in options["routes"]}
        self.assertTrue(routes["Round 2 route"]["compatible"])
        self.assertFalse(routes["Just a line"]["compatible"])
        self.assertTrue(routes["Just a line"]["reasons"])

    def test_the_options_are_for_the_managers_only(self, *_):
        viewer = get_user_model().objects.create(email="viewer@example.com")
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(f"{self.url}duplicate_options/").status_code, status.HTTP_403_FORBIDDEN)
