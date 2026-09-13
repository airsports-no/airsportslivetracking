from copy import deepcopy
import datetime
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase, override_settings
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from display.models import Contest
from display.serialisers import EditableRouteSerialiser
from display.default_scorecards.create_scorecards import create_scorecards
from display.viewsets import EditableRouteViewSet
from display.tasks import generate_editable_route_thumbnail
from utilities.mock_utilities import TraccarMock


class TestNavigationTaskCreationFlow(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.user = get_user_model().objects.create_user(email="navtask@example.com", password="secret")
        contest_creator, _ = Group.objects.get_or_create(name="ContestCreator")
        self.user.groups.add(contest_creator)
        self.user.user_permissions.add(Permission.objects.get(codename="add_contest"))
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.request = APIRequestFactory().post("/")
        self.request.user = self.user
        self.contest = Contest.objects.create(
            name="test",
            start_time=datetime.datetime.utcnow(),
            finish_time=datetime.datetime.utcnow(),
            time_zone="Europe/Oslo",
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)

        self.ROUTE_DATA = {
            "name": "API nav task route",
            "settings": {},
            "route": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "sp-1",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                            "segmentType": "straight",
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "fp-1",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 1,
                            "segmentType": "straight",
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                ],
            },
        }

    def NAVIGATION_TASK_DATA(self, editable_route_pk):
        return {
            "name": "Created nav task",
            "start_time": "2026-08-01T09:00:00Z",
            "finish_time": "2026-08-01T17:00:00Z",
            "display_background_map": True,
            "display_secrets": True,
            "minutes_to_starting_point": 5,
            "planning_time": 45,
            "original_scorecard": "FAI ANR",
            "minutes_to_landing": 30,
            "wind_speed": 0,
            "wind_direction": 0,
            "allow_self_management": True,
            "calculation_delay_minutes": 0,
            "editable_route": editable_route_pk,
            "corridor_width": 0.5,
            "rounded_corners": True,
        }

    def test_post_navigation_task_with_matching_task_subtype(self, *args):
        serialiser = EditableRouteSerialiser(data=self.ROUTE_DATA, context={"request": self.request})
        serialiser.is_valid()
        editable_route = serialiser.save()
        data = deepcopy(self.NAVIGATION_TASK_DATA(editable_route.pk))
        data["task_subtype"] = "anr_catalogue"
        data["task_config"] = {"source": "test"}
        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        payload = response.json()
        self.assertEqual(payload["task_subtype"], "anr_catalogue")
        self.assertEqual(payload["task_config"], {"source": "test"})

    @override_settings(GATE_CIMA_TASK_VISIBILITY=True, DEFAULT_FREE_TASK_TYPE_GROUPS=["legacy"])
    def test_post_navigation_task_with_cima_subtype_is_rejected_without_a_grant(self, *args):
        # Guards the API create path directly: the wizard UI hides CIMA subtypes
        # under this configuration, but that alone doesn't stop a client from
        # POSTing one straight to the API - assert_can_add_navigation_task must
        # be enforced in the serialiser too, or gating is UI-only.
        serialiser = EditableRouteSerialiser(data=self.ROUTE_DATA, context={"request": self.request})
        serialiser.is_valid()
        editable_route = serialiser.save()
        data = deepcopy(self.NAVIGATION_TASK_DATA(editable_route.pk))
        data["task_subtype"] = "anr_catalogue"
        data["task_config"] = {"source": "test"}
        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_post_navigation_task_rejects_route_incompatible_with_task_subtype(self, *args):
        # The dropdown filtering React/the wizards apply (compatible_task_types) is only a UX
        # affordance - this is the actual, non-bypassable server-side check. A plain waypoint
        # route (self.ROUTE_DATA) has none of the circle_*_marker features "circle" requires.
        serialiser = EditableRouteSerialiser(data=self.ROUTE_DATA, context={"request": self.request})
        serialiser.is_valid()
        editable_route = serialiser.save()
        data = deepcopy(self.NAVIGATION_TASK_DATA(editable_route.pk))
        data["original_scorecard"] = "FAI Precision"
        data.pop("corridor_width", None)
        data.pop("rounded_corners", None)
        data["task_subtype"] = "circle"
        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        errors = response.json()["editable_route"][0]
        self.assertIn("not compatible with the selected task type", errors)
        self.assertIn("circle_center_marker", errors)

    def test_post_navigation_task_response_includes_warnings_field(self, *args):
        # Advisory route-validation warnings (corridor geometry etc.) used to be surfaced only
        # as Django messages.warning() by the wizards and silently discarded by this API path.
        serialiser = EditableRouteSerialiser(data=self.ROUTE_DATA, context={"request": self.request})
        serialiser.is_valid()
        editable_route = serialiser.save()
        data = deepcopy(self.NAVIGATION_TASK_DATA(editable_route.pk))
        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        self.assertIn("warnings", response.json())
        self.assertIsInstance(response.json()["warnings"], list)

    def test_get_navigation_task_exposes_effective_legacy_precision_subtype_definition(self, *args):
        serialiser = EditableRouteSerialiser(data=self.ROUTE_DATA, context={"request": self.request})
        serialiser.is_valid()
        editable_route = serialiser.save()
        data = deepcopy(self.NAVIGATION_TASK_DATA(editable_route.pk))
        data["original_scorecard"] = "FAI Precision"
        data.pop("corridor_width", None)
        data.pop("rounded_corners", None)
        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        task_id = response.json()["id"]

        detail_response = self.client.get(f"/api/v1/contests/{self.contest.pk}/navigationtasks/{task_id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK, detail_response.content)
        detail_payload = detail_response.json()
        self.assertEqual(detail_payload["task_subtype"], None)
        self.assertEqual(detail_payload["effective_task_subtype"], "legacy_precision")
        self.assertEqual(detail_payload["task_subtype_definition"]["key"], "legacy_precision")
        self.assertEqual(detail_payload["task_subtype_definition"]["coarse_family"], "precision")
        self.assertFalse(detail_payload["task_subtype_definition"]["requires_contestant_configuration"])
        self.assertEqual(detail_payload["task_information"]["family_display_name"], "Precision navigation")
        self.assertEqual(detail_payload["task_information"]["subtype_display_name"], "Legacy precision navigation")

    def test_get_navigation_task_exposes_effective_legacy_anr_subtype_definition(self, *args):
        serialiser = EditableRouteSerialiser(data=self.ROUTE_DATA, context={"request": self.request})
        serialiser.is_valid()
        editable_route = serialiser.save()
        data = deepcopy(self.NAVIGATION_TASK_DATA(editable_route.pk))
        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        task_id = response.json()["id"]

        detail_response = self.client.get(f"/api/v1/contests/{self.contest.pk}/navigationtasks/{task_id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK, detail_response.content)
        detail_payload = detail_response.json()
        self.assertEqual(detail_payload["task_subtype"], None)
        self.assertEqual(detail_payload["effective_task_subtype"], "legacy_anr_corridor")
        self.assertEqual(detail_payload["task_subtype_definition"]["key"], "legacy_anr_corridor")
        self.assertEqual(detail_payload["task_subtype_definition"]["coarse_family"], "anr_corridor")
        self.assertFalse(detail_payload["task_subtype_definition"]["requires_contestant_configuration"])
        self.assertEqual(detail_payload["task_information"]["family_display_name"], "ANR corridor")
        self.assertEqual(detail_payload["task_information"]["subtype_display_name"], "Legacy ANR corridor")

    def test_post_navigation_task_with_unknown_legs_subtype_uses_existing_unknown_leg_primitive(self, *args):
        route_data = deepcopy(self.ROUTE_DATA)
        route_data["route"]["features"].insert(
            2,
            {
                "type": "Feature",
                "properties": {
                    "id": "ul-1",
                    "name": "UL1",
                    "pointType": "ul",
                    "featureType": "route_waypoint",
                    "width": 1852,
                    "isTiming": True,
                    "isPassing": True,
                    "sequence": 1,
                    "segmentType": "straight",
                },
                "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
            },
        )
        route_data["route"]["features"][3]["properties"]["sequence"] = 2
        route_data["route"]["features"].append(
            {
                "type": "Feature",
                "properties": {
                    "id": "obs-1",
                    "name": "Photo 1",
                    "featureType": "observation_photo",
                },
                "geometry": {"type": "Point", "coordinates": [11.25, 60.25]},
            }
        )
        serialiser = EditableRouteSerialiser(data=route_data, context={"request": self.request})
        serialiser.is_valid()
        editable_route = serialiser.save()
        data = deepcopy(self.NAVIGATION_TASK_DATA(editable_route.pk))
        data["original_scorecard"] = "FAI Precision"
        data.pop("corridor_width", None)
        data.pop("rounded_corners", None)
        data["task_subtype"] = "unknown_legs"

        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        payload = response.json()
        self.assertEqual(payload["task_subtype"], "unknown_legs")

        detail_response = self.client.get(f"/api/v1/contests/{self.contest.pk}/navigationtasks/{payload['id']}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK, detail_response.content)
        detail_payload = detail_response.json()
        self.assertGreaterEqual(len(detail_payload.get("task_catalogue_targets") or []), 1)
        self.assertEqual(
            detail_payload["task_catalogue_targets"][0]["segment_name"],
            "segment_1",
        )

    def test_post_navigation_task_with_turnpoint_hunt_task_config(self, *args):
        # limited_fuel_turnpoint_hunt has no route backbone - 2.A6/2.B2 are standalone timed
        # turnpoints only (see TASK_SUBTYPE_DEFINITIONS and
        # route_compatibility.turnpoint_hunt_structural_errors, which also requires exactly three
        # known_time_gate markers), so this can't extend self.ROUTE_DATA (a route_path + SP/FP
        # backbone) the way the other subtype tests in this file do.
        route_data = {
            "name": "Turnpoint hunt route",
            "settings": {},
            "route": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"id": "ctp-1", "name": "CTP1", "featureType": "catalogue_turnpoint"},
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "ktg-1", "name": "KTG1", "featureType": "known_time_gate"},
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "ktg-2", "name": "KTG2", "featureType": "known_time_gate"},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "ktg-3", "name": "KTG3", "featureType": "known_time_gate"},
                        "geometry": {"type": "Point", "coordinates": [11.3, 60.3]},
                    },
                ],
            },
        }
        serialiser = EditableRouteSerialiser(data=route_data, context={"request": self.request})
        serialiser.is_valid()
        editable_route = serialiser.save()
        data = deepcopy(self.NAVIGATION_TASK_DATA(editable_route.pk))
        data["original_scorecard"] = "FAI Precision"
        data.pop("corridor_width", None)
        data.pop("rounded_corners", None)
        data["task_subtype"] = "limited_fuel_turnpoint_hunt"
        data["task_config"] = {
            "maximum_task_duration_minutes": 45,
            "maximum_task_duration_penalty": 123,
            "fuel_deadline_penalty": 77,
            "compulsory_timing_tolerance_seconds": 8,
        }
        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        payload = response.json()
        self.assertEqual(payload["task_subtype"], "limited_fuel_turnpoint_hunt")
        self.assertEqual(
            payload["task_config"],
            {
                "maximum_task_duration_minutes": 45,
                "maximum_task_duration_penalty": 123,
                "fuel_deadline_penalty": 77,
                "compulsory_timing_tolerance_seconds": 8,
            },
        )

    def test_post_navigation_task_rejects_turnpoint_hunt_route_with_a_backbone(self, *args):
        # get_blocking_reasons alone only checks primitive presence (catalogue_turnpoint/
        # known_time_gate exist somewhere), not the CodeRabbit-reviewed structural rules
        # (turnpoint_hunt_structural_errors) - a route with an authored route_path backbone must
        # still be rejected even though it has the required primitives.
        route_data = deepcopy(self.ROUTE_DATA)
        route_data["route"]["features"].extend(
            [
                {
                    "type": "Feature",
                    "properties": {"id": "ctp-1", "name": "CTP1", "featureType": "catalogue_turnpoint"},
                    "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                },
                {
                    "type": "Feature",
                    "properties": {"id": "ktg-1", "name": "KTG1", "featureType": "known_time_gate"},
                    "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                },
                {
                    "type": "Feature",
                    "properties": {"id": "ktg-2", "name": "KTG2", "featureType": "known_time_gate"},
                    "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                },
                {
                    "type": "Feature",
                    "properties": {"id": "ktg-3", "name": "KTG3", "featureType": "known_time_gate"},
                    "geometry": {"type": "Point", "coordinates": [11.3, 60.3]},
                },
            ]
        )
        serialiser = EditableRouteSerialiser(data=route_data, context={"request": self.request})
        serialiser.is_valid()
        editable_route = serialiser.save()
        data = deepcopy(self.NAVIGATION_TASK_DATA(editable_route.pk))
        data["original_scorecard"] = "FAI Precision"
        data.pop("corridor_width", None)
        data.pop("rounded_corners", None)
        data["task_subtype"] = "limited_fuel_turnpoint_hunt"
        data["task_config"] = {
            "maximum_task_duration_minutes": 45,
            "maximum_task_duration_penalty": 123,
            "fuel_deadline_penalty": 77,
            "compulsory_timing_tolerance_seconds": 8,
        }
        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        errors = response.json()["editable_route"][0]
        self.assertIn("no route backbone", errors)

    def test_post_navigation_task_with_duration_task_config(self, *args):
        serialiser = EditableRouteSerialiser(data=self.ROUTE_DATA, context={"request": self.request})
        serialiser.is_valid()
        editable_route = serialiser.save()
        data = deepcopy(self.NAVIGATION_TASK_DATA(editable_route.pk))
        data["original_scorecard"] = "FAI Precision"
        data.pop("corridor_width", None)
        data.pop("rounded_corners", None)
        data["task_subtype"] = "duration"
        data["task_config"] = {
            "duration_normalization_policy": "raw_minutes",
        }
        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        payload = response.json()
        self.assertEqual(payload["task_subtype"], "duration")
        self.assertEqual(payload["task_config"], {"duration_normalization_policy": "raw_minutes"})

    def test_post_navigation_task_with_duration_landing_area_polygon(self, *args):
        serialiser = EditableRouteSerialiser(data=self.ROUTE_DATA, context={"request": self.request})
        serialiser.is_valid()
        editable_route = serialiser.save()
        data = deepcopy(self.NAVIGATION_TASK_DATA(editable_route.pk))
        data["original_scorecard"] = "FAI Precision"
        data.pop("corridor_width", None)
        data.pop("rounded_corners", None)
        data["task_subtype"] = "duration"
        data["task_config"] = {
            "duration_landing_area_polygon": [[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2]],
        }
        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        payload = response.json()
        self.assertEqual(payload["task_subtype"], "duration")
        self.assertEqual(
            payload["task_config"],
            {"duration_landing_area_polygon": [[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2]]},
        )

    def test_post_navigation_task_with_duration_residual_fuel_required(self, *args):
        serialiser = EditableRouteSerialiser(data=self.ROUTE_DATA, context={"request": self.request})
        serialiser.is_valid()
        editable_route = serialiser.save()
        data = deepcopy(self.NAVIGATION_TASK_DATA(editable_route.pk))
        data["original_scorecard"] = "FAI Precision"
        data.pop("corridor_width", None)
        data.pop("rounded_corners", None)
        data["task_subtype"] = "duration"
        data["task_config"] = {
            "duration_residual_fuel_required": True,
        }
        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        payload = response.json()
        self.assertEqual(payload["task_subtype"], "duration")
        self.assertEqual(payload["task_config"], {"duration_residual_fuel_required": True})

    def test_post_navigation_task_with_circle_radius_config(self, *args):
        # circle has no route backbone - it requires the editable route to carry all four
        # standalone circle_*_marker features instead (see TASK_SUBTYPE_DEFINITIONS), which the
        # plain self.ROUTE_DATA fixture doesn't have.
        route_data = deepcopy(self.ROUTE_DATA)
        route_data["route"]["features"].extend(
            [
                {
                    "type": "Feature",
                    "properties": {"id": "cm-1", "name": "CM", "featureType": "circle_center_marker"},
                    "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                },
                {
                    "type": "Feature",
                    "properties": {"id": "cs-1", "name": "CS", "featureType": "circle_start_marker"},
                    "geometry": {"type": "Point", "coordinates": [11.01, 60.0]},
                },
                {
                    "type": "Feature",
                    "properties": {"id": "ce-1", "name": "CE", "featureType": "circle_entry_marker"},
                    "geometry": {"type": "Point", "coordinates": [11.02, 60.0]},
                },
                {
                    "type": "Feature",
                    "properties": {"id": "cx-1", "name": "CX", "featureType": "circle_exit_marker"},
                    "geometry": {"type": "Point", "coordinates": [11.03, 60.0]},
                },
            ]
        )
        serialiser = EditableRouteSerialiser(data=route_data, context={"request": self.request})
        serialiser.is_valid()
        editable_route = serialiser.save()
        data = deepcopy(self.NAVIGATION_TASK_DATA(editable_route.pk))
        data["original_scorecard"] = "FAI Precision"
        data.pop("corridor_width", None)
        data.pop("rounded_corners", None)
        data["task_subtype"] = "circle"
        data["task_config"] = {
            "circle_radius_min_m": 250,
            "circle_radius_max_m": 800,
        }
        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        payload = response.json()
        self.assertEqual(payload["task_subtype"], "circle")
        self.assertEqual(payload["task_config"], {"circle_radius_min_m": 250, "circle_radius_max_m": 800})

        detail_response = self.client.get(f"/api/v1/contests/{self.contest.pk}/navigationtasks/{payload['id']}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK, detail_response.content)
        detail_payload = detail_response.json()
        self.assertEqual(detail_payload["task_information"]["subtype_display_name"], "2.A7 Circle")
        self.assertIn("Configured radius band is 250 m to 800 m.", detail_payload["task_information"]["overrides"])

    def test_post_navigation_task_rejects_incompatible_task_subtype(self, *args):
        serialiser = EditableRouteSerialiser(data=self.ROUTE_DATA, context={"request": self.request})
        serialiser.is_valid()
        editable_route = serialiser.save()
        data = deepcopy(self.NAVIGATION_TASK_DATA(editable_route.pk))
        data["task_subtype"] = "curve_navigation_time_estimation"
        response = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/navigationtasks/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("task_subtype", response.json())


class EditableRouteViewSetThumbnailSchedulingTests(TestCase):
    def test_perform_create_enqueues_thumbnail_generation_on_commit(self):
        viewset = EditableRouteViewSet()
        serializer = type("SerializerStub", (), {"instance": type("EditableRouteStub", (), {"pk": 123})()})()

        with patch("display.viewsets.ModelViewSet.perform_create") as super_create, \
             patch("display.viewsets.transaction.on_commit") as on_commit_mock, \
             patch("display.viewsets.generate_editable_route_thumbnail.delay") as delay_mock:
            viewset.perform_create(serializer)

            super_create.assert_called_once_with(serializer)
            on_commit_mock.assert_called_once()
            delay_mock.assert_not_called()
            on_commit_mock.call_args.args[0]()
            delay_mock.assert_called_once_with(123)

    def test_perform_update_enqueues_thumbnail_generation_on_commit(self):
        viewset = EditableRouteViewSet()
        serializer = type("SerializerStub", (), {"instance": type("EditableRouteStub", (), {"pk": 456})()})()

        with patch("display.viewsets.ModelViewSet.perform_update") as super_update, \
             patch("display.viewsets.transaction.on_commit") as on_commit_mock, \
             patch("display.viewsets.generate_editable_route_thumbnail.delay") as delay_mock:
            viewset.perform_update(serializer)

            super_update.assert_called_once_with(serializer)
            on_commit_mock.assert_called_once()
            delay_mock.assert_not_called()
            on_commit_mock.call_args.args[0]()
            delay_mock.assert_called_once_with(456)


class EditableRouteThumbnailTaskTests(TestCase):
    def test_generate_editable_route_thumbnail_updates_existing_route(self):
        route = MagicMock()
        manager = MagicMock()
        manager.get.return_value = route
        missing_exception = type("MissingRoute", (Exception,), {})
        editable_route_model = type("EditableRouteModelStub", (), {"objects": manager, "DoesNotExist": missing_exception})
        import sys
        original_models = sys.modules.get("display.models")
        display_models_stub = MagicMock()
        display_models_stub.EditableRoute = editable_route_model
        sys.modules["display.models"] = display_models_stub
        try:
            generate_editable_route_thumbnail(7)
        finally:
            if original_models is None:
                del sys.modules["display.models"]
            else:
                sys.modules["display.models"] = original_models

        manager.get.assert_called_once_with(pk=7)
        route.update_thumbnail.assert_called_once_with()

    def test_generate_editable_route_thumbnail_ignores_missing_route(self):
        missing_exception = type("MissingRoute", (Exception,), {})
        manager = MagicMock()
        manager.get.side_effect = missing_exception()
        editable_route_model = type("EditableRouteModelStub", (), {"objects": manager, "DoesNotExist": missing_exception})
        import sys
        original_models = sys.modules.get("display.models")
        display_models_stub = MagicMock()
        display_models_stub.EditableRoute = editable_route_model
        sys.modules["display.models"] = display_models_stub
        try:
            with patch("display.tasks.logger.warning") as warning_mock:
                generate_editable_route_thumbnail(9)
        finally:
            if original_models is None:
                del sys.modules["display.models"]
            else:
                sys.modules["display.models"] = original_models

        manager.get.assert_called_once_with(pk=9)
        warning_mock.assert_called_once()
