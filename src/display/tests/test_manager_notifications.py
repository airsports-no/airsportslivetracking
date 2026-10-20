"""GitHub #17: e-mail the managers of a contest when a contestant starts or finishes a navigation task."""

import datetime
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from guardian.shortcuts import assign_perm

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    Contest,
    ContestTeam,
    Contestant,
    ContestantTrack,
    Crew,
    NavigationTask,
    Person,
    Route,
    Team,
)
from display.models.my_user import MyUser
from display.services import manager_notifications
from display.services.manager_notifications import FINISHED, STARTED, queue_manager_notification, recipients
from display.utilities.tracking_definitions import TRACKING_PILOT
from utilities.mock_utilities import TraccarMock

TASK = "display.tasks.send_manager_notification_task.apply_async"


class Base(TestCase):
    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(name="Cup", start_time=self.now, finish_time=self.now, is_public=True)
        self.task = NavigationTask.create(
            name="Round 1",
            original_scorecard=get_default_scorecard(),
            start_time=self.now,
            finish_time=self.now + datetime.timedelta(hours=3),
            route=Route.objects.create(name="Route"),
            contest=self.contest,
            is_public=True,
        )
        self.pilot = Person.objects.create(first_name="Pi", last_name="Lot", email="pilot@example.com")
        team = Team.objects.create(
            crew=Crew.objects.create(member1=self.pilot), aeroplane=Aeroplane.objects.create(registration="LN-A")
        )
        ContestTeam.objects.create(contest=self.contest, team=team)
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.task,
            tracking_device=TRACKING_PILOT,
            contestant_number=1,
            tracker_start_time=self.now - datetime.timedelta(minutes=5),
            takeoff_time=self.now + datetime.timedelta(minutes=5),
            finished_by_time=self.now + datetime.timedelta(hours=2),
        )
        self.manager = self.make_manager("manager@example.com")
        for kind in (STARTED, FINISHED):
            cache.delete(manager_notifications._sent_key(self.contestant, kind))
            self.addCleanup(cache.delete, manager_notifications._sent_key(self.contestant, kind))

    def make_manager(self, email, permission="change_contest"):
        user = MyUser.objects.create(username=email, email=email)
        assign_perm(permission, user, self.contest)
        return user

    def turn_on(self, start=True, finish=True):
        self.task.notify_managers_on_start = start
        self.task.notify_managers_on_finish = finish
        self.task.save()
        self.contestant.refresh_from_db()


class TestQueueing(Base):
    def queue(self, kind):
        with patch(TASK) as task, self.captureOnCommitCallbacks(execute=True):
            queued = queue_manager_notification(self.contestant, kind)
        return queued, task

    def test_nothing_is_sent_unless_the_task_asks_for_it(self):
        for kind in (STARTED, FINISHED):
            queued, task = self.queue(kind)
            self.assertFalse(queued)
            task.assert_not_called()

    def test_each_switch_controls_its_own_notification(self):
        self.turn_on(start=False, finish=True)
        self.assertFalse(self.queue(STARTED)[0])
        queued, task = self.queue(FINISHED)
        self.assertTrue(queued)
        task.assert_called_once()
        self.assertEqual(task.call_args.args[0], (self.contestant.pk, FINISHED))
        self.assertGreater(task.call_args.kwargs["countdown"], 0, "the finish waits for the last scores")

    def test_a_restarted_calculator_does_not_notify_again(self):
        self.turn_on()
        self.assertTrue(self.queue(STARTED)[0])
        queued, task = self.queue(STARTED)
        self.assertFalse(queued)
        task.assert_not_called()

    def test_recalculating_an_old_flight_sends_nothing(self):
        self.turn_on()
        self.contestant.finished_by_time = self.now - datetime.timedelta(days=3)
        for kind in (STARTED, FINISHED):
            self.assertFalse(self.queue(kind)[0])

    def test_a_finish_shortly_after_the_window_still_counts(self):
        self.turn_on()
        self.contestant.finished_by_time = self.now - datetime.timedelta(minutes=10)
        self.assertFalse(self.queue(STARTED)[0], "a start after the window is not live")
        self.assertTrue(self.queue(FINISHED)[0])

    def test_a_failure_never_reaches_the_calculator(self):
        self.turn_on()
        with patch("display.services.manager_notifications.cache.add", side_effect=RuntimeError("redis down")):
            self.assertFalse(queue_manager_notification(self.contestant, STARTED))


class TestHooks(Base):
    def test_the_calculator_start_and_finish_queue_the_notifications(self):
        track = ContestantTrack.objects.get(contestant=self.contestant)
        with patch("display.services.manager_notifications.queue_manager_notification") as queue:
            track.set_calculator_started()
            track.set_calculator_started()  # already started: not again
            track.set_calculator_finished()
        self.assertEqual([call.args[1] for call in queue.call_args_list], ["started", "finished"])


class TestRecipientsAndMail(Base):
    def test_the_managers_get_it_but_not_viewers_or_the_crew(self):
        self.make_manager("viewer@example.com", permission="view_contest")
        self.make_manager("pilot@example.com")  # a manager who is flying
        self.make_manager("Second@Example.com")
        self.assertEqual(recipients(self.contestant), ["manager@example.com", "second@example.com"])

    def test_the_finish_mail_has_the_score_and_says_whether_the_finish_line_was_crossed(self):
        self.make_manager("second@example.com")
        track = ContestantTrack.objects.get(contestant=self.contestant)
        ContestantTrack.objects.filter(pk=track.pk).update(
            score=123.4, passed_finish_gate=True, current_state="Finished"
        )
        self.contestant.refresh_from_db()
        sent = manager_notifications.send_manager_notification(self.contestant, FINISHED)
        self.assertEqual(sent, 2)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(
            {tuple(message.to) for message in mail.outbox}, {("manager@example.com",), ("second@example.com",)}
        )
        message = mail.outbox[0]
        self.assertIn("Pi Lot has finished Round 1: 123", message.subject)
        self.assertIn("They crossed the finish line.", message.alternatives[0][0])
        self.assertIn("LN-A", message.body)

    def test_the_start_mail_links_to_the_live_map(self):
        manager_notifications.send_manager_notification(self.contestant, STARTED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Pi Lot has started Round 1", mail.outbox[0].subject)
        self.assertIn("Follow the flight", mail.outbox[0].alternatives[0][0])

    def test_nobody_to_tell_sends_nothing(self):
        self.manager.delete()
        self.assertEqual(manager_notifications.send_manager_notification(self.contestant, STARTED), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_the_task_e_mails_the_managers(self):
        from display.tasks import send_manager_notification_task

        send_manager_notification_task(self.contestant.pk, STARTED)
        self.assertEqual(len(mail.outbox), 1)
        send_manager_notification_task(999999, STARTED)  # a contestant deleted in the meantime
        self.assertEqual(len(mail.outbox), 1)
