import datetime

from unittest.mock import patch

import dateutil
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from guardian.shortcuts import assign_perm, remove_perm
from pprint import pprint
from rest_framework import status
from rest_framework.test import APITestCase

from display.convert_flightcontest_gpx import create_precision_route_from_csv
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, NavigationTask, Contest, Crew, Person, Team, ContestTeam, Contestant
from mock_utilities import TraccarMock


@patch("display.models.get_traccar_instance", return_value=TraccarMock)
class TestContestantGatesCalculation(APITestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, patch):
        with open("display/tests/NM.csv", "r") as file:
            self.route = create_precision_route_from_csv("navigation_task", file.readlines()[1:], True)
        self.navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        self.navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        self.scorecard = get_default_scorecard()
        self.contest = Contest.objects.create(name="contest", time_zone="Europe/Oslo",
                                              start_time=datetime.datetime.now(
                                                  datetime.timezone.utc),
                                              finish_time=datetime.datetime.now(
                                                  datetime.timezone.utc))
        self.navigation_task = NavigationTask.objects.create(name="NM navigation test",
                                                             scorecard=self.scorecard,
                                                             minutes_to_starting_point=5,
                                                             minutes_to_landing=20,
                                                             route=self.route, contest=self.contest,
                                                             start_time=self.navigation_task_start_time,
                                                             finish_time=self.navigation_task_finish_time,
                                                             allow_self_management=True)
        crew = Crew.objects.create(
            member1=Person.objects.create(first_name="Mister", last_name="Pilot", email="objectpermissions"))
        self.team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        self.contest_team = ContestTeam.objects.create(team=self.team, contest=self.contest, air_speed=70)

        self.user_owner = get_user_model().objects.create(email="objectpermissions")
        self.user_owner.user_permissions.add(
            Permission.objects.get(codename="add_contest"),
            Permission.objects.get(codename="change_contest"),
            Permission.objects.get(codename="delete_contest")
        )
        assign_perm("add_contest", self.user_owner, self.contest)
        assign_perm("view_contest", self.user_owner, self.contest)
        assign_perm("change_contest", self.user_owner, self.contest)
        assign_perm("delete_contest", self.user_owner, self.contest)

        self.user_someone_else = get_user_model().objects.create(email="withpermissions")

    def test_self_management_signup(self, p):
        self.client.force_login(user=self.user_owner)
        data = {
            "starting_point_time": "2021-05-13T09:00:00Z",
            "contest_team": self.contest_team.pk,
            "adaptive_start": False,
            "wind_speed": 5,
            "wind_direction": 170
        }
        url = reverse("navigationtasks-contestant-self-registration",
                      kwargs={'contest_pk': self.contest.id, 'pk': self.navigation_task.id})
        print(url)
        print(data)
        result = self.client.put(url, data=data, format="json")
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_201_CREATED)
        self.assertEqual(1, Contestant.objects.all().count())
        contestant = Contestant.objects.first()
        self.assertEqual(datetime.datetime(2021, 5, 13, 8, 55, tzinfo=datetime.timezone.utc), contestant.takeoff_time)
        self.assertEqual(datetime.datetime(2021, 5, 13, 10, 19, 52, 296336, tzinfo=datetime.timezone.utc),
                         contestant.finished_by_time)

    def test_self_management_signup_without_permissions(self, p):
        remove_perm("add_contest", self.user_owner, self.contest)
        remove_perm("view_contest", self.user_owner, self.contest)
        remove_perm("change_contest", self.user_owner, self.contest)
        remove_perm("delete_contest", self.user_owner, self.contest)

        self.client.force_login(user=self.user_owner)

        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.contest.is_public = True
        self.contest.save()
        data = {
            "starting_point_time": "2021-05-13T09:00:00Z",
            "contest_team": self.contest_team.pk,
            "adaptive_start": False,
            "wind_speed": 5,
            "wind_direction": 170
        }
        url = reverse("navigationtasks-contestant-self-registration",
                      kwargs={'contest_pk': self.contest.id, 'pk': self.navigation_task.id})
        print(url)
        print(data)
        result = self.client.put(url, data=data, format="json")
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_201_CREATED)
        self.assertEqual(1, Contestant.objects.all().count())
        contestant = Contestant.objects.first()
        self.assertEqual(datetime.datetime(2021, 5, 13, 8, 55, tzinfo=datetime.timezone.utc), contestant.takeoff_time)
        self.assertEqual(datetime.datetime(2021, 5, 13, 10, 19, 52, 296336, tzinfo=datetime.timezone.utc),
                         contestant.finished_by_time)

    def test_self_management_signup_not_available(self, p):
        self.navigation_task.allow_self_management = False
        self.navigation_task.save()
        self.client.force_login(user=self.user_owner)
        data = {
            "starting_point_time": "2021-05-13T09:00:00Z",
            "contest_team": self.contest_team.pk,
            "wind_speed": 5,
            "wind_direction": 170
        }
        url = reverse("navigationtasks-contestant-self-registration",
                      kwargs={'contest_pk': self.contest.id, 'pk': self.navigation_task.id})
        print(url)
        print(data)
        result = self.client.put(url, data=data, format="json")
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_403_FORBIDDEN)

    def test_self_management_signup_another_team(self, p):
        self.navigation_task.is_public = True
        self.navigation_task.save()

        self.client.force_login(user=self.user_someone_else)
        data = {
            "starting_point_time": "2021-05-13T09:00:00Z",
            "contest_team": self.contest_team.pk,
            "wind_speed": 5,
            "wind_direction": 170
        }
        url = reverse("navigationtasks-contestant-self-registration",
                      kwargs={'contest_pk': self.contest.id, 'pk': self.navigation_task.id})
        print(url)
        print(data)
        result = self.client.put(url, data=data, format="json")
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)

    def test_self_management_signup_not_signed_in(self, p):
        data = {
            "starting_point_time": "2021-05-13T09:00:00Z",
            "contest_team": self.contest_team.pk,
            "wind_speed": 5,
            "wind_direction": 170
        }
        url = reverse("navigationtasks-contestant-self-registration",
                      kwargs={'contest_pk': self.contest.id, 'pk': self.navigation_task.id})
        print(url)
        print(data)
        result = self.client.put(url, data=data, format="json")
        print(result)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_my_participation(self, p):
        with open("display/tests/NM.csv", "r") as file:
            route = create_precision_route_from_csv("navigation_task", file.readlines()[1:], True)
        self.contest.finish_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        self.contest.save()
        another_navigation_task = NavigationTask.objects.create(name="no self management",
                                                                scorecard=self.scorecard,
                                                                minutes_to_starting_point=5,
                                                                minutes_to_landing=20,
                                                                route=route, contest=self.contest,
                                                                start_time=self.navigation_task.start_time,
                                                                finish_time=self.navigation_task.finish_time,
                                                                allow_self_management=False)
        self.client.force_login(user=self.user_owner)
        start_time = datetime.datetime.now(datetime.timezone.utc)
        data = {
            "starting_point_time": start_time.isoformat(),
            "contest_team": self.contest_team.pk,
            "adaptive_start": False,
            "wind_speed": 5,
            "wind_direction": 170
        }
        url = reverse("navigationtasks-contestant-self-registration",
                      kwargs={'contest_pk': self.contest.id, 'pk': self.navigation_task.id})
        result = self.client.put(url, data=data, format="json")
        self.assertEqual(result.status_code, status.HTTP_201_CREATED)

        response = self.client.get("/api/v1/userprofile/my_participating_contests/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()[0]
        pprint(data)
        self.assertEqual(1, len(data["contest"]["navigationtask_set"]))
        self.assertEqual("NM navigation test", data["contest"]["navigationtask_set"][0]["name"])
        self.assertEqual(1, len(data["contest"]["navigationtask_set"][0]["future_contestants"]))
        self.assertEqual((start_time - datetime.timedelta(minutes=self.navigation_task.minutes_to_starting_point)),
                         dateutil.parser.parse(
                             data["contest"]["navigationtask_set"][0]["future_contestants"][0]["takeoff_time"]))
