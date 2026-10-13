import datetime
import uuid
from unittest.mock import patch

from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    ClientNotification,
    Contest,
    Contestant,
    Crew,
    MobileAppActivity,
    MobileDevice,
    NavigationTask,
    Person,
    PushNotificationLog,
    Route,
    Team,
)
from display.models.my_user import MyUser
from display.services import push_notifications
from display.services.received_positions import note_position_received
from display.utilities.tracking_definitions import TRACKING_PILOT
from utilities.mock_utilities import TraccarMock


@override_settings(PUSH_NOTIFICATIONS_ENABLED=True)
class TestClientNotifications(TransactionTestCase):
    """The flight notifications for the MSFS client, which has no push: kept for it to fetch while it runs."""

    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        send = patch("display.services.push_notifications._send_one", return_value=True)
        self.send = send.start()
        self.addCleanup(send.stop)

        self.now = timezone.now()
        contest = Contest.objects.create(name="Cup", start_time=self.now, finish_time=self.now)
        self.task = NavigationTask.create(
            name="Day 1",
            original_scorecard=get_default_scorecard(),
            start_time=self.now,
            finish_time=self.now + datetime.timedelta(hours=3),
            route=Route.objects.create(name="Route"),
            contest=contest,
        )
        self.user = MyUser.objects.create(username=f"u{uuid.uuid4().hex[:8]}", email="pilot@example.com")
        self.pilot = Person.objects.create(first_name="Pi", last_name="Lot", email="pilot@example.com")
        self.team = Team.objects.create(
            crew=Crew.objects.create(member1=self.pilot), aeroplane=Aeroplane.objects.create(registration="LN-X")
        )

    def uses_client(self, days_ago=1):
        MobileAppActivity.objects.create(
            user=self.user, platform="msfs", app_version="2.0.0", app_build="35",
            last_seen=self.now - datetime.timedelta(days=days_ago),
        )

    def contestant(self, start_in_min=10, takeoff_in_min=20, number=1):
        return Contestant.objects.create(
            team=self.team,
            navigation_task=self.task,
            tracking_device=TRACKING_PILOT,
            contestant_number=number,
            tracker_start_time=self.now + datetime.timedelta(minutes=start_in_min),
            takeoff_time=self.now + datetime.timedelta(minutes=takeoff_in_min),
            finished_by_time=self.now + datetime.timedelta(hours=2),
        )

    def test_a_pilot_with_only_the_msfs_client_gets_the_reminder_there(self):
        self.uses_client()
        contestant = self.contestant(start_in_min=10)
        self.assertEqual(push_notifications.notify_upcoming_tracking_windows(self.now), 1)
        self.assertEqual(push_notifications.notify_upcoming_tracking_windows(self.now), 0)  # once
        self.send.assert_not_called()  # no phone
        row = ClientNotification.objects.get()
        self.assertEqual((row.person, row.kind, row.contestant), (self.pilot, "tracking_window_opens", contestant))
        self.assertEqual(row.title, "Tracking opens soon")
        self.assertIn("press play", row.body)
        self.assertNotIn("tap Start tracking", row.body)

    def test_a_pilot_with_a_phone_and_the_client_gets_both(self):
        self.uses_client()
        MobileDevice.objects.create(person=self.pilot, platform="android", push_token="tok")
        self.contestant(start_in_min=-30, takeoff_in_min=-10)
        self.assertEqual(push_notifications.notify_not_tracking(self.now), 1)
        self.send.assert_called_once()
        self.assertIn("Open Airsports", self.send.call_args.args[2])  # the phone's own wording
        self.assertIn("Air Sports client", ClientNotification.objects.get().body)
        self.assertEqual(PushNotificationLog.objects.get().devices_reached, 2)

    def test_nobody_is_notified_without_a_phone_or_a_recently_used_client(self):
        self.uses_client(days_ago=45)  # used long ago
        self.contestant(start_in_min=10)
        self.assertEqual(push_notifications.notify_upcoming_tracking_windows(self.now), 0)
        self.assertFalse(ClientNotification.objects.exists())
        self.assertFalse(PushNotificationLog.objects.exists())

    def finished_flight(self):
        done = self.contestant(start_in_min=-200, takeoff_in_min=-180)
        Contestant.objects.filter(pk=done.pk).update(finished_by_time=self.now - datetime.timedelta(minutes=30))
        return done

    def test_a_simulator_left_tracking_is_reported_to_the_client_only(self):
        self.uses_client()
        MobileDevice.objects.create(person=self.pilot, platform="android", push_token="tok")
        self.pilot.simulator_tracking_id = f"s{uuid.uuid4().hex[:20]}"
        self.pilot.app_tracking_id = f"a{uuid.uuid4().hex[:20]}"
        self.pilot.save()
        self.finished_flight()
        note_position_received(self.pilot.simulator_tracking_id, self.now - datetime.timedelta(seconds=20))
        self.assertEqual(push_notifications.notify_still_tracking(self.now), 1)
        self.send.assert_not_called()  # the phone is not tracking: it is not told about the simulator
        body = ClientNotification.objects.get(kind="still_tracking").body
        self.assertIn("closed 30 minutes ago", body)
        self.assertIn("from the simulator", body)

    def test_a_phone_left_tracking_is_reported_to_the_phone_only(self):
        self.uses_client()
        MobileDevice.objects.create(person=self.pilot, platform="android", push_token="tok")
        self.pilot.simulator_tracking_id = f"s{uuid.uuid4().hex[:20]}"
        self.pilot.app_tracking_id = f"a{uuid.uuid4().hex[:20]}"
        self.pilot.save()
        self.finished_flight()
        note_position_received(self.pilot.app_tracking_id, self.now - datetime.timedelta(seconds=20))
        self.assertEqual(push_notifications.notify_still_tracking(self.now), 1)
        self.send.assert_called_once()
        self.assertFalse(ClientNotification.objects.exists())

    def test_the_client_fetches_its_new_notifications(self):
        self.uses_client()
        other = Person.objects.create(first_name="O", last_name="Ther", email="other@example.com")
        first = ClientNotification.objects.create(person=self.pilot, kind="scoring_started", title="A", body="a")
        second = ClientNotification.objects.create(person=self.pilot, kind="flight_scored", title="B", body="b")
        ClientNotification.objects.create(person=other, kind="flight_scored", title="Not mine", body="x")
        old = ClientNotification.objects.create(person=self.pilot, kind="flight_scored", title="Old", body="o")
        ClientNotification.objects.filter(pk=old.pk).update(created_at=self.now - datetime.timedelta(days=2))
        client = APIClient()
        client.force_authenticate(self.user)
        data = client.get("/api/v1/userprofile/client_notifications/").json()
        self.assertEqual([n["title"] for n in data], ["B", "A"])  # newest first, own, last 24 hours
        self.assertEqual(data[0]["kind"], "flight_scored")
        data = client.get(f"/api/v1/userprofile/client_notifications/?after={first.pk}").json()
        self.assertEqual([n["id"] for n in data], [second.pk])
        self.assertEqual(client.get("/api/v1/userprofile/client_notifications/?after=x").status_code, 400)
        self.assertIn(APIClient().get("/api/v1/userprofile/client_notifications/").status_code, (401, 403))
