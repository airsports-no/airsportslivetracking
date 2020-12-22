import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.forms import ContestantForm
from display.models import Person, Contest, Route, NavigationTask, Crew, Aeroplane, Team


class TestContestantForm(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="test", is_superuser=True)
        self.contest = Contest.objects.create(name="TestContest", start_time=datetime.datetime.utcnow(),
                                              finish_time=datetime.datetime.utcnow())
        route = Route.objects.create(name="Route")
        self.navigation_task = NavigationTask.objects.create(name="NavigationTask",
                                                             start_time=datetime.datetime.utcnow(),
                                                             finish_time=datetime.datetime.utcnow(),
                                                             route=route, contest=self.contest)

        self.data = {
            "pilot_first_name": "pilot_first",
            "pilot_last_name": "pilot_last",
            "pilot_phone": "+4773215330",
            "pilot_email": "rxdtcfyvgbhjn@hgbjk.com",

            "copilot_first_name": "copilot_first",
            "copilot_last_name": "copilot_last",
            "copilot_phone": "+4773215328",
            "copilot_email": "lknlkb@kjbh.com",

            "aircraft_registration": "LN-YDB",

            "contestant_number": 0,
            "tracker_start_time": datetime.datetime.utcnow(),
            "traccar_device_name": "cfjgvhk",
            "tracking_service": "traccar",
            "takeoff_time": datetime.datetime.utcnow(),
            "finished_by_time": datetime.datetime.utcnow(),
            "minutes_to_starting_point": 3,
            "air_speed": 3,
            "wind_direction": 0,
            "wind_speed": 1,
            "scorecard": get_default_scorecard().pk
        }

    def test_form_validation(self):
        form = ContestantForm(data=self.data)
        for key, value in form.errors.items():
            print("{}: {}".format(key, value))
        self.assertTrue(form.is_valid())

    def test_email_validation(self):
        self.data["pilot_email"] = "invalid"
        self.data["copilot_email"] = "invalid"
        form = ContestantForm(data=self.data)
        self.assertEqual(form.errors["pilot_email"], ['Enter a valid email address.'])
        self.assertEqual(form.errors["copilot_email"], ['Enter a valid email address.'])

    def test_different_nonexisting_persons(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("contestant_create", kwargs={"navigationtask_pk": self.navigation_task.pk}),
                                    data=self.data)
        print(response.content)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(2, Person.objects.all().count())

    def test_preexisting_phone_numbers(self):
        person = Person.objects.create(first_name="first", last_name="last", phone="+4773215338")
        self.data["pilot_phone"] = "+4773215338"
        self.data["copilot_phone"] = "+4773215338"
        self.client.force_login(self.user)
        response = self.client.post(reverse("contestant_create", kwargs={"navigationtask_pk": self.navigation_task.pk}),
                                    data=self.data)
        print(response.content)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(1, Person.objects.all().count())
        self.assertEqual(person, Person.objects.first())

    def test_preexisting_email(self):
        person = Person.objects.create(first_name="first", last_name="last", email="tt@ta.com")
        self.data["pilot_email"] = "tt@ta.com"
        self.data["copilot_email"] = "tt@ta.com"
        self.client.force_login(self.user)
        response = self.client.post(reverse("contestant_create", kwargs={"navigationtask_pk": self.navigation_task.pk}),
                                    data=self.data)
        print(response.content)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(1, Person.objects.all().count())
        self.assertEqual(person, Person.objects.first())

    def test_preexisting_crewand_missing_copilot(self):
        person = Person.objects.create(first_name="first", last_name="last", email="tt@ta.com")
        crew = Crew.objects.create(member1=person)
        self.data["pilot_email"] = "tt@ta.com"
        self.data["copilot_email"] = ""
        self.data["copilot_phone"] = ""
        self.data["copilot_first_name"] = ""
        self.data["copilot_last_name"] = ""

        self.client.force_login(self.user)
        response = self.client.post(reverse("contestant_create", kwargs={"navigationtask_pk": self.navigation_task.pk}),
                                    data=self.data)
        print(response.content)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(1, Person.objects.all().count())
        self.assertEqual(person, Person.objects.first())
        self.assertEqual(1, Crew.objects.all().count())
        self.assertEqual(crew, Crew.objects.first())

    def test_preexisting_team(self):
        person = Person.objects.create(first_name="first", last_name="last", email="tt@ta.com")
        crew = Crew.objects.create(member1=person)
        aircraft = Aeroplane.objects.create(registration="LN-YDB")
        team = Team.objects.create(crew=crew, aeroplane=aircraft)
        self.data["pilot_email"] = "tt@ta.com"
        self.data["copilot_email"] = ""
        self.data["copilot_phone"] = ""
        self.data["copilot_first_name"] = ""
        self.data["copilot_last_name"] = ""

        self.client.force_login(self.user)
        response = self.client.post(reverse("contestant_create", kwargs={"navigationtask_pk": self.navigation_task.pk}),
                                    data=self.data)
        print(response.content)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(1, Person.objects.all().count())
        self.assertEqual(person, Person.objects.first())
        self.assertEqual(1, Crew.objects.all().count())
        self.assertEqual(crew, Crew.objects.first())
        self.assertEqual(1, Team.objects.all().count())
        self.assertEqual(team, Team.objects.first())
