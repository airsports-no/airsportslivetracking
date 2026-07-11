import datetime
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TransactionTestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    Contest,
    ContestTeam,
    ContestSummary,
    Crew,
    NavigationTask,
    Person,
    Route,
    Task,
    TaskSummary,
    TaskTest,
    Team,
    TeamTestScore,
)
from websocket_channels import WebsocketFacade


class ResultsRealtimeUpdateTests(TransactionTestCase):
    def setUp(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(
            name="Realtime Results Contest",
            start_time=now,
            finish_time=now + datetime.timedelta(hours=1),
            location="60.0,11.0",
            time_zone="UTC",
            autosum_scores=True,
            summary_score_sorting_direction=Contest.DESCENDING,
        )
        self.team = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="One", email="p1@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-RT1"),
        )
        self.task = Task.objects.create(
            contest=self.contest,
            name="task-1",
            heading="Task 1",
            index=1,
            autosum_scores=True,
            summary_score_sorting_direction=Task.DESCENDING,
        )
        self.task_test = TaskTest.objects.create(
            task=self.task,
            name="test-1",
            heading="Test 1",
            index=1,
            sorting=TaskTest.DESCENDING,
        )

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_team_test_score_update_emits_single_bundled_score_update(self, safe_group_send):
        score = TeamTestScore.objects.create(team=self.team, task_test=self.task_test, points=12)

        self.assertEqual(TaskSummary.objects.get(task=self.task, team=self.team).points, 12)
        self.assertEqual(ContestSummary.objects.get(contest=self.contest, team=self.team).points, 12)
        self.assertEqual(safe_group_send.call_count, 1)

        group_name, payload = safe_group_send.call_args.args
        self.assertEqual(group_name, f"contestresults_{self.contest.pk}")
        self.assertEqual(payload["type"], "contestresults")
        self.assertEqual(payload["content"]["type"], "score.update")
        self.assertEqual(payload["content"]["test_score"]["id"], score.id)
        self.assertEqual(payload["content"]["test_score"]["points"], 12.0)
        self.assertEqual(payload["content"]["task_summary"]["team"], self.team.id)
        self.assertEqual(payload["content"]["task_summary"]["task"], self.task.id)
        self.assertEqual(payload["content"]["task_summary"]["points"], 12.0)
        self.assertEqual(payload["content"]["contest_summary"]["team"], self.team.id)
        self.assertEqual(payload["content"]["task_test_id"], self.task_test.id)
        self.assertEqual(payload["content"]["team_id"], self.team.id)

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_task_test_create_emits_full_results_refresh(self, safe_group_send):
        extra_test = TaskTest.objects.create(
            task=self.task,
            name="test-2",
            heading="Test 2",
            index=2,
            sorting=TaskTest.DESCENDING,
        )

        self.assertIsNotNone(extra_test.pk)
        self.assertEqual(safe_group_send.call_count, 1)
        group_name, payload = safe_group_send.call_args.args
        self.assertEqual(group_name, f"contestresults_{self.contest.pk}")
        self.assertEqual(payload["type"], "contestresults")
        self.assertEqual(payload["content"]["type"], "contest.results")
        self.assertIn("results", payload["content"])
        returned_test_ids = [
            test["id"]
            for task in payload["content"]["results"]["task_set"]
            for test in task["tasktest_set"]
        ]
        self.assertIn(extra_test.id, returned_test_ids)

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_manual_task_summary_update_still_emits_full_results_refresh(self, safe_group_send):
        task_summary = TaskSummary.objects.create(task=self.task, team=self.team, points=7)

        self.assertEqual(safe_group_send.call_count, 1)
        group_name, payload = safe_group_send.call_args.args
        self.assertEqual(group_name, f"contestresults_{self.contest.pk}")
        self.assertEqual(payload["content"]["type"], "contest.results")
        self.assertEqual(TaskSummary.objects.get(pk=task_summary.pk).points, 7)

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_manual_contest_summary_update_still_emits_full_results_refresh(self, safe_group_send):
        contest_summary = ContestSummary.objects.create(contest=self.contest, team=self.team, points=9)

        self.assertEqual(safe_group_send.call_count, 1)
        group_name, payload = safe_group_send.call_args.args
        self.assertEqual(group_name, f"contestresults_{self.contest.pk}")
        self.assertEqual(payload["content"]["type"], "contest.results")
        self.assertEqual(ContestSummary.objects.get(pk=contest_summary.pk).points, 9)

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_task_update_emits_tasks_message(self, safe_group_send):
        self.task.heading = "Renamed Task"
        self.task.save()

        self.assertEqual(safe_group_send.call_count, 1)
        group_name, payload = safe_group_send.call_args.args
        self.assertEqual(group_name, f"contestresults_{self.contest.pk}")
        self.assertEqual(payload["type"], "contestresults")
        self.assertEqual(payload["content"]["type"], "contest.tasks")
        matching_task = next(task for task in payload["content"]["tasks"] if task["id"] == self.task.id)
        self.assertEqual(matching_task["heading"], "Renamed Task")

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_task_test_update_emits_full_results_refresh(self, safe_group_send):
        self.task_test.heading = "Renamed Test"
        self.task_test.save()

        self.assertEqual(safe_group_send.call_count, 1)
        group_name, payload = safe_group_send.call_args.args
        self.assertEqual(group_name, f"contestresults_{self.contest.pk}")
        self.assertEqual(payload["type"], "contestresults")
        self.assertEqual(payload["content"]["type"], "contest.results")
        matching_task = next(task for task in payload["content"]["results"]["task_set"] if task["id"] == self.task.id)
        matching_test = next(test for test in matching_task["tasktest_set"] if test["id"] == self.task_test.id)
        self.assertEqual(matching_test["heading"], "Renamed Test")

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_team_test_score_update_repairs_missing_task_summaries_before_contest_total(self, safe_group_send):
        other_task = Task.objects.create(
            contest=self.contest,
            name="task-2",
            heading="Task 2",
            index=2,
            autosum_scores=True,
            summary_score_sorting_direction=Task.DESCENDING,
        )
        other_test = TaskTest.objects.create(
            task=other_task,
            name="test-3",
            heading="Test 3",
            index=1,
            sorting=TaskTest.DESCENDING,
        )

        first_score = TeamTestScore.objects.create(team=self.team, task_test=self.task_test, points=12)
        TeamTestScore.objects.create(team=self.team, task_test=other_test, points=30)

        TaskSummary.objects.filter(task=other_task, team=self.team).delete()
        ContestSummary.objects.filter(contest=self.contest, team=self.team).update(points=12)

        safe_group_send.reset_mock()
        first_score.points = 15
        first_score.save()

        repaired_summary = TaskSummary.objects.get(task=other_task, team=self.team)
        contest_summary = ContestSummary.objects.get(contest=self.contest, team=self.team)

        self.assertEqual(repaired_summary.points, 30)
        self.assertEqual(contest_summary.points, 45)
        self.assertEqual(safe_group_send.call_count, 1)
        _, payload = safe_group_send.call_args.args
        self.assertEqual(payload["content"]["type"], "score.update")
        self.assertEqual(payload["content"]["contest_summary"]["points"], 45)

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_team_test_score_update_does_not_duplicate_recovered_task_summary_when_other_crews_exist(
        self, safe_group_send
    ):
        other_task = Task.objects.create(
            contest=self.contest,
            name="task-4",
            heading="Task 4",
            index=4,
            autosum_scores=True,
            summary_score_sorting_direction=Task.DESCENDING,
        )
        other_test = TaskTest.objects.create(
            task=other_task,
            name="test-4",
            heading="Test 4",
            index=1,
            sorting=TaskTest.DESCENDING,
        )

        other_team_one = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="Two", email="p2@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-RT2"),
        )
        other_team_two = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="Three", email="p3@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-RT3"),
        )
        TaskSummary.objects.create(task=other_task, team=other_team_one, points=5)
        TaskSummary.objects.create(task=other_task, team=other_team_two, points=7)

        first_score = TeamTestScore.objects.create(team=self.team, task_test=self.task_test, points=12)
        TeamTestScore.objects.create(team=self.team, task_test=other_test, points=30)
        TaskSummary.objects.filter(task=other_task, team=self.team).delete()

        safe_group_send.reset_mock()
        first_score.points = 18
        first_score.save()

        recovered_summaries = TaskSummary.objects.filter(task=other_task, team=self.team)
        self.assertEqual(recovered_summaries.count(), 1)
        self.assertEqual(recovered_summaries.get().points, 30)

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_update_test_result_endpoint_does_not_raise_duplicate_tasksummary_error_when_missing_summary_exists(
        self, safe_group_send
    ):
        other_task = Task.objects.create(
            contest=self.contest,
            name="task-5",
            heading="Task 5",
            index=5,
            autosum_scores=True,
            summary_score_sorting_direction=Task.DESCENDING,
        )
        other_test = TaskTest.objects.create(
            task=other_task,
            name="test-5",
            heading="Test 5",
            index=1,
            sorting=TaskTest.DESCENDING,
        )
        other_team = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="Four", email="p4@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-RT4"),
        )
        TaskSummary.objects.create(task=other_task, team=other_team, points=11)

        TeamTestScore.objects.create(team=self.team, task_test=other_test, points=30)
        TaskSummary.objects.filter(task=other_task, team=self.team).delete()
        ContestSummary.objects.filter(contest=self.contest, team=self.team).update(points=0)

        safe_group_send.reset_mock()
        TeamTestScore.objects.filter(team=self.team, task_test=self.task_test).delete()
        created_score = TeamTestScore.objects.create(team=self.team, task_test=self.task_test, points=12)
        self.assertEqual(created_score.points, 12)
        recovered_summaries = TaskSummary.objects.filter(task=other_task, team=self.team)
        self.assertEqual(recovered_summaries.count(), 1)
        self.assertEqual(recovered_summaries.get().points, 30)

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_team_test_score_update_repairs_multiple_missing_task_summaries_without_duplicates(self, safe_group_send):
        task_a = Task.objects.create(
            contest=self.contest,
            name="task-6",
            heading="Task 6",
            index=6,
            autosum_scores=True,
            summary_score_sorting_direction=Task.DESCENDING,
        )
        task_b = Task.objects.create(
            contest=self.contest,
            name="task-7",
            heading="Task 7",
            index=7,
            autosum_scores=True,
            summary_score_sorting_direction=Task.DESCENDING,
        )
        test_a = TaskTest.objects.create(
            task=task_a,
            name="test-6",
            heading="Test 6",
            index=1,
            sorting=TaskTest.DESCENDING,
        )
        test_b = TaskTest.objects.create(
            task=task_b,
            name="test-7",
            heading="Test 7",
            index=1,
            sorting=TaskTest.DESCENDING,
        )

        other_team = Team.objects.create(
            crew=Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="Five", email="p5@example.com")),
            aeroplane=Aeroplane.objects.create(registration="LN-RT5"),
        )
        TaskSummary.objects.create(task=task_a, team=other_team, points=9)
        TaskSummary.objects.create(task=task_b, team=other_team, points=11)

        first_score = TeamTestScore.objects.create(team=self.team, task_test=self.task_test, points=12)
        TeamTestScore.objects.create(team=self.team, task_test=test_a, points=20)
        TeamTestScore.objects.create(team=self.team, task_test=test_b, points=30)
        contest_summary = ContestSummary.objects.get(contest=self.contest, team=self.team)

        safe_group_send.reset_mock()
        first_score.points = 19
        first_score.save()

        contest_summary.refresh_from_db()
        self.assertEqual(contest_summary.points, 69)
        self.assertEqual(safe_group_send.call_count, 1)


class NavigationTaskResultsServiceTests(APITransactionTestCase):
    @patch("display.models.contestant.get_traccar_instance")
    @patch("display.signals.get_traccar_instance")
    def setUp(self, mock_signal_traccar, mock_model_traccar):
        mock_traccar = Mock()
        mock_traccar.get_or_create_device.return_value = ({}, False)
        mock_traccar.update_device_name.return_value = None
        mock_traccar.get_device.return_value = None
        mock_traccar.delete_device.return_value = None
        mock_signal_traccar.return_value = mock_traccar
        mock_model_traccar.return_value = mock_traccar
        self.auth_user = get_user_model().objects.create(
            email="editor@example.com"
        )
        self.client.force_login(self.auth_user)
        self.contest = Contest.objects.create(
            name="Navigation Results Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2),
            time_zone="UTC",
            location="60.0,11.0",
        )
        assign_perm("display.change_contest", self.auth_user, self.contest)
        assign_perm("display.view_contest", self.auth_user, self.contest)
        self.route = Route.objects.create(name="Route")
        self.navigation_task = NavigationTask.create(
            name="Nav Task",
            original_scorecard=get_default_scorecard(),
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
            route=self.route,
            contest=self.contest,
        )

    def test_navigation_task_creation_creates_results_service_task_and_test(self, *_args):
        self.assertTrue(hasattr(self.navigation_task, "tasktest"))
        task_test = self.navigation_task.tasktest
        self.assertEqual(task_test.navigation_task_id, self.navigation_task.id)
        self.assertEqual(task_test.name, "Navigation")
        self.assertEqual(task_test.heading, "Navigation")
        self.assertEqual(task_test.task.contest_id, self.contest.id)
        self.assertEqual(task_test.task.heading, self.navigation_task.name)
        self.assertEqual(task_test.task.summary_score_sorting_direction, self.navigation_task.score_sorting_direction)

    def test_results_details_includes_navigation_task_results_service_entries(self, *_args):
        response = self.client.get(reverse("contests-results-details", kwargs={"pk": self.contest.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        payload = response.json()
        task_ids = [task["id"] for task in payload["task_set"]]
        self.assertIn(self.navigation_task.tasktest.task_id, task_ids)
        matching_task = next(task for task in payload["task_set"] if task["id"] == self.navigation_task.tasktest.task_id)
        matching_test = next(test for test in matching_task["tasktest_set"] if test["id"] == self.navigation_task.tasktest.id)
        self.assertEqual(matching_test["navigation_task"], self.navigation_task.id)
        self.assertIsNotNone(matching_test["navigation_task_link"])

    def test_deleting_navigation_task_removes_linked_results_service_entries(self, *_args):
        linked_task_id = self.navigation_task.tasktest.task_id
        linked_test_id = self.navigation_task.tasktest.id

        self.navigation_task.delete()

        self.assertFalse(TaskTest.objects.filter(pk=linked_test_id).exists())
        self.assertFalse(Task.objects.filter(pk=linked_task_id).exists())

    def test_navigation_backed_test_cannot_be_deleted_via_results_api(self, *_args):
        response = self.client.delete(
            reverse("tasktests-detail", kwargs={"contest_pk": self.contest.pk, "pk": self.navigation_task.tasktest.id})
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertTrue(TaskTest.objects.filter(pk=self.navigation_task.tasktest.id).exists())

    def test_navigation_backed_task_cannot_be_deleted_via_results_api(self, *_args):
        response = self.client.delete(
            reverse("tasks-detail", kwargs={"contest_pk": self.contest.pk, "pk": self.navigation_task.tasktest.task_id})
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertTrue(Task.objects.filter(pk=self.navigation_task.tasktest.task_id).exists())

    def test_navigation_backed_test_cannot_be_updated_via_results_api(self, *_args):
        response = self.client.put(
            reverse("tasktests-detail", kwargs={"contest_pk": self.contest.pk, "pk": self.navigation_task.tasktest.id}),
            data={
                "id": self.navigation_task.tasktest.id,
                "task": self.navigation_task.tasktest.task_id,
                "name": "Changed",
                "heading": "Changed",
                "weight": 2,
                "sorting": self.navigation_task.tasktest.sorting,
                "index": self.navigation_task.tasktest.index,
                "navigation_task": self.navigation_task.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.navigation_task.tasktest.refresh_from_db()
        self.assertEqual(self.navigation_task.tasktest.name, "Navigation")

    def test_navigation_backed_task_cannot_be_updated_via_results_api(self, *_args):
        linked_task = self.navigation_task.tasktest.task
        response = self.client.put(
            reverse("tasks-detail", kwargs={"contest_pk": self.contest.pk, "pk": linked_task.id}),
            data={
                "id": linked_task.id,
                "contest": self.contest.id,
                "name": linked_task.name,
                "heading": "Changed Task Heading",
                "weight": linked_task.weight,
                "index": linked_task.index,
                "autosum_scores": linked_task.autosum_scores,
                "summary_score_sorting_direction": linked_task.summary_score_sorting_direction,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        linked_task.refresh_from_db()
        self.assertEqual(linked_task.heading, self.navigation_task.name)


class ContestResultsEndpointBroadcastTests(APITransactionTestCase):
    def setUp(self):
        self.auth_user = get_user_model().objects.create(email="contest-editor@example.com")
        self.client.force_login(self.auth_user)
        self.contest = Contest.objects.create(
            name="Broadcast Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2),
            time_zone="UTC",
            location="60.0,11.0",
        )
        assign_perm("display.change_contest", self.auth_user, self.contest)
        assign_perm("display.view_contest", self.auth_user, self.contest)
        self.team = Team.objects.create(
            crew=Crew.objects.create(
                member1=Person.objects.create(first_name="Pilot", last_name="Two", email="p2@example.com")
            ),
            aeroplane=Aeroplane.objects.create(registration="LN-RT2"),
        )
        self.contest_team = ContestTeam.objects.create(contest=self.contest, team=self.team)

    @patch.object(WebsocketFacade, "transmit_contest_results")
    @patch.object(WebsocketFacade, "transmit_teams")
    def test_team_results_delete_broadcasts_results_and_removes_team_via_signals(self, transmit_teams, transmit_results):
        response = self.client.post(
            reverse("contests-team-results-delete", kwargs={"pk": self.contest.pk}),
            data={"team_id": self.team.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.content)
        transmit_results.assert_called_once_with(self.auth_user, self.contest)
        self.assertEqual(transmit_teams.call_count, 1)
        transmit_teams.assert_called_with(self.contest)


class ContestResultsRestMutationTests(APITransactionTestCase):
    def setUp(self):
        self.auth_user = get_user_model().objects.create(email="results-editor@example.com")
        self.client.force_login(self.auth_user)
        now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(
            name="REST Mutation Contest",
            start_time=now,
            finish_time=now + datetime.timedelta(hours=2),
            time_zone="UTC",
            location="60.0,11.0",
            autosum_scores=True,
            summary_score_sorting_direction=Contest.DESCENDING,
        )
        assign_perm("display.change_contest", self.auth_user, self.contest)
        assign_perm("display.view_contest", self.auth_user, self.contest)
        self.team = Team.objects.create(
            crew=Crew.objects.create(
                member1=Person.objects.create(first_name="Pilot", last_name="Three", email="p3@example.com")
            ),
            aeroplane=Aeroplane.objects.create(registration="LN-RT3"),
        )
        self.task = Task.objects.create(
            contest=self.contest,
            name="rest-task",
            heading="REST Task",
            index=1,
            autosum_scores=True,
            summary_score_sorting_direction=Task.DESCENDING,
        )
        self.task_test = TaskTest.objects.create(
            task=self.task,
            name="rest-test",
            heading="REST Test",
            index=1,
            sorting=TaskTest.DESCENDING,
        )

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_update_test_result_endpoint_emits_score_update(self, safe_group_send):
        response = self.client.put(
            reverse("contests-update-test-result", kwargs={"pk": self.contest.pk}),
            data={"team": self.team.pk, "task_test": self.task_test.pk, "points": 17},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(safe_group_send.call_count, 1)
        group_name, payload = safe_group_send.call_args.args
        self.assertEqual(group_name, f"contestresults_{self.contest.pk}")
        self.assertEqual(payload["content"]["type"], "score.update")
        self.assertEqual(payload["content"]["test_score"]["points"], 17.0)
        self.assertEqual(payload["content"]["task_summary"]["points"], 17.0)
        self.assertEqual(payload["content"]["contest_summary"]["points"], 17.0)

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_update_task_summary_endpoint_emits_full_results_refresh(self, safe_group_send):
        response = self.client.put(
            reverse("contests-update-task-summary", kwargs={"pk": self.contest.pk}),
            data={"team": self.team.pk, "task": self.task.pk, "points": 23},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(safe_group_send.call_count, 1)
        group_name, payload = safe_group_send.call_args.args
        self.assertEqual(group_name, f"contestresults_{self.contest.pk}")
        self.assertEqual(payload["content"]["type"], "contest.results")
        matching_summary = next(summary for summary in payload["content"]["results"]["contestsummary_set"] if summary["team"]["id"] == self.team.pk)
        self.assertEqual(matching_summary["points"], 23.0)

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_update_contest_summary_endpoint_emits_full_results_refresh(self, safe_group_send):
        response = self.client.put(
            reverse("contests-update-contest-summary", kwargs={"pk": self.contest.pk}),
            data={"team": self.team.pk, "points": 31},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(safe_group_send.call_count, 1)
        group_name, payload = safe_group_send.call_args.args
        self.assertEqual(group_name, f"contestresults_{self.contest.pk}")
        self.assertEqual(payload["content"]["type"], "contest.results")
        matching_summary = next(summary for summary in payload["content"]["results"]["contestsummary_set"] if summary["team"]["id"] == self.team.pk)
        self.assertEqual(matching_summary["points"], 31.0)

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_task_reorder_update_via_api_emits_tasks_message(self, safe_group_send):
        response = self.client.put(
            reverse("tasks-detail", kwargs={"contest_pk": self.contest.pk, "pk": self.task.pk}),
            data={
                "id": self.task.pk,
                "contest": self.contest.pk,
                "name": self.task.name,
                "heading": self.task.heading,
                "weight": self.task.weight,
                "index": 5,
                "autosum_scores": self.task.autosum_scores,
                "summary_score_sorting_direction": self.task.summary_score_sorting_direction,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(safe_group_send.call_count, 1)
        group_name, payload = safe_group_send.call_args.args
        self.assertEqual(group_name, f"contestresults_{self.contest.pk}")
        self.assertEqual(payload["content"]["type"], "contest.tasks")
        matching_task = next(task for task in payload["content"]["tasks"] if task["id"] == self.task.pk)
        self.assertEqual(matching_task["index"], 5)

    @patch.object(WebsocketFacade, "_safe_group_send")
    def test_test_reorder_update_via_api_emits_full_results_refresh(self, safe_group_send):
        response = self.client.put(
            reverse("tasktests-detail", kwargs={"contest_pk": self.contest.pk, "pk": self.task_test.pk}),
            data={
                "id": self.task_test.pk,
                "task": self.task.pk,
                "name": self.task_test.name,
                "heading": self.task_test.heading,
                "weight": self.task_test.weight,
                "sorting": self.task_test.sorting,
                "index": 6,
                "navigation_task": None,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(safe_group_send.call_count, 1)
        group_name, payload = safe_group_send.call_args.args
        self.assertEqual(group_name, f"contestresults_{self.contest.pk}")
        self.assertEqual(payload["content"]["type"], "contest.results")
        matching_task = next(task for task in payload["content"]["results"]["task_set"] if task["id"] == self.task.pk)
        matching_test = next(test for test in matching_task["tasktest_set"] if test["id"] == self.task_test.pk)
        self.assertEqual(matching_test["index"], 6)
