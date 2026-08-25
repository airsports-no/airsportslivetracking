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
        serialiser = EditableRouteSerialiser(data=self.ROUTE_DATA, context={"request": self.request})
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
        serialiser = EditableRouteSerialiser(data=self.ROUTE_DATA, context={"request": self.request})
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
