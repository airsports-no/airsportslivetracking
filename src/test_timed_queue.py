from unittest import TestCase

import datetime

import threading

from timed_queue import TimedQueue, TimedOut


def now():
    return datetime.datetime.now(datetime.timezone.utc)


class TestTimedQueue(TestCase):
    def test_simple_delay(self):
        start = now()
        tq = TimedQueue()
        tq.put("Test", start + datetime.timedelta(seconds=8))
        data = tq.get()
        time_difference = (now() - start).total_seconds()
        self.assertEqual("Test", data)
        self.assertGreaterEqual(time_difference, 8)
        self.assertLessEqual(time_difference, 8.1)

    def test_wait_empty(self):
        start = now()
        tq = TimedQueue()
        threading.Timer(3, lambda: tq.put("Test", start + datetime.timedelta(seconds=7))).start()
        data = tq.get()
        time_difference = (now() - start).total_seconds()
        self.assertEqual("Test", data)
        self.assertGreaterEqual(time_difference, 7)
        self.assertLessEqual(time_difference, 7.1)

    def test_close_terminates(self):
        start = now()
        tq = TimedQueue()
        tq.put("Test", start + datetime.timedelta(seconds=8))
        threading.Timer(3, lambda: tq.close()).start()
        data = tq.get()
        time_difference = (now() - start).total_seconds()
        self.assertEqual("Test", data)
        self.assertGreaterEqual(time_difference, 8)
        self.assertLessEqual(time_difference, 8.1)
        data = tq.get()
        self.assertIsNone(data)
        time_difference = (now() - start).total_seconds()
        self.assertLessEqual(time_difference, 8.5)

    def test_time_out_with_data(self):
        start = now()
        tq = TimedQueue()
        tq.put("Test", start + datetime.timedelta(seconds=8))
        with self.assertRaises(TimedOut):
            tq.get(timeout=3)
        time_difference = (now() - start).total_seconds()
        self.assertGreaterEqual(time_difference, 3)
        self.assertLessEqual(time_difference, 3.1)
        data = tq.get()
        self.assertEqual("Test", data)

    def test_time_out_without_data(self):
        tq = TimedQueue()
        with self.assertRaises(TimedOut):
            tq.get(timeout=3)

    def test_message_in_the_past(self):
        start = now()
        tq = TimedQueue()
        tq.put("Test", start - datetime.timedelta(seconds=8))
        tq.put("Test2", start - datetime.timedelta(seconds=8))
        data = tq.get()
        data2 = tq.get()
        time_difference = (now() - start).total_seconds()
        self.assertEqual("Test", data)
        self.assertEqual("Test2", data2)
        self.assertGreaterEqual(time_difference, 0)
        self.assertLessEqual(time_difference, 0.1)
