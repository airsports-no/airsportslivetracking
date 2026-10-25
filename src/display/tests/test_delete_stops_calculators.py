"""
Deleting a task (or contest) while its live calculators still write scores: the calculators are stopped first, and
the delete tried again if the database refuses it because of a write that raced with it.
"""

from unittest.mock import patch

from django.db.utils import IntegrityError, OperationalError
from django.test import SimpleTestCase, TestCase

from display.utilities.calculator_termination_utilities import delete_retrying, stop_calculators

RUNNING = "display.utilities.calculator_running_utilities.is_calculator_running"
REQUEST = "display.utilities.calculator_termination_utilities.request_termination"


class TestStopCalculators(SimpleTestCase):
    def test_only_running_calculators_are_asked_to_stop_and_waited_for(self):
        still_running = {1: 2, 2: 0}  # polls left before each calculator has stopped
        def running(pk):
            if still_running.get(pk, 0) > 0:
                still_running[pk] -= 1
                return True
            return False

        with patch(RUNNING, side_effect=running), patch(REQUEST) as request:
            self.assertTrue(stop_calculators([1, 2, 3], timeout_seconds=5, poll_seconds=0))
        requested = [call.args[0] for call in request.call_args_list]
        self.assertEqual(requested, [1])  # 2 had stopped already and 3 never ran

    def test_gives_up_waiting_after_the_timeout(self):
        with patch(RUNNING, return_value=True), patch(REQUEST):
            self.assertFalse(stop_calculators([1], timeout_seconds=0.05, poll_seconds=0.01))

    def test_nothing_to_stop(self):
        with patch(RUNNING, return_value=False), patch(REQUEST) as request:
            self.assertTrue(stop_calculators([]))
        request.assert_not_called()


class TestDeleteRetrying(SimpleTestCase):
    def test_a_write_that_raced_with_the_delete_is_retried(self):
        calls = []

        def delete():
            calls.append(1)
            if len(calls) < 3:
                raise IntegrityError(1451, "Cannot delete or update a parent row")
            return "deleted"

        self.assertEqual(delete_retrying(delete, attempts=3, delay_seconds=0), "deleted")
        self.assertEqual(len(calls), 3)

    def test_gives_up_after_the_attempts(self):
        def delete():
            raise OperationalError(1213, "Deadlock found")

        with self.assertRaises(OperationalError):
            delete_retrying(delete, attempts=2, delay_seconds=0)

    def test_other_errors_are_not_retried(self):
        calls = []

        def delete():
            calls.append(1)
            raise IntegrityError(1062, "Duplicate entry")

        with self.assertRaises(IntegrityError):
            delete_retrying(delete, attempts=3, delay_seconds=0)
        self.assertEqual(len(calls), 1)


class TestDeleteRetryingInsideATransaction(TestCase):
    """A test case runs in a transaction: someone else's, as far as the delete is concerned."""

    def test_a_refused_delete_is_not_retried_on_a_transaction_that_is_marked_for_rollback(self):
        calls = []

        def delete():
            calls.append(1)
            raise IntegrityError(1451, "Cannot delete or update a parent row")

        with self.assertRaises(IntegrityError):
            delete_retrying(delete, attempts=3, delay_seconds=0)
        self.assertEqual(len(calls), 1)
