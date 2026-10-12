import datetime
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    Contest,
    ContestAnnouncement,
    ContestTeam,
    Contestant,
    ContestantTrack,
    Crew,
    EmailMapLink,
    MobileDevice,
    NavigationTask,
    Person,
    PushNotificationLog,
    Route,
    Team,
)
from display.models.my_user import MyUser
from display.services import push_notifications
from display.services.announcements import announcements_for, recipients
from display.utilities.tracking_definitions import TRACKING_PILOT
from utilities.mock_utilities import TraccarMock


class Base(TestCase):
    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(name="Cup", start_time=self.now, finish_time=self.now, is_public=True)
        self.task = self.make_task("Day 1")
        self.other_task = self.make_task("Day 2")
        self.pilot = Person.objects.create(first_name="Pi", last_name="Lot", email="pilot@example.com")
        self.other = Person.objects.create(first_name="Ot", last_name="Her", email="other@example.com")
        self.team = self.make_team(self.pilot, "LN-A")
        self.other_team = self.make_team(self.other, "LN-B")
        self.contestant = self.make_contestant(self.team, self.task, 1)
        self.make_contestant(self.other_team, self.other_task, 2)

    def make_task(self, name):
        return NavigationTask.create(
            name=name,
            original_scorecard=get_default_scorecard(),
            start_time=self.now,
            finish_time=self.now + datetime.timedelta(hours=3),
            route=Route.objects.create(name="Route " + name),
            contest=self.contest,
            is_public=True,
        )

    def make_team(self, person, registration):
        team = Team.objects.create(crew=Crew.objects.create(member1=person), aeroplane=Aeroplane.objects.create(registration=registration))
        ContestTeam.objects.create(contest=self.contest, team=team)
        return team

    def make_contestant(self, team, task, number):
        return Contestant.objects.create(
            team=team,
            navigation_task=task,
            tracking_device=TRACKING_PILOT,
            contestant_number=number,
            tracker_start_time=self.now - datetime.timedelta(minutes=5),
            takeoff_time=self.now + datetime.timedelta(minutes=5),
            finished_by_time=self.now + datetime.timedelta(hours=2),
        )


class TestAnnouncements(Base):
    def setUp(self):
        super().setUp()
        self.organizer = MyUser.objects.create(username="org", email="org@example.com")
        self.pilot_user = MyUser.objects.create(username="pilot", email="pilot@example.com")
        self.client = APIClient()

    def test_a_task_announcement_goes_to_that_tasks_crews_and_a_contest_one_to_everybody(self):
        self.assertEqual({p.pk for p in recipients(self.contest, self.task)}, {self.pilot.pk})
        self.assertEqual({p.pk for p in recipients(self.contest)}, {self.pilot.pk, self.other.pk})

    def test_the_app_lists_the_announcements_that_concern_the_pilot_and_have_not_expired(self):
        ContestAnnouncement.objects.create(contest=self.contest, message="Briefing 08:30")
        ContestAnnouncement.objects.create(contest=self.contest, navigation_task=self.other_task, message="Only day 2")
        old = ContestAnnouncement.objects.create(contest=self.contest, message="Old news")
        ContestAnnouncement.objects.filter(pk=old.pk).update(created_at=self.now - datetime.timedelta(hours=30))
        self.assertEqual([a.message for a in announcements_for(self.pilot)], ["Briefing 08:30"])

    def test_the_endpoint_lists_them_for_the_signed_in_pilot(self):
        ContestAnnouncement.objects.create(contest=self.contest, message="Briefing 08:30")
        self.client.force_authenticate(self.pilot_user)
        response = self.client.get("/api/v1/userprofile/announcements/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([(a["message"], a["contest_name"], a["task_name"]) for a in response.json()], [("Briefing 08:30", "Cup", None)])

    def test_only_a_contest_editor_may_announce_and_the_message_is_checked(self):
        self.client.force_authenticate(self.pilot_user)
        denied = self.client.post(f"/api/v1/contests/{self.contest.pk}/announce/", {"message": "Hi"}, format="json")
        self.assertIn(denied.status_code, (403, 404))
        self.assertFalse(ContestAnnouncement.objects.exists())

        from guardian.shortcuts import assign_perm

        for permission in ("change_contest", "view_contest"):
            assign_perm(permission, self.organizer, self.contest)
        self.client.force_authenticate(self.organizer)
        self.assertEqual(self.client.post(f"/api/v1/contests/{self.contest.pk}/announce/", {"message": " "}, format="json").status_code, 400)
        other_contest = Contest.objects.create(name="Other", start_time=self.now, finish_time=self.now)
        foreign_task = NavigationTask.create(
            name="X", original_scorecard=get_default_scorecard(), start_time=self.now, finish_time=self.now,
            route=Route.objects.create(name="R"), contest=other_contest,
        )
        bad = self.client.post(f"/api/v1/contests/{self.contest.pk}/announce/", {"message": "Hi", "navigation_task": foreign_task.pk}, format="json")
        self.assertEqual(bad.status_code, 400)

        MobileDevice.objects.create(person=self.pilot, platform="android", push_token="tok")
        with override_settings(PUSH_NOTIFICATIONS_ENABLED=True), patch("display.services.push_notifications._send_one", return_value=True) as send:
            ok = self.client.post(f"/api/v1/contests/{self.contest.pk}/announce/", {"message": "Briefing 08:30"}, format="json")
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ok.json()["people_reached"], 1)
        title, body, data = send.call_args.args[1:4]
        self.assertEqual((title, body, data["type"]), ("Cup", "Briefing 08:30", "announcement"))
        self.assertEqual(ContestAnnouncement.objects.get().created_by, self.organizer)


class TestScoreAndFlightOrderInNowEndpoint(Base):
    def setUp(self):
        super().setUp()
        self.user = MyUser.objects.create(username="p", email="pilot@example.com")
        self.pilot.app_tracking_id = "pilot-device-score"
        self.pilot.save()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def current(self):
        response = self.client.get("/api/v1/userprofile/get_current_app_navigation_task/")
        self.assertEqual(response.status_code, 200)
        return response.json()[0]["active_contestants"][0]

    def test_the_score_shows_where_results_are_visible_and_is_held_back_otherwise(self):
        ContestantTrack.objects.filter(contestant=self.contestant).update(score=42)
        self.assertEqual(self.current()["score"], 42)
        self.task.calculation_delay_minutes = 5
        self.task.save()
        self.assertIsNone(self.current()["score"], "held back while the flight is on")
        # Once the flight is over and the hold-back has passed the score is released (the Now endpoint no longer lists the
        # flight by then, so this is checked on the rule itself).
        from display.viewsets import own_score_for

        Contestant.objects.filter(pk=self.contestant.pk).update(finished_by_time=self.now - datetime.timedelta(minutes=10))
        self.contestant.refresh_from_db()
        self.assertEqual(own_score_for(self.contestant, self.task, True), 42)
        Contestant.objects.filter(pk=self.contestant.pk).update(finished_by_time=self.now - datetime.timedelta(minutes=3))
        self.contestant.refresh_from_db()
        self.assertIsNone(own_score_for(self.contestant, self.task, True), "5 minute hold-back not over yet")
        Contestant.objects.filter(pk=self.contestant.pk).update(finished_by_time=self.now + datetime.timedelta(hours=2))
        self.task.calculation_delay_minutes = 0
        self.task.is_public = False
        self.task.save()
        self.assertIsNone(self.current()["score"], "a private task the pilot may not view")

    def test_the_newest_generated_flight_order_is_offered(self):
        self.assertIsNone(self.current()["flight_order_path"])
        older = EmailMapLink.objects.create(contestant=self.contestant, orders=b"%PDF-1")
        newer = EmailMapLink.objects.create(contestant=self.contestant, orders=b"%PDF-2")
        self.assertEqual(self.current()["flight_order_path"], f"/display/maplink/{newer.pk}/")
        self.assertNotEqual(older.pk, newer.pk)


    def test_the_flights_lists_offer_the_newest_flight_order_too(self):
        EmailMapLink.objects.create(contestant=self.contestant, orders=b"%PDF-1")
        newest = EmailMapLink.objects.create(contestant=self.contestant, orders=b"%PDF-2")
        flights = self.client.get("/api/v1/userprofile/my_future_flights/").json()
        self.assertEqual(flights[0]["flight_order_path"], f"/display/maplink/{newest.pk}/")
        no_orders = EmailMapLink.objects.filter(contestant=self.contestant)
        no_orders.delete()
        self.assertIsNone(self.client.get("/api/v1/userprofile/my_future_flights/").json()[0]["flight_order_path"])


class TestFlightScoredPush(Base):
    def setUp(self):
        super().setUp()
        MobileDevice.objects.create(person=self.pilot, platform="android", push_token="tok")
        MyUser.objects.create(username="p", email="pilot@example.com")
        send = patch("display.services.push_notifications._send_one", return_value=True)
        self.send = send.start()
        self.addCleanup(send.stop)
        settings_patch = override_settings(PUSH_NOTIFICATIONS_ENABLED=True)
        settings_patch.enable()
        self.addCleanup(settings_patch.disable)

    def finish(self, score=17.5, ended_minutes_ago=10):
        Contestant.objects.filter(pk=self.contestant.pk).update(
            finished_by_time=self.now - datetime.timedelta(minutes=ended_minutes_ago)
        )
        ContestantTrack.objects.filter(contestant=self.contestant).update(calculator_finished=True, score=score)

    def test_tells_the_pilot_once_when_live_scoring_has_finished(self):
        self.assertEqual(push_notifications.notify_flight_scored(self.now), 0)  # not finished yet
        self.finish()
        self.assertEqual(push_notifications.notify_flight_scored(self.now), 1)
        self.assertEqual(push_notifications.notify_flight_scored(self.now), 0)
        title, body, data = self.send.call_args.args[1:4]
        self.assertEqual((title, data["type"]), ("Live scoring has finished", "flight_scored"))
        self.assertIn("17.5 points", body)
        self.assertIn("can still adjust", body)
        self.assertEqual(PushNotificationLog.objects.get().kind, "flight_scored")

    def test_waits_a_short_settling_time_after_the_finish(self):
        self.finish(ended_minutes_ago=1)  # the photo observations are scored just after the calculator finishes
        self.assertEqual(push_notifications.notify_flight_scored(self.now), 0)
        self.assertEqual(push_notifications.notify_flight_scored(self.now + datetime.timedelta(minutes=2)), 1)

    def test_waits_for_the_calculation_delay_before_telling_the_pilot(self):
        self.task.calculation_delay_minutes = 10
        self.task.save()
        self.finish(ended_minutes_ago=5)
        self.assertEqual(push_notifications.notify_flight_scored(self.now), 0, "the results are still held back")
        self.send.assert_not_called()
        # 10 minutes of hold-back plus the settling time have passed since the finish.
        self.assertEqual(push_notifications.notify_flight_scored(self.now + datetime.timedelta(minutes=8)), 1)

    def test_not_when_the_results_are_not_the_pilots_to_see(self):
        self.finish()
        self.task.is_public = False
        self.task.save()
        self.assertEqual(push_notifications.notify_flight_scored(self.now), 0)
        self.send.assert_not_called()
