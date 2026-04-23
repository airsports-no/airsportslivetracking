from unittest import TestCase
from unittest.mock import patch

from django.db import OperationalError

from display.utilities.db_retry import is_retryable_lock_error, retry_on_lock_timeout


class TestIsRetryableLockError(TestCase):
    def test_lock_wait_timeout_is_retryable(self):
        self.assertTrue(is_retryable_lock_error(OperationalError(1205, "Lock wait timeout exceeded")))

    def test_deadlock_is_retryable(self):
        self.assertTrue(is_retryable_lock_error(OperationalError(1213, "Deadlock found")))

    def test_too_many_connections_is_not_retryable(self):
        self.assertFalse(is_retryable_lock_error(OperationalError(1040, "Too many connections")))

    def test_empty_args_is_not_retryable(self):
        self.assertFalse(is_retryable_lock_error(OperationalError()))


class TestRetryOnLockTimeout(TestCase):
    def test_succeeds_without_retry(self):
        calls = {"n": 0}

        @retry_on_lock_timeout()
        def fn():
            calls["n"] += 1
            return "ok"

        self.assertEqual("ok", fn())
        self.assertEqual(1, calls["n"])

    def test_retries_lock_timeout_then_succeeds(self):
        attempts = {"n": 0}

        @retry_on_lock_timeout(max_attempts=3, base_delay=0)
        def fn():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise OperationalError(1205, "Lock wait timeout exceeded")
            return "ok"

        with patch("time.sleep"):
            self.assertEqual("ok", fn())
        self.assertEqual(3, attempts["n"])

    def test_gives_up_after_max_attempts(self):
        attempts = {"n": 0}

        @retry_on_lock_timeout(max_attempts=2, base_delay=0)
        def fn():
            attempts["n"] += 1
            raise OperationalError(1205, "Lock wait timeout exceeded")

        with patch("time.sleep"), self.assertRaises(OperationalError):
            fn()
        self.assertEqual(2, attempts["n"])

    def test_non_retryable_code_propagates_immediately(self):
        attempts = {"n": 0}

        @retry_on_lock_timeout(max_attempts=5, base_delay=0)
        def fn():
            attempts["n"] += 1
            raise OperationalError(1040, "Too many connections")

        with self.assertRaises(OperationalError):
            fn()
        self.assertEqual(1, attempts["n"])

    def test_other_exception_propagates_immediately(self):
        attempts = {"n": 0}

        @retry_on_lock_timeout(max_attempts=5, base_delay=0)
        def fn():
            attempts["n"] += 1
            raise ValueError("nope")

        with self.assertRaises(ValueError):
            fn()
        self.assertEqual(1, attempts["n"])
