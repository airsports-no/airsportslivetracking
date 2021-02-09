import datetime
from pprint import pprint
from unittest.mock import patch

from django.contrib.auth.models import User, Permission
from django.contrib.auth import get_user_model

from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.models import Contest, Aeroplane, Person, Crew, Team, Task, TaskTest, ContestSummary, TaskSummary, \
    TeamTestScore

@patch("display.models.get_traccar_instance")
class TestTaskResultsApi(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="test")
        permission = Permission.objects.get(codename="change_contest")
        self.user.user_permissions.add(permission)
        self.client.force_login(user=self.user)
        self.contest = Contest.objects.create(name="NM 2020", start_time=datetime.datetime.now(datetime.timezone.utc),
                                              finish_time=datetime.datetime.now(datetime.timezone.utc))
        assign_perm("display.change_contest", self.user, self.contest)
        assign_perm("display.view_contest", self.user, self.contest)
        self.aeroplane = Aeroplane.objects.create(registration="test")

    def test_put_task(self, p):

        contestants = {
            "Anders": {
                "planning": 8,
                "navigation": 373,
                "observation": 320,
                "landing_one": 70,
                "landing_two": 200,
                "landing_three": 3,
                "landing_four": 246,
                "navigation_summary": 701,
                "landing_summary": 498,
                "summary": 947
            },
            "Arild": {
                "planning": 22,
                "navigation": 813,
                "observation": 420,
                "landing_one": 300,
                "landing_two": 200,
                "landing_three": 200,
                "landing_four": 30,
                "navigation_summary": 1255,
                "landing_summary": 370,
                "summary": 1620
            },
        }
        task_tests = {
            "navigation": (["planning", "navigation", "observation"], "navigation_summary"),
            "landing": (["landing_one", "landing_two", "landing_three", "landing_four"], "landing_summary")
        }
        for task, data in task_tests.items():
            task_data = {
                "name": task,
                "heading": task.upper(),
                "tasksummary_set": [],
                "tasktest_set": []
            }
            tests, summary = data
            for contestant_name, scores in contestants.items():
                pilot = Person.get_or_create(contestant_name, "Pilot", None, None)
                crew, _ = Crew.objects.get_or_create(member1=pilot)
                team, _ = Team.objects.get_or_create(crew=crew, aeroplane=self.aeroplane)
                task_data["tasksummary_set"].append({"team": team.pk, "points": scores[summary]})
            for index, test in enumerate(tests):
                test_results = []
                for contestant_name, scores in contestants.items():
                    pilot = Person.get_or_create(contestant_name, "Pilot", None, None)
                    crew, _ = Crew.objects.get_or_create(member1=pilot)
                    team, _ = Team.objects.get_or_create(crew=crew, aeroplane=self.aeroplane)
                    test_results.append({
                        "team": team.pk,
                        "points": scores[test]
                    })
                task_data["tasktest_set"].append({
                    "name": test,
                    "heading": test.upper(),
                    "teamtestscore_set": test_results,
                    "index": index
                })
            pprint(task_data)
            response = self.client.put("/api/v1/contests/{}/task_results/".format(self.contest.pk), data=task_data,
                                       format="json")
            print(response.content)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Check tasks
        self.assertTrue(Task.objects.filter(name="navigation").exists())
        self.assertTrue(Task.objects.filter(name="landing").exists())
        # Check tests
        navigation_task = Task.objects.get(name="navigation")
        self.assertTrue(TaskTest.objects.filter(task=navigation_task, name="planning").exists())
        self.assertTrue(TaskTest.objects.filter(task=navigation_task, name="navigation").exists())
        self.assertTrue(TaskTest.objects.filter(task=navigation_task, name="observation").exists())
        landing_task = Task.objects.get(name="landing")
        self.assertTrue(TaskTest.objects.filter(task=landing_task, name="landing_one").exists())
        self.assertTrue(TaskTest.objects.filter(task=landing_task, name="landing_two").exists())
        self.assertTrue(TaskTest.objects.filter(task=landing_task, name="landing_three").exists())
        self.assertTrue(TaskTest.objects.filter(task=landing_task, name="landing_four").exists())
        # Check results
        self.assertEqual(2, Team.objects.all().count())
        first_team = Team.objects.get(crew__member1__first_name="Anders")
        # There is no contest summary, just for the tasks
        # self.assertEqual(947, ContestSummary.objects.get(team=first_team, contest=self.contest).points)
        self.assertEqual(498, TaskSummary.objects.get(team=first_team, task=landing_task).points)
        self.assertEqual(701, TaskSummary.objects.get(team=first_team, task=navigation_task).points)
        self.assertEqual(8, TeamTestScore.objects.get(team=first_team, task_test__name="planning").points)
        self.assertEqual(373, TeamTestScore.objects.get(team=first_team, task_test__name="navigation").points)
        self.assertEqual(320, TeamTestScore.objects.get(team=first_team, task_test__name="observation").points)

        self.assertEqual(70, TeamTestScore.objects.get(team=first_team, task_test__name="landing_one").points)
        self.assertEqual(200, TeamTestScore.objects.get(team=first_team, task_test__name="landing_two").points)
        self.assertEqual(3, TeamTestScore.objects.get(team=first_team, task_test__name="landing_three").points)
        self.assertEqual(246, TeamTestScore.objects.get(team=first_team, task_test__name="landing_four").points)

    def test_overwrite_task_results(self, p):
        another_contest = Contest.objects.create(name="another NM 2020", start_time=datetime.datetime.now(datetime.timezone.utc),
                                                 finish_time=datetime.datetime.now(datetime.timezone.utc))
        assign_perm("display.change_contest", self.user, another_contest)
        assign_perm("display.view_contest", self.user, another_contest)
        pilot = Person.get_or_create("Pilot", "Pilot", None, None)
        crew, _ = Crew.objects.get_or_create(member1=pilot)
        team, _ = Team.objects.get_or_create(crew=crew, aeroplane=self.aeroplane)
        Task.objects.all().delete()
        another_task = Task.objects.create(contest=another_contest, name="another_task", heading="heading")
        task_data = {
            "name": "navigation",
            "heading": "heading",
            "tasksummary_set": [
                {
                    "team": team.pk,
                    "points": 1
                }
            ],
            "tasktest_set": [
                {
                    "heading": "heading",
                    "name": "test",
                    "index": 0,
                    "teamtestscore_set": [
                        {
                            "points": 1,
                            "team": team.pk
                        }
                    ]
                }
            ]
        }
        response = self.client.put("/api/v1/contests/{}/task_results/".format(self.contest.pk), data=task_data,
                                   format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(2, Task.objects.all().count())
        self.assertEqual(1, TeamTestScore.objects.all().count())
        self.assertEqual(1, TeamTestScore.objects.first().points)
        self.assertEqual(1, TaskSummary.objects.all().count())
        self.assertEqual(1, TaskSummary.objects.first().points)
        # Overwriting the data
        task_data["tasksummary_set"][0]["points"] = 2
        task_data["tasktest_set"][0]["teamtestscore_set"][0]["points"] = 3
        response = self.client.put("/api/v1/contests/{}/task_results/".format(self.contest.pk), data=task_data,
                                   format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(2, Task.objects.all().count())
        self.assertEqual(1, TeamTestScore.objects.all().count())
        self.assertEqual(3, TeamTestScore.objects.first().points)
        self.assertEqual(1, TaskSummary.objects.all().count())
        self.assertEqual(2, TaskSummary.objects.first().points)

    def test_delete_task_results(self, p):
        pilot = Person.get_or_create("Pilot", "Pilot", None, None)
        crew, _ = Crew.objects.get_or_create(member1=pilot)
        team, _ = Team.objects.get_or_create(crew=crew, aeroplane=self.aeroplane)
        Task.objects.all().delete()

        task_data = {
            "name": "navigation",
            "heading": "heading",
            "tasksummary_set": [
                {
                    "team": team.pk,
                    "points": 1
                }
            ],
            "tasktest_set": [
                {
                    "heading": "heading",
                    "name": "test",
                    "index": 0,
                    "teamtestscore_set": [
                        {
                            "points": 1,
                            "team": team.pk
                        }
                    ]
                }
            ]
        }

        response = self.client.put("/api/v1/contests/{}/task_results/".format(self.contest.pk), data=task_data,
                                   format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        Task.objects.create(contest=self.contest, name="extra", heading="heading")
        response = self.client.delete("/api/v1/contests/{}/all_task_results/".format(self.contest.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(0, Task.objects.all().count())
        self.assertEqual(0, TaskSummary.objects.all().count())
        self.assertEqual(0, TaskTest.objects.all().count())
        self.assertEqual(0, TeamTestScore.objects.all().count())

    def test_post_contest_summary(self, p):
        pilot = Person.get_or_create("Pilot", "Pilot", None, None)
        pilot2 = Person.get_or_create("Pilot2", "Pilot", None, None)
        crew, _ = Crew.objects.get_or_create(member1=pilot)
        crew2, _ = Crew.objects.get_or_create(member1=pilot2)
        team, _ = Team.objects.get_or_create(crew=crew, aeroplane=self.aeroplane)
        team2, _ = Team.objects.get_or_create(crew=crew2, aeroplane=self.aeroplane)
        summary_data = [
            {
                "team": team.pk,
                "points": 1
            },
            {
                "team": team2.pk,
                "points": 2
            }
        ]
        response = self.client.post("/api/v1/contests/{}/contest_summary_results/".format(self.contest.pk),
                                    data=summary_data,
                                    format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(2, ContestSummary.objects.all().count())
        self.assertEqual(1, ContestSummary.objects.get(team=team).points)
        self.assertEqual(2, ContestSummary.objects.get(team=team2).points)

    def test_delete_contest_summary(self, p):
        pilot = Person.get_or_create("Pilot", "Pilot", None, None)
        crew, _ = Crew.objects.get_or_create(member1=pilot)
        team, _ = Team.objects.get_or_create(crew=crew, aeroplane=self.aeroplane)
        summary_data = [
            {
                "team": team.pk,
                "points": 1
            }
        ]
        response = self.client.post("/api/v1/contests/{}/contest_summary_results/".format(self.contest.pk),
                                    data=summary_data,
                                    format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(1, ContestSummary.objects.all().count())
        response = self.client.delete("/api/v1/contests/{}/contest_summary_results/".format(self.contest.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(0, ContestSummary.objects.all().count())
