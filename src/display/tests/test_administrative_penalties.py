import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import (
    AdministrativePenalty,
    Aeroplane,
    Contest,
    Contestant,
    Crew,
    EditableRoute,
    GateCumulativeScore,
    NavigationTask,
    Person,
    ScoreLogEntry,
    Scorecard,
    Team,
    TrackAnnotation,
)
from display.services.administrative_penalties import AdministrativePenaltyService
from display.waypoint import Waypoint
from utilities.mock_utilities import TraccarMock


class TestAdministrativePenalties(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.user = get_user_model().objects.create(username="penalty-organizer", email="penalty@example.com")
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Penalty test", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)
        self.contest = Contest.objects.create(
            name="Administrative penalty contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
            created_by=self.user,
        )
        self.navigation_task = NavigationTask.create(
            name="Administrative penalty task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Penalty", last_name="Pilot"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-PENALTY"))
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="penalty-test",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)

    @patch.object(ScoreLogEntry, "push")
    @patch.object(TrackAnnotation, "push")
    def test_apply_contestant_penalty_creates_score_log_annotation_and_updates_score(self, mock_annotation_push, mock_score_push):
        score_before = self.contestant.contestanttrack.score
        version_before = self.contestant.score_version

        entry = AdministrativePenaltyService.apply_contestant_penalty(
            contestant=self.contestant,
            points=25.0,
            reason="quarantine breach",
            gate="ADMIN-QUAR",
            actor=self.user,
        )

        self.contestant.refresh_from_db()
        self.contestant.contestanttrack.refresh_from_db()

        self.assertEqual(entry.gate, "ADMIN-QUAR")
        self.assertEqual(entry.message, "quarantine breach")
        self.assertEqual(entry.points, 25.0)
        self.assertEqual(self.contestant.contestanttrack.score, score_before + 25.0)
        self.assertEqual(self.contestant.score_version, version_before + 1)

        gate_score = GateCumulativeScore.objects.get(contestant=self.contestant, gate="ADMIN-QUAR")
        self.assertEqual(gate_score.points, 25.0)

        admin_penalty = AdministrativePenalty.objects.get(score_log_entry=entry)
        self.assertEqual(admin_penalty.contestant, self.contestant)
        self.assertEqual(admin_penalty.actor, self.user)
        self.assertEqual(admin_penalty.category, "quarantine")
        self.assertEqual(admin_penalty.reason, "quarantine breach")

        annotation = TrackAnnotation.objects.get(score_log_entry=entry)
        self.assertEqual(annotation.gate, "ADMIN-QUAR")
        self.assertIn("quarantine breach", annotation.message)
        self.assertEqual(mock_score_push.call_count, 1)
        self.assertEqual(mock_annotation_push.call_count, 1)

    @patch.object(ScoreLogEntry, "push")
    @patch.object(TrackAnnotation, "push")
    def test_apply_contestant_penalty_can_skip_annotation(self, mock_annotation_push, mock_score_push):
        entry = AdministrativePenaltyService.apply_contestant_penalty(
            contestant=self.contestant,
            points=10.0,
            reason="manual administrative note",
            gate="ADMIN-NOANN",
            category="fuel",
            annotation=False,
            actor=self.user,
        )

        self.assertTrue(ScoreLogEntry.objects.filter(pk=entry.pk).exists())
        self.assertFalse(TrackAnnotation.objects.filter(score_log_entry=entry).exists())
        admin_penalty = AdministrativePenalty.objects.get(score_log_entry=entry)
        self.assertEqual(admin_penalty.category, "fuel")
        self.assertEqual(admin_penalty.actor, self.user)
        self.assertEqual(mock_score_push.call_count, 1)
        self.assertEqual(mock_annotation_push.call_count, 0)

    @patch.object(ScoreLogEntry, "push")
    @patch.object(TrackAnnotation, "push")
    def test_quarantine_penalty_view_applies_penalty_and_redirects(self, mock_annotation_push, mock_score_push):
        self.client.force_login(self.user)
        score_before = self.contestant.contestanttrack.score
        version_before = self.contestant.score_version

        response = self.client.post(
            reverse("contestant_apply_quarantine_penalty", kwargs={"pk": self.contestant.pk}),
            {"points": "35", "reason": "late exit from quarantine", "category": "quarantine"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("contestant_gate_times", kwargs={"pk": self.contestant.pk}))

        self.contestant.refresh_from_db()
        self.contestant.contestanttrack.refresh_from_db()
        entry = ScoreLogEntry.objects.filter(contestant=self.contestant, gate="ADMIN-QUAR").latest("pk")
        admin_penalty = AdministrativePenalty.objects.get(score_log_entry=entry)
        self.assertEqual(entry.points, 35.0)
        self.assertEqual(entry.message, "late exit from quarantine")
        self.assertEqual(admin_penalty.category, "quarantine")
        self.assertEqual(admin_penalty.actor, self.user)
        self.assertEqual(self.contestant.contestanttrack.score, score_before + 35.0)
        self.assertEqual(self.contestant.score_version, version_before + 1)
        self.assertEqual(mock_score_push.call_count, 1)
        self.assertEqual(mock_annotation_push.call_count, 1)

    @patch.object(ScoreLogEntry, "push")
    @patch.object(TrackAnnotation, "push")
    def test_penalty_view_supports_other_categories(self, mock_annotation_push, mock_score_push):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("contestant_apply_quarantine_penalty", kwargs={"pk": self.contestant.pk}),
            {"points": "50", "reason": "ignored task instructions", "category": "instructions"},
        )

        self.assertEqual(response.status_code, 302)
        entry = ScoreLogEntry.objects.filter(contestant=self.contestant, gate="ADMIN-INSTR").latest("pk")
        admin_penalty = AdministrativePenalty.objects.get(score_log_entry=entry)
        self.assertEqual(entry.points, 50.0)
        self.assertEqual(entry.message, "ignored task instructions")
        self.assertEqual(admin_penalty.category, "instructions")
        self.assertEqual(admin_penalty.actor, self.user)
        self.assertEqual(mock_score_push.call_count, 1)
        self.assertEqual(mock_annotation_push.call_count, 1)

    @patch.object(ScoreLogEntry, "push")
    @patch.object(TrackAnnotation, "push")
    def test_penalty_view_supports_observation_and_map_categories(self, mock_annotation_push, mock_score_push):
        self.client.force_login(self.user)

        observation_response = self.client.post(
            reverse("contestant_apply_quarantine_penalty", kwargs={"pk": self.contestant.pk}),
            {"points": "20", "reason": "photo evidence mismatch", "category": "observation"},
        )
        map_response = self.client.post(
            reverse("contestant_apply_quarantine_penalty", kwargs={"pk": self.contestant.pk}),
            {"points": "30", "reason": "map placement mismatch", "category": "map"},
        )

        self.assertEqual(observation_response.status_code, 302)
        self.assertEqual(map_response.status_code, 302)
        observation_entry = ScoreLogEntry.objects.filter(contestant=self.contestant, gate="ADMIN-OBS").latest("pk")
        map_entry = ScoreLogEntry.objects.filter(contestant=self.contestant, gate="ADMIN-MAP").latest("pk")
        observation_penalty = AdministrativePenalty.objects.get(score_log_entry=observation_entry)
        map_penalty = AdministrativePenalty.objects.get(score_log_entry=map_entry)
        self.assertEqual(observation_entry.message, "photo evidence mismatch")
        self.assertEqual(map_entry.message, "map placement mismatch")
        self.assertEqual(observation_penalty.category, "observation")
        self.assertEqual(map_penalty.category, "map")
        self.assertEqual(mock_score_push.call_count, 2)
        self.assertEqual(mock_annotation_push.call_count, 2)

    @patch.object(ScoreLogEntry, "push")
    @patch.object(TrackAnnotation, "push")
    def test_score_data_includes_structured_administrative_penalties(self, mock_annotation_push, mock_score_push):
        self.client.force_login(self.user)
        self.navigation_task.task_subtype = "known_circuit"
        self.navigation_task.save(update_fields=["task_subtype"])

        AdministrativePenaltyService.apply_contestant_penalty(
            contestant=self.contestant,
            points=12.0,
            reason="photo evidence mismatch",
            gate="ADMIN-OBS",
            category="observation",
            actor=self.user,
        )

        score_response = self.client.get(
            reverse(
                "contestants-score",
                kwargs={
                    "contest_pk": self.contest.pk,
                    "navigationtask_pk": self.navigation_task.pk,
                    "pk": self.contestant.pk,
                },
            )
        )

        self.assertEqual(score_response.status_code, 200)
        penalties = score_response.json()["administrative_penalties"]
        self.assertEqual(len(penalties), 1)
        self.assertEqual(penalties[0]["category"], "observation")
        self.assertEqual(penalties[0]["reason"], "photo evidence mismatch")
        self.assertEqual(penalties[0]["actor_email"], self.user.email)
        self.assertEqual(mock_score_push.call_count, 1)
        self.assertEqual(mock_annotation_push.call_count, 1)

    @patch.object(ScoreLogEntry, "push")
    @patch.object(TrackAnnotation, "push")
    def test_score_data_includes_manual_observation_judging_mode(self, mock_annotation_push, mock_score_push):
        self.client.force_login(self.user)
        editable_route = EditableRoute.objects.create(
            name="Score data observation primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "hg-1", "name": "HG1", "pointType": "secret", "featureType": "route_waypoint", "width": 1852, "isTiming": False, "isPassing": True}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                ],
            },
        )
        self.navigation_task.task_subtype = "known_circuit"
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])

        from display.services.contestant_task_compiler import ContestantTaskCompiler

        ContestantTaskCompiler(self.contestant).compile(force=True)

        score_response = self.client.get(
            reverse(
                "contestants-score",
                kwargs={
                    "contest_pk": self.contest.pk,
                    "navigationtask_pk": self.navigation_task.pk,
                    "pk": self.contestant.pk,
                },
            )
        )

        self.assertEqual(score_response.status_code, 200)
        payload = score_response.json()["compiled_effective_route_payload"]
        self.assertEqual(payload["observation_judging_mode"], "external_manual")
        self.assertEqual(payload["manual_adjudication_categories"], ["observation", "map"])
        self.assertEqual(payload["observation_photos"][0]["evidence_category"], "observation")
        self.assertEqual(mock_score_push.call_count, 0)
        self.assertEqual(mock_annotation_push.call_count, 0)

    @patch.object(ScoreLogEntry, "push")
    @patch.object(TrackAnnotation, "push")
    def test_apply_contestant_penalty_uses_route_location_for_annotation_coordinates(self, mock_annotation_push, mock_score_push):
        waypoint = Waypoint("SP")
        waypoint.latitude = 61.1
        waypoint.longitude = 12.2
        self.route.waypoints = [waypoint]
        self.route.save(update_fields=["waypoints"])

        entry = AdministrativePenaltyService.apply_contestant_penalty(
            contestant=self.contestant,
            points=15.0,
            reason="route location penalty",
            gate="ADMIN-LOC",
            category="quarantine",
            actor=self.user,
        )

        annotation = TrackAnnotation.objects.get(score_log_entry=entry)
        self.assertEqual(annotation.latitude, 61.1)
        self.assertEqual(annotation.longitude, 12.2)
        self.assertEqual(mock_score_push.call_count, 1)
        self.assertEqual(mock_annotation_push.call_count, 1)

    def test_gate_times_view_exposes_compiled_evidence_context(self):
        editable_route = EditableRoute.objects.create(
            name="Gate times evidence primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "hg-1", "name": "HG1", "pointType": "secret", "featureType": "route_waypoint", "width": 1852, "isTiming": False, "isPassing": True}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                ],
            },
        )
        self.navigation_task.task_subtype = "known_circuit"
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])
        self.client.force_login(self.user)

        from display.services.contestant_task_compiler import ContestantTaskCompiler

        ContestantTaskCompiler(self.contestant).compile(force=True)
        response = self.client.get(reverse("contestant_gate_times", kwargs={"pk": self.contestant.pk}))

        self.assertEqual(response.status_code, 200)
        compiled_evidence = response.context["compiled_evidence"]
        self.assertEqual(compiled_evidence["hidden_gate_names"], ["HG1"])
        self.assertEqual(compiled_evidence["observation_judging_mode"], "external_manual")
        self.assertEqual(compiled_evidence["manual_adjudication_categories"], ["observation", "map"])
        self.assertEqual(compiled_evidence["observation_photos"][0]["name"], "Photo 1")
        self.assertEqual(compiled_evidence["observation_photos"][0]["evidence_category"], "observation")
        self.assertEqual(compiled_evidence["unknown_leg_names"], [])
        self.assertContains(response, "Compiled evidence review")
        self.assertContains(response, "HG1")
        self.assertContains(response, "Photo 1")
        self.assertContains(response, "observation")
        self.assertContains(response, "Apply observation penalty")
        self.assertContains(response, "Apply map-placement penalty")
        self.assertContains(response, 'value="observation"', html=False)
        self.assertContains(response, 'value="map"', html=False)

    def test_gate_times_view_exposes_unknown_leg_compiled_evidence_context(self):
        editable_route = EditableRoute.objects.create(
            name="Gate times unknown leg primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "ul-1", "name": "UL1", "pointType": "ul", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0, "segmentType": "straight"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                ],
            },
        )
        self.navigation_task.task_subtype = "unknown_legs"
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])
        self.client.force_login(self.user)

        from display.services.contestant_task_compiler import ContestantTaskCompiler

        ContestantTaskCompiler(self.contestant).compile(force=True)
        response = self.client.get(reverse("contestant_gate_times", kwargs={"pk": self.contestant.pk}))

        self.assertEqual(response.status_code, 200)
        compiled_evidence = response.context["compiled_evidence"]
        self.assertEqual(compiled_evidence["unknown_leg_names"], ["UL1"])
        self.assertEqual(compiled_evidence["observation_judging_mode"], "external_manual")
        self.assertEqual(compiled_evidence["manual_adjudication_categories"], ["observation", "map"])
        self.assertEqual(compiled_evidence["observation_photos"][0]["name"], "Photo 1")
        self.assertEqual(compiled_evidence["observation_photos"][0]["evidence_category"], "observation")
        self.assertEqual(compiled_evidence["hidden_gate_names"], [])
        self.assertContains(response, "Compiled evidence review")
        self.assertContains(response, "UL1")
        self.assertContains(response, "Photo 1")
        self.assertContains(response, "observation")
        self.assertContains(response, "Apply observation penalty")
        self.assertContains(response, "Apply map-placement penalty")

    def test_gate_times_view_exposes_anr_auxiliary_path_review_context(self):
        editable_route = EditableRoute.objects.create(
            name="Gate times ANR auxiliary primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "rts-1", "name": "Route to SP", "featureType": "route_to_sp_path"}, "geometry": {"type": "LineString", "coordinates": [[10.9, 59.9], [11.0, 60.0]]}},
                    {"type": "Feature", "properties": {"id": "rfp-1", "name": "Route from FP", "featureType": "route_from_fp_path"}, "geometry": {"type": "LineString", "coordinates": [[11.1, 60.1], [11.2, 60.0]]}},
                ],
            },
        )
        self.navigation_task.task_subtype = "anr_catalogue"
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])
        self.client.force_login(self.user)

        from display.services.contestant_task_compiler import ContestantTaskCompiler

        ContestantTaskCompiler(self.contestant).compile(force=True)
        response = self.client.get(reverse("contestant_gate_times", kwargs={"pk": self.contestant.pk}))

        self.assertEqual(response.status_code, 200)
        compiled_evidence = response.context["compiled_evidence"]
        self.assertEqual(
            compiled_evidence["compiled_auxiliary_paths"]["route_to_sp_path"],
            [[[10.9, 59.9], [11.0, 60.0]]],
        )
        self.assertEqual(
            compiled_evidence["compiled_auxiliary_paths"]["route_from_fp_path"],
            [[[11.1, 60.1], [11.2, 60.0]]],
        )
        self.assertContains(response, "Route to SP")
        self.assertContains(response, "Route from FP")

    def test_gate_times_view_uses_effective_waypoints_for_total_distance_and_cards(self):
        editable_route = EditableRoute.objects.create(
            name="Gate times contract distance primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.0, 60.8]]}},
                    {"type": "Feature", "properties": {"id": "wp-sp", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
                    {"type": "Feature", "properties": {"id": "wp-mp", "name": "MP", "pointType": "tp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.0, 60.4]}},
                    {"type": "Feature", "properties": {"id": "wp-fp", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 2}, "geometry": {"type": "Point", "coordinates": [11.0, 60.8]}},
                    {"type": "Feature", "properties": {"id": "cat-a", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.0, 60.2]}},
                    {"type": "Feature", "properties": {"id": "cat-b", "name": "B", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.0, 60.6]}},
                ],
            },
        )
        self.navigation_task.task_subtype = "contract_navigation_time_controls"
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])
        self.client.force_login(self.user)

        from display.services.contestant_task_compiler import ContestantTaskCompiler

        ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"declared_sequence": ["A", "MP", "B", "FP"], "declared_t_seconds": 600},
            force=True,
        )
        response = self.client.get(reverse("contestant_gate_times", kwargs={"pk": self.contestant.pk}))

        self.assertEqual(response.status_code, 200)
        rendered_names = [gate.name for gate in response.context["rendered_waypoints"]]
        self.assertEqual(rendered_names, ["SP", "A", "MP", "B", "FP"])
        self.assertContains(response, "A")
        self.assertContains(response, "B")
        self.assertGreater(response.context["total_distance"], 0)

    def test_gate_times_view_exposes_fuel_review_for_limited_fuel_turnpoint_hunt(self):
        editable_route = EditableRoute.objects.create(
            name="Gate times fuel primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "kt-1", "name": "TG1", "pointType": "tp", "featureType": "known_time_gate"}, "geometry": {"type": "Point", "coordinates": [11.25, 60.25]}},
                    {"type": "Feature", "properties": {"id": "obs-1", "name": "Photo 1", "featureType": "observation_photo"}, "geometry": {"type": "Point", "coordinates": [11.35, 60.35]}},
                ],
            },
        )
        self.navigation_task.task_subtype = "limited_fuel_turnpoint_hunt"
        self.navigation_task.editable_route = editable_route
        self.navigation_task.save(update_fields=["task_subtype", "editable_route"])
        self.client.force_login(self.user)

        from display.services.contestant_task_compiler import ContestantTaskCompiler

        ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={
                "predicted_sequence": ["A"],
                "predicted_gate_times": {"TG1": "2020-08-01T08:15:00Z"},
                "fuel_metadata": {"declared_endurance_minutes": 95},
            },
            force=True,
        )
        response = self.client.get(reverse("contestant_gate_times", kwargs={"pk": self.contestant.pk}))

        self.assertEqual(response.status_code, 200)
        fuel_review = response.context["compiled_fuel_review"]
        self.assertEqual(fuel_review["declared_endurance_minutes"], 95)
        self.assertEqual(fuel_review["fuel_deadline"], self.contestant.takeoff_time + datetime.timedelta(minutes=95))
        self.assertContains(response, "Declared endurance")
        self.assertContains(response, "95")
        self.assertContains(response, "Apply fuel-check penalty")
        self.assertContains(response, 'value="fuel"', html=False)

    def test_gate_times_view_exposes_duration_residual_fuel_review(self):
        self.navigation_task.task_subtype = "duration"
        self.navigation_task.task_config = {"duration_residual_fuel_required": True}
        self.navigation_task.save(update_fields=["task_subtype", "task_config"])
        self.client.force_login(self.user)

        from display.services.contestant_task_compiler import ContestantTaskCompiler

        ContestantTaskCompiler(self.contestant).compile(force=True)
        response = self.client.get(reverse("contestant_gate_times", kwargs={"pk": self.contestant.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["compiled_fuel_review"],
            {"duration_residual_fuel_required": True},
        )
        self.assertContains(response, "Residual fuel review")
        self.assertContains(response, "Residual fuel required")
        self.assertContains(response, "Apply fuel-check penalty")
        self.assertContains(response, 'value="fuel"', html=False)
