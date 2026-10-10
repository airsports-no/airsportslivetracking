import datetime
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    ContestantReceivedPosition,
    Crew,
    MobileDevice,
    NavigationTask,
    Person,
    PushNotificationLog,
    Route,
    Team,
)
from display.models.my_user import MyUser
from display.services import push_notifications
from display.utilities.tracking_definitions import TRACKING_DEVICE, TRACKING_PILOT
from utilities.mock_utilities import TraccarMock


class TestMobileConfig(TestCase):
    def test_is_public_and_cacheable(self):
        response = self.client.get("/api/v1/mobile/config/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("public", response["Cache-Control"])
        body = response.json()
        self.assertEqual(body["tracking"]["interval_ms"], 1000)
        self.assertIn("play.google.com", body["android"]["store_url"])
        self.assertIn("apps.apple.com", body["ios"]["store_url"])

    @override_settings(MOBILE_ANDROID_MIN_VERSION=120, MOBILE_ANDROID_LATEST_VERSION=130, MOBILE_IOS_MIN_VERSION=5)
    def test_versions_come_from_settings(self):
        body = self.client.get("/api/v1/mobile/config/").json()
        self.assertEqual((body["android"]["min_version"], body["android"]["latest_version"]), (120, 130))
        self.assertEqual(body["ios"]["min_version"], 5)


class TestMobileTime(TestCase):
    def test_returns_the_server_clock_uncached(self):
        import time

        before = int(time.time() * 1000)
        response = self.client.get("/api/v1/mobile/time/")
        after = int(time.time() * 1000)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(before <= response.json()["epoch_ms"] <= after)
        self.assertIn("no-store", response["Cache-Control"])


class TestDeviceRegistration(TestCase):
    def setUp(self):
        patcher = patch("display.signals.get_traccar_instance", return_value=TraccarMock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = MyUser.objects.create(username="a", email="a@example.com")
        self.person = Person.objects.create(first_name="A", last_name="A", email="a@example.com")
        self.other = Person.objects.create(first_name="B", last_name="B", email="b@example.com")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def register(self, **body):
        body = {"platform": "android", "push_token": "tok-1", "app_version": "100", **body}
        return self.client.post("/api/v1/userprofile/register_device/", body, format="json")

    def test_registers_and_refreshes_a_token(self):
        self.assertEqual(self.register().status_code, 204)
        self.assertEqual(self.register(app_version="101").status_code, 204)
        device = MobileDevice.objects.get()
        self.assertEqual((device.person, device.platform, device.app_version), (self.person, "android", "101"))

    def test_token_moves_to_the_person_who_signs_in_on_the_phone(self):
        MobileDevice.objects.create(person=self.other, platform="android", push_token="tok-1")
        self.register()
        self.assertEqual(MobileDevice.objects.get().person, self.person)

    def test_rejects_bad_platform_and_empty_token(self):
        self.assertEqual(self.register(platform="windows").status_code, 400)
        self.assertEqual(self.register(push_token=" ").status_code, 400)
        self.assertFalse(MobileDevice.objects.exists())

    def test_unregister_only_removes_own_tokens(self):
        MobileDevice.objects.create(person=self.person, platform="android", push_token="mine")
        MobileDevice.objects.create(person=self.other, platform="android", push_token="theirs")
        for token in ("mine", "theirs"):
            self.client.post("/api/v1/userprofile/unregister_device/", {"push_token": token}, format="json")
        self.assertEqual(list(MobileDevice.objects.values_list("push_token", flat=True)), ["theirs"])


@override_settings(PUSH_NOTIFICATIONS_ENABLED=True)
class TestPushNotifications(TransactionTestCase):
    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        send = patch("display.services.push_notifications._send_one", return_value=True)
        self.send = send.start()
        self.addCleanup(send.stop)

        self.now = datetime.datetime(2026, 10, 10, 12, 0, tzinfo=datetime.timezone.utc)
        contest = Contest.objects.create(name="Cup", start_time=self.now, finish_time=self.now)
        self.task = NavigationTask.create(
            name="Day 1",
            original_scorecard=get_default_scorecard(),
            start_time=self.now,
            finish_time=self.now + datetime.timedelta(hours=3),
            route=Route.objects.create(name="Route"),
            contest=contest,
        )
        self.pilot = Person.objects.create(first_name="Pi", last_name="Lot", email="pilot@example.com")
        MobileDevice.objects.create(person=self.pilot, platform="android", push_token="tok")
        self.team = Team.objects.create(crew=Crew.objects.create(member1=self.pilot), aeroplane=Aeroplane.objects.create(registration="LN-X"))

    def contestant(self, start_in_min=10, takeoff_in_min=20, device=TRACKING_PILOT, number=1):
        return Contestant.objects.create(
            team=self.team,
            navigation_task=self.task,
            tracking_device=device,
            tracker_device_id="hw" if device == TRACKING_DEVICE else "",
            contestant_number=number,
            tracker_start_time=self.now + datetime.timedelta(minutes=start_in_min),
            takeoff_time=self.now + datetime.timedelta(minutes=takeoff_in_min),
            finished_by_time=self.now + datetime.timedelta(hours=2),
        )

    def test_reminds_once_before_the_tracking_window(self):
        contestant = self.contestant(start_in_min=10)
        self.assertEqual(push_notifications.notify_upcoming_tracking_windows(self.now), 1)
        self.assertEqual(push_notifications.notify_upcoming_tracking_windows(self.now), 0)
        self.send.assert_called_once()
        device, title, body, data = self.send.call_args.args
        self.assertEqual(device.push_token, "tok")
        self.assertIn("Day 1", body)
        self.assertEqual(data["type"], "tracking_window_opens")
        self.assertEqual(data["contestant_id"], str(contestant.pk))
        log = PushNotificationLog.objects.get()
        self.assertEqual((log.person, log.devices_reached), (self.pilot, 1))

    def test_ignores_windows_outside_the_lead_time_and_hardware_trackers(self):
        self.contestant(start_in_min=45, takeoff_in_min=60, number=1)
        self.contestant(start_in_min=10, device=TRACKING_DEVICE, number=2)
        self.assertEqual(push_notifications.notify_upcoming_tracking_windows(self.now), 0)
        self.send.assert_not_called()

    def test_people_without_a_registered_phone_are_skipped(self):
        MobileDevice.objects.all().delete()
        self.contestant(start_in_min=10)
        self.assertEqual(push_notifications.notify_upcoming_tracking_windows(self.now), 0)
        self.assertFalse(PushNotificationLog.objects.exists())

    def test_nothing_is_sent_while_the_feature_flag_is_off(self):
        self.contestant(start_in_min=10)
        with override_settings(PUSH_NOTIFICATIONS_ENABLED=False):
            self.assertEqual(push_notifications.notify_upcoming_tracking_windows(self.now), 0)
            self.assertEqual(push_notifications.notify_not_tracking(self.now), 0)
        self.send.assert_not_called()

    def test_warns_when_the_flight_started_without_positions(self):
        contestant = self.contestant(start_in_min=-30, takeoff_in_min=-10)
        self.assertEqual(push_notifications.notify_not_tracking(self.now), 1)
        self.assertEqual(push_notifications.notify_not_tracking(self.now), 0)
        self.assertEqual(self.send.call_args.args[3]["type"], "not_tracking")
        self.assertEqual(self.send.call_args.args[3]["contestant_id"], str(contestant.pk))

    def test_no_warning_when_positions_arrive_or_take_off_is_recent(self):
        arrived = self.contestant(start_in_min=-30, takeoff_in_min=-10, number=1)
        ContestantReceivedPosition.objects.create(contestant=arrived, time=self.now, latitude=1, longitude=1)
        self.contestant(start_in_min=-5, takeoff_in_min=-1, number=2)  # inside the grace period
        self.assertEqual(push_notifications.notify_not_tracking(self.now), 0)

    def test_confirms_once_the_calculator_has_been_started_by_positions(self):
        from display.models import ContestantTrack

        started = self.contestant(start_in_min=-30, takeoff_in_min=-10, number=1)
        ContestantTrack.objects.filter(contestant=started).update(calculator_started=True)
        waiting = self.contestant(start_in_min=-30, takeoff_in_min=-10, number=2)  # calculator never started
        done = self.contestant(start_in_min=-30, takeoff_in_min=-10, number=3)
        ContestantTrack.objects.filter(contestant=done).update(calculator_started=True, calculator_finished=True)

        self.assertEqual(push_notifications.notify_scoring_started(self.now), 1)
        self.assertEqual(push_notifications.notify_scoring_started(self.now), 0)
        data = self.send.call_args.args[3]
        self.assertEqual((data["type"], data["contestant_id"]), ("scoring_started", str(started.pk)))
        self.assertNotEqual(data["contestant_id"], str(waiting.pk))


class TestSendOne(TestCase):
    def setUp(self):
        patcher = patch("display.signals.get_traccar_instance", return_value=TraccarMock)
        patcher.start()
        self.addCleanup(patcher.stop)
        init = patch("display.auth_backends.FirebaseMigrationBackend._initialize_firebase")
        init.start()
        self.addCleanup(init.stop)
        person = Person.objects.create(first_name="A", last_name="A", email="a@example.com")
        self.device = MobileDevice.objects.create(person=person, platform="android", push_token="tok")

    def test_builds_a_high_priority_message_on_the_reminder_channel(self):
        with patch("firebase_admin.messaging.send") as send:
            self.assertTrue(push_notifications._send_one(self.device, "Title", "Body", {"contestant_id": 5}))
        message = send.call_args.args[0]
        self.assertEqual(message.token, "tok")
        self.assertEqual((message.notification.title, message.notification.body), ("Title", "Body"))
        self.assertEqual(message.data, {"contestant_id": "5"})
        self.assertEqual(message.android.priority, "high")
        self.assertEqual(message.android.notification.channel_id, "flight_reminders")

    def test_dead_token_is_deleted(self):
        from firebase_admin import messaging

        with patch("firebase_admin.messaging.send", side_effect=messaging.UnregisteredError("gone")):
            self.assertFalse(push_notifications._send_one(self.device, "T", "B", {}))
        self.assertFalse(MobileDevice.objects.exists())

    @override_settings(PUSH_NOTIFICATIONS_ENABLED=True)
    def test_one_failing_device_does_not_stop_the_others(self):
        MobileDevice.objects.create(person=self.device.person, platform="ios", push_token="tok2")
        calls = []

        def flaky(device, *args):
            calls.append(device.push_token)
            if device.push_token == "tok":
                raise RuntimeError("boom")
            return True

        with patch("display.services.push_notifications._send_one", side_effect=flaky):
            reached = push_notifications.send_to_person(self.device.person, "T", "B", {})
        self.assertEqual((reached, sorted(calls)), (1, ["tok", "tok2"]))


class TestCalculatorStatusInNowEndpoint(TestCase):
    """The pilot app polls get_current_app_navigation_task; it must tell whether the live calculator is running."""

    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        now = datetime.datetime.now(datetime.timezone.utc)
        contest = Contest.objects.create(name="Cup", start_time=now, finish_time=now)
        task = NavigationTask.create(
            name="Day 1",
            original_scorecard=get_default_scorecard(),
            start_time=now,
            finish_time=now + datetime.timedelta(hours=3),
            route=Route.objects.create(name="Route"),
            contest=contest,
        )
        self.user = MyUser.objects.create(username="p", email="p@example.com")
        self.pilot = Person.objects.create(first_name="Pi", last_name="Lot", email="p@example.com")
        team = Team.objects.create(crew=Crew.objects.create(member1=self.pilot), aeroplane=Aeroplane.objects.create(registration="LN-Y"))
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=task,
            tracking_device=TRACKING_PILOT,
            contestant_number=1,
            tracker_start_time=now - datetime.timedelta(minutes=5),
            takeoff_time=now + datetime.timedelta(minutes=5),
            finished_by_time=now + datetime.timedelta(hours=2),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def current(self):
        response = self.client.get("/api/v1/userprofile/get_current_app_navigation_task/")
        self.assertEqual(response.status_code, 200)
        return response.json()[0]["active_contestants"][0]

    def test_reports_calculator_not_running_before_positions_arrive(self):
        with patch("display.viewsets.is_calculator_running", return_value=False), patch(
            "display.viewsets.is_dispatch_pending", return_value=False
        ):
            self.assertIs(self.current()["calculator_running"], False)

    def test_reports_calculator_running_once_the_heartbeat_is_alive(self):
        with patch("display.viewsets.is_calculator_running", return_value=True):
            active = self.current()
        self.assertIs(active["calculator_running"], True)
        self.assertEqual(active["id"], self.contestant.pk)

    def test_a_dispatched_but_not_yet_heartbeating_calculator_counts_as_running(self):
        with patch("display.viewsets.is_calculator_running", return_value=False), patch(
            "display.viewsets.is_dispatch_pending", return_value=True
        ):
            self.assertIs(self.current()["calculator_running"], True)
