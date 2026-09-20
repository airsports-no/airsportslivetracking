"""
Tests for NavigationTaskViewSet's remove_contestants/batch_update_contestants/
refresh_editable_route REST actions and ContestantViewSet.destroy's permission fix - all part of
migrating navigationtask_detail.html to the React SPA (Slice 0).
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework.test import APITestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    Contest,
    ContestTeam,
    Contestant,
    Crew,
    EditableRoute,
    NavigationTask,
    Person,
    Route,
    Team,
)
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestNavigationTaskAndContestantManagementRestActions(APITestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="Task Management Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        self.route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="Task Management Task",
            original_scorecard=get_default_scorecard(),
            route=self.route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        self.manager = get_user_model().objects.create(email="task-mgmt-manager@example.com")
        assign_perm("view_contest", self.manager, self.contest)
        assign_perm("change_contest", self.manager, self.contest)
        self.client.force_login(user=self.manager)

    def _make_contestant(self, number, **overrides):
        now = datetime.datetime.now(datetime.timezone.utc)
        crew = Crew.objects.create(
            member1=Person.objects.create(
                first_name=f"P{number}", last_name="Mgmt", email=f"p{number}-mgmt@example.com"
            )
        )
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration=f"LN-MG{number}"))
        defaults = dict(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id=f"task-mgmt-device-{number}",
            contestant_number=number,
        )
        defaults.update(overrides)
        return Contestant.objects.create(**defaults)

    def _url(self, action, viewset="navigationtasks", **extra_kwargs):
        kwargs = {"contest_pk": self.contest.pk, "pk": self.navigation_task.pk}
        kwargs.update(extra_kwargs)
        return reverse(f"{viewset}-{action}", kwargs=kwargs)

    def test_remove_contestants_deletes_all_and_reports_count(self, *args):
        self._make_contestant(1)
        self._make_contestant(2)
        response = self.client.post(self._url("remove-contestants"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["deleted"], 2)
        self.assertEqual(self.navigation_task.contestant_set.count(), 0)

    def test_remove_contestants_requires_change_contest_permission(self, *args):
        self._make_contestant(1)
        viewer = get_user_model().objects.create(email="task-mgmt-viewer@example.com")
        assign_perm("view_contest", viewer, self.contest)
        self.client.force_login(user=viewer)
        response = self.client.post(self._url("remove-contestants"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.navigation_task.contestant_set.count(), 1)

    def test_batch_update_contestants_shifts_times_and_updates_wind(self, *args):
        c1 = self._make_contestant(1)
        c2 = self._make_contestant(2)
        original_takeoff = c1.takeoff_time

        response = self.client.post(
            self._url("batch-update-contestants"),
            {
                "contestant_ids": [c1.pk, c2.pk],
                "update_wind": True,
                "wind_speed": 12.5,
                "wind_direction": 270,
                "shift_times": True,
                "time_shift_minutes": 15,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["updated"], 2)
        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertEqual(c1.takeoff_time, original_takeoff + datetime.timedelta(minutes=15))
        self.assertEqual(c1.wind_speed, 12.5)
        self.assertEqual(c1.wind_direction, 270)

    @patch("display.viewsets.is_calculator_running", return_value=True)
    def test_batch_update_contestants_skips_currently_running_calculator(self, _mock_running, *args):
        c1 = self._make_contestant(1)
        original_takeoff = c1.takeoff_time

        response = self.client.post(
            self._url("batch-update-contestants"),
            {"contestant_ids": [c1.pk], "shift_times": True, "time_shift_minutes": 15},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["updated"], 0)
        c1.refresh_from_db()
        self.assertEqual(c1.takeoff_time, original_takeoff)

    def test_refresh_editable_route_succeeds(self, *args):
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Refresh test", file.readlines()[1:])
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])
        old_route_pk = self.navigation_task.route.pk

        response = self.client.post(self._url("refresh-editable-route"))

        self.assertEqual(response.status_code, 200, response.content)
        self.navigation_task.refresh_from_db()
        self.assertNotEqual(self.navigation_task.route.pk, old_route_pk)

    def test_refresh_editable_route_rejects_when_no_editable_route_linked(self, *args):
        response = self.client.post(self._url("refresh-editable-route"))
        self.assertEqual(response.status_code, 400)

    def test_refresh_editable_route_rejects_when_contestants_exist(self, *args):
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Refresh test 2", file.readlines()[1:])
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["editable_route"])
        self._make_contestant(1)

        response = self.client.post(self._url("refresh-editable-route"))

        self.assertEqual(response.status_code, 400)

    def test_destroy_contestant_succeeds_for_change_contest_only_manager(self, *args):
        # The classic ContestantDeleteView only required change_contest (not delete_contest) -
        # ContestantViewSet.destroy must match that, not the stricter delete_contest the base
        # ContestantNavigationTaskContestPermissions maps DELETE to (see get_permissions()).
        contestant = self._make_contestant(1)
        url = reverse(
            "contestants-detail",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk, "pk": contestant.pk},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204, response.content)
        self.assertFalse(Contestant.objects.filter(pk=contestant.pk).exists())

    def test_destroy_contestant_requires_change_contest_permission(self, *args):
        contestant = self._make_contestant(1)
        viewer = get_user_model().objects.create(email="task-mgmt-destroy-viewer@example.com")
        assign_perm("view_contest", viewer, self.contest)
        self.client.force_login(user=viewer)
        url = reverse(
            "contestants-detail",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk, "pk": contestant.pk},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Contestant.objects.filter(pk=contestant.pk).exists())

    def _make_contest_team(self, number=1, **overrides):
        crew = Crew.objects.create(
            member1=Person.objects.create(
                first_name=f"QA{number}", last_name="Team", email=f"qa{number}-team@example.com"
            )
        )
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration=f"LN-QA{number}"))
        defaults = dict(contest=self.contest, team=team, air_speed=80)
        defaults.update(overrides)
        return ContestTeam.objects.create(**defaults)

    def test_quick_add_contestant_derives_schedule_from_starting_point_time(self, *args):
        contest_team = self._make_contest_team()
        starting_point_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)

        response = self.client.post(
            self._url("quick-add-contestant"),
            {"contest_team": contest_team.pk, "starting_point_time": starting_point_time.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        contestant = Contestant.objects.get(pk=response.data["id"])
        self.assertEqual(contestant.contestant_number, 1)
        self.assertEqual(contestant.team, contest_team.team)
        self.assertEqual(contestant.air_speed, 80)
        self.assertEqual(
            contestant.takeoff_time,
            starting_point_time - datetime.timedelta(minutes=self.navigation_task.minutes_to_starting_point),
        )

    def test_quick_add_contestant_numbers_are_sequential(self, *args):
        self._make_contestant(1)
        self._make_contestant(2)
        contest_team = self._make_contest_team()
        starting_point_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)

        response = self.client.post(
            self._url("quick-add-contestant"),
            {"contest_team": contest_team.pk, "starting_point_time": starting_point_time.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["contestant_number"], 3)

    def test_quick_add_contestant_rejects_contest_team_from_other_contest(self, *args):
        other_contest = Contest.objects.create(
            name="Other Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        other_contest_team = self._make_contest_team(contest=other_contest)
        starting_point_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)

        response = self.client.post(
            self._url("quick-add-contestant"),
            {"contest_team": other_contest_team.pk, "starting_point_time": starting_point_time.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_quick_add_contestant_requires_change_contest_permission(self, *args):
        contest_team = self._make_contest_team()
        viewer = get_user_model().objects.create(email="task-mgmt-quickadd-viewer@example.com")
        assign_perm("view_contest", viewer, self.contest)
        self.client.force_login(user=viewer)
        starting_point_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)

        response = self.client.post(
            self._url("quick-add-contestant"),
            {"contest_team": contest_team.pk, "starting_point_time": starting_point_time.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_update_details_applies_partial_changes(self, *args):
        response = self.client.post(
            self._url("update-details"),
            {"name": "Renamed task", "wind_speed": 12, "allow_self_management": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.navigation_task.refresh_from_db()
        self.assertEqual(self.navigation_task.name, "Renamed task")
        self.assertEqual(self.navigation_task.wind_speed, 12)
        self.assertTrue(self.navigation_task.allow_self_management)

    def test_update_details_leaves_unspecified_fields_untouched(self, *args):
        original_finish_time = self.navigation_task.finish_time

        response = self.client.post(self._url("update-details"), {"name": "Only the name changes"}, format="json")

        self.assertEqual(response.status_code, 200, response.content)
        self.navigation_task.refresh_from_db()
        self.assertEqual(self.navigation_task.name, "Only the name changes")
        self.assertEqual(self.navigation_task.finish_time, original_finish_time)

    def test_update_details_requires_change_contest_permission(self, *args):
        viewer = get_user_model().objects.create(email="task-mgmt-update-viewer@example.com")
        assign_perm("view_contest", viewer, self.contest)
        self.client.force_login(user=viewer)

        response = self.client.post(self._url("update-details"), {"name": "Should not apply"}, format="json")

        self.assertEqual(response.status_code, 403)

    def test_destroy_navigation_task_succeeds_for_delete_contest_manager(self, *args):
        # Unlike ContestantViewSet.destroy, NavigationTaskViewSet doesn't need a permission fix -
        # the classic NavigationTaskDeleteView already required delete_contest, matching the base
        # NavigationTaskContestPermissions' own DELETE branch.
        assign_perm("delete_contest", self.manager, self.contest)
        url = reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest.pk, "pk": self.navigation_task.pk})

        response = self.client.delete(url)

        self.assertEqual(response.status_code, 204, response.content)
        self.assertFalse(NavigationTask.objects.filter(pk=self.navigation_task.pk).exists())

    def test_destroy_navigation_task_requires_delete_contest_permission(self, *args):
        # self.manager only has change_contest (assigned in setUp) - matches most real
        # organizers, who don't have delete_contest.
        url = reverse("navigationtasks-detail", kwargs={"contest_pk": self.contest.pk, "pk": self.navigation_task.pk})

        response = self.client.delete(url)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(NavigationTask.objects.filter(pk=self.navigation_task.pk).exists())

    def test_flight_order_configuration_returns_current_config(self, *args):
        response = self.client.get(self._url("flight-order-configuration"))

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("map_source", response.data)
        self.assertIn("map_dpi", response.data)

    def test_flight_order_configuration_requires_change_contest_permission(self, *args):
        viewer = get_user_model().objects.create(email="task-mgmt-flightorder-viewer@example.com")
        assign_perm("view_contest", viewer, self.contest)
        self.client.force_login(user=viewer)

        response = self.client.get(self._url("flight-order-configuration"))

        self.assertEqual(response.status_code, 403)

    def test_update_flight_order_configuration_applies_partial_changes(self, *args):
        response = self.client.post(
            self._url("update-flight-order-configuration"),
            {"map_dpi": 200, "map_include_openaip_overlay": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.navigation_task.flightorderconfiguration.refresh_from_db()
        self.assertEqual(self.navigation_task.flightorderconfiguration.map_dpi, 200)
        self.assertTrue(self.navigation_task.flightorderconfiguration.map_include_openaip_overlay)

    def test_update_flight_order_configuration_requires_change_contest_permission(self, *args):
        viewer = get_user_model().objects.create(email="task-mgmt-flightorder-update-viewer@example.com")
        assign_perm("view_contest", viewer, self.contest)
        self.client.force_login(user=viewer)

        response = self.client.post(self._url("update-flight-order-configuration"), {"map_dpi": 200}, format="json")

        self.assertEqual(response.status_code, 403)

    def test_map_source_options_excludes_openaip_and_includes_always_on_sources(self, *args):
        # Mirrors get_available_map_source_definitions_for_navigation_task: openaip is
        # overlay-only and deliberately excluded from base-map choices; non-mbtiles built-ins
        # (osm/cyclosm) are always available regardless of the route's bounds.
        response = self.client.get(self._url("map-source-options"))

        self.assertEqual(response.status_code, 200, response.content)
        keys = {item["key"] for item in response.data}
        self.assertIn("cyclosm", keys)
        self.assertNotIn("openaip", keys)

    def test_map_source_options_requires_change_contest_permission(self, *args):
        viewer = get_user_model().objects.create(email="task-mgmt-map-source-viewer@example.com")
        assign_perm("view_contest", viewer, self.contest)
        self.client.force_login(user=viewer)

        response = self.client.get(self._url("map-source-options"))

        self.assertEqual(response.status_code, 403)

    def test_update_flight_order_configuration_accepts_available_map_source(self, *args):
        response = self.client.post(
            self._url("update-flight-order-configuration"),
            {"map_source": "cyclosm", "map_zoom_level": 12},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.navigation_task.flightorderconfiguration.refresh_from_db()
        self.assertEqual(self.navigation_task.flightorderconfiguration.map_source, "cyclosm")
        self.assertEqual(self.navigation_task.flightorderconfiguration.map_zoom_level, 12)

    def test_update_flight_order_configuration_rejects_unavailable_map_source(self, *args):
        response = self.client.post(
            self._url("update-flight-order-configuration"),
            {"map_source": "not-a-real-map-source"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("map_source", response.data)

    def test_update_flight_order_configuration_rejects_out_of_range_zoom_level_for_map_source(self, *args):
        response = self.client.post(
            self._url("update-flight-order-configuration"),
            {"map_source": "cyclosm", "map_zoom_level": 99},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("map_zoom_level", response.data)

    @patch("display.viewsets.generate_map_async")
    def test_generate_map_dispatches_async_task_for_a_contest_manager(self, mock_generate_map_async, *args):
        # self.manager already has change_contest (assigned in setUp), matching the same
        # manager-only gate as map_source_options/flight_order_configuration above - the
        # standalone "Navigation Map" generator reuses those two actions for its source list
        # and seed defaults rather than exposing its own.
        response = self.client.post(
            self._url("generate-map"),
            {
                "size": "A4",
                "orientation": "landscape",
                "plot_track_between_waypoints": True,
                "include_meridians_and_parallels_lines": True,
                "scale": 0,
                "map_source": "cyclosm",
                "include_openaip_overlay": False,
                "zoom_level": 12,
                "dpi": 150,
                "line_width": 0.5,
                "colour": "#0000ff",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 202, response.content)
        self.assertIn("status_check_url", response.data)
        mock_generate_map_async.delay.assert_called_once()
        call_args = mock_generate_map_async.delay.call_args.args
        self.assertEqual(call_args[0], self.navigation_task.pk)
        self.assertIsNone(call_args[1])
        self.assertEqual(call_args[2]["map_source"], "cyclosm")
        self.assertEqual(call_args[3], self.manager.pk)

    def test_generate_map_requires_change_contest_permission(self, *args):
        viewer = get_user_model().objects.create(email="task-mgmt-generate-map-viewer@example.com")
        assign_perm("view_contest", viewer, self.contest)
        self.client.force_login(user=viewer)

        response = self.client.post(
            self._url("generate-map"),
            {
                "size": "A4",
                "orientation": "landscape",
                "plot_track_between_waypoints": True,
                "include_meridians_and_parallels_lines": True,
                "scale": 0,
                "map_source": "cyclosm",
                "include_openaip_overlay": False,
                "zoom_level": 12,
                "dpi": 150,
                "line_width": 0.5,
                "colour": "#0000ff",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_generate_map_rejects_unavailable_map_source(self, *args):
        response = self.client.post(
            self._url("generate-map"),
            {
                "size": "A4",
                "orientation": "landscape",
                "plot_track_between_waypoints": True,
                "include_meridians_and_parallels_lines": True,
                "scale": 0,
                "map_source": "not-a-real-map-source",
                "include_openaip_overlay": False,
                "zoom_level": 12,
                "dpi": 150,
                "line_width": 0.5,
                "colour": "#0000ff",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("map_source", response.data)

    def test_generate_map_requires_authentication(self, *args):
        self.client.logout()

        response = self.client.post(
            self._url("generate-map"),
            {
                "size": "A4",
                "orientation": "landscape",
                "plot_track_between_waypoints": True,
                "include_meridians_and_parallels_lines": True,
                "scale": 0,
                "map_source": "cyclosm",
                "include_openaip_overlay": False,
                "zoom_level": 12,
                "dpi": 150,
                "line_width": 0.5,
                "colour": "#0000ff",
            },
            format="json",
        )

        # 401, not 403: the class-level NavigationTaskContestPermissions requires
        # IsAuthenticated before any object-level change_contest check runs.
        self.assertEqual(response.status_code, 401)
