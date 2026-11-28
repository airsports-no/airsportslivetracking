"""
S22 / S22b: the flight order status of a flight for its own crew, the flight order that follows the declaration (a changed
declaration removes the old one, an incomplete one makes none), the organiser's page keeping a declaration in seconds after the
start point, and the contestant form leaving the declaration alone.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from display.models import Contestant, EmailMapLink
from display.serialisers import OwnFlightSerialiser
from display.services import flight_order_status as status_module
from display.services.declaration_access import ROLE_ORGANISER, ROLE_PILOT, declaration_edit_path
from display.services.flight_order_status import flight_order_status, record_flight_order_state
from display.tasks import generate_and_maybe_notify_flight_order
from display.tests.test_pilot_declaration import BEFORE_TAKEOFF, NOW, PilotDeclarationTestBase
from display.viewsets import flight_order_path_for

APPLY_ASYNC = "display.tasks.generate_and_maybe_notify_flight_order.apply_async"
GENERATE = "display.flight_order_and_maps.generate_flight_orders.generate_flight_orders"
# The task closes stale connections between its steps, which would close the one the test runs in
CONNECTIONS = "display.tasks.connections"


class FlightOrderTestBase(PilotDeclarationTestBase):
    def setUp(self):
        super().setUp()
        Contestant.objects.filter(pk=self.contestant.pk).update(self_registered=True)
        self.contestant = Contestant.objects.get(pk=self.contestant.pk)
        self.pilot_user = get_user_model().objects.get(email=self.pilot_email)
        self.stranger_user = get_user_model().objects.get(email="stranger@example.com")
        cache_key = f"flight_order_state_{self.contestant.pk}"
        from django.core.cache import cache

        cache.delete(cache_key)
        self.addCleanup(cache.delete, cache_key)

    def status(self, user=None):
        return flight_order_status(Contestant.objects.get(pk=self.contestant.pk), user or self.pilot_user)

    def save_declaration(self, declaration, client=None):
        with patch(NOW, return_value=BEFORE_TAKEOFF), self.captureOnCommitCallbacks(execute=True):
            response = self.put(client or self.pilot, declaration)
        self.assertEqual(200, response.status_code, response.content)
        return response

    def complete_declaration(self):
        with patch(APPLY_ASYNC):
            self.save_declaration(self.full_declaration())

    def make_link(self):
        return EmailMapLink.objects.create(contestant=self.contestant, orders=b"pdf")


class TestFlightOrderStatus(FlightOrderTestBase):
    def test_waiting_for_declaration_while_the_required_declaration_is_not_complete(self):
        self.assertEqual("waiting_for_declaration", self.status()["state"])
        first = self.declared_names()[0]
        with patch(APPLY_ASYNC) as dispatch:
            self.save_declaration({"known_time_gate_predictions": {first: "2026-08-01T10:10:00Z"}})
        dispatch.assert_not_called()
        self.assertEqual("waiting_for_declaration", self.status()["state"])

    def test_being_made_from_the_complete_declaration_until_the_flight_order_exists(self):
        with patch(APPLY_ASYNC) as dispatch:
            response = self.save_declaration(self.full_declaration())
        dispatch.assert_called_once()
        self.assertEqual("being_made", self.status()["state"])
        self.assertEqual("being_made", response.json()["flight_order_status"]["state"])
        self.assertIsNone(response.json()["flight_order_status"]["path"])

    def test_ready_gives_the_download_path_and_when_it_was_made(self):
        link = self.make_link()
        result = self.status()
        self.assertEqual("ready", result["state"])
        self.assertEqual(f"/display/maplink/{link.pk}/", result["path"])
        self.assertEqual(flight_order_path_for(Contestant.objects.get(pk=self.contestant.pk)), result["path"])
        self.assertEqual(link.created_at.isoformat(), result["created_at"])

    def test_the_pdf_of_the_flight_order_is_not_loaded_to_tell_that_it_is_ready(self):
        from django.db import connection
        from django.db.models import Prefetch
        from django.test.utils import CaptureQueriesContext

        link = self.make_link()
        contestant = Contestant.objects.get(pk=self.contestant.pk)
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(f"/display/maplink/{link.pk}/", flight_order_status(contestant, self.pilot_user)["path"])
        link_queries = [q["sql"] for q in queries if "display_emailmaplink" in q["sql"]]
        self.assertEqual(1, len(link_queries))
        self.assertNotIn("orders", link_queries[0])
        # Prefetched by the caller: no further query for the links
        contestant = Contestant.objects.prefetch_related(
            Prefetch("emailmaplink_set", queryset=EmailMapLink.objects.only("id", "contestant_id", "created_at"))
        ).get(pk=self.contestant.pk)
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual("ready", flight_order_status(contestant, self.pilot_user)["state"])
        self.assertEqual([], [q for q in queries if "display_emailmaplink" in q["sql"]])

    def test_failed_says_why_in_words_for_the_pilot(self):
        self.complete_declaration()
        with patch(CONNECTIONS), patch(GENERATE, side_effect=RuntimeError("secret internal detail")):
            generate_and_maybe_notify_flight_order(self.contestant.pk, "a@example.com", "A", True)
        result = self.status()
        self.assertEqual("failed", result["state"])
        self.assertIn("could not be made", result["reason"])
        self.assertNotIn("secret internal detail", result["reason"])

    def test_a_task_that_never_finished_is_failed_after_a_while(self):
        self.complete_declaration()
        record_flight_order_state(self.contestant.pk, "queued")
        self.assertEqual("being_made", self.status()["state"])
        later = status_module._utcnow() + datetime.timedelta(minutes=16)
        with patch.object(status_module, "_utcnow", return_value=later):
            self.assertEqual("failed", self.status()["state"])

    def test_the_running_task_records_being_made_and_then_done(self):
        self.complete_declaration()
        seen = []

        def generate(contestant):
            seen.append(self.status()["state"])
            return b"pdf"

        with (
            patch(CONNECTIONS),
            patch(GENERATE, side_effect=generate),
            patch.object(EmailMapLink, "send_email") as send,
        ):
            generate_and_maybe_notify_flight_order(self.contestant.pk, "a@example.com", "A", True)
        self.assertEqual(["being_made"], seen)
        send.assert_called_once()
        self.assertEqual("ready", self.status()["state"])

    def test_not_available_for_a_flight_the_organiser_made_until_there_is_a_flight_order(self):
        Contestant.objects.filter(pk=self.contestant.pk).update(self_registered=False)
        self.assertEqual("not_available", self.status()["state"])
        self.make_link()
        self.assertEqual("ready", self.status()["state"])

    def test_not_available_without_an_address_to_send_it_to(self):
        person = self.contest_team.team.crew.member1
        type(person).objects.filter(pk=person.pk).update(email="")
        # The pilot's account still matches by the address the crew had; the status is computed for the organiser here
        self.assertEqual("not_available", self.status(self.user)["state"])

    def test_a_task_without_declaration_is_being_made_after_booking(self):
        from display.services.self_registration import send_self_registration_flight_order

        self.navigation_task.task_subtype = ""
        self.navigation_task.save(update_fields=["task_subtype"])
        with patch(APPLY_ASYNC):
            send_self_registration_flight_order(Contestant.objects.get(pk=self.contestant.pk), "a@example.com", "A")
        self.assertEqual("being_made", self.status()["state"])


class TestWhoSeesTheStatus(FlightOrderTestBase):
    def test_the_crew_and_the_organiser_see_it(self):
        self.assertEqual("waiting_for_declaration", self.status()["state"])
        self.assertEqual("waiting_for_declaration", self.status(self.user)["state"])

    def test_somebody_else_gets_nothing_even_with_a_flight_order(self):
        self.make_link()
        self.assertIsNone(self.status(self.stranger_user))
        self.assertIsNone(flight_order_status(self.contestant, None))

    def test_the_declaration_endpoint_hides_it_from_others(self):
        self.make_link()
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            self.assertEqual(404, self.stranger.get(self.url).status_code)
            body = self.pilot.get(self.url).json()
        self.assertEqual("ready", body["flight_order_status"]["state"])
        self.assertEqual(self.contest.pk, body["contest_id"])
        self.assertEqual("Europe/Oslo", body["time_zone"])

    def test_the_pilot_is_told_why_it_can_only_be_read_after_the_cut_off(self):
        from display.tests.test_pilot_declaration import AFTER_TAKEOFF

        with patch(NOW, return_value=BEFORE_TAKEOFF):
            self.assertIsNone(self.pilot.get(self.url).json()["read_only_reason"])
        with patch(NOW, return_value=AFTER_TAKEOFF):
            reason = self.pilot.get(self.url).json()["read_only_reason"]
            self.assertIsNone(self.organiser.get(self.url).json()["read_only_reason"])
        self.assertIn("can no longer be changed", reason)

    def test_the_own_flights_data_carries_it_for_the_crew_only(self):
        link = self.make_link()

        class Request:
            user = self.pilot_user

        class OtherRequest:
            user = self.stranger_user

        contestant = Contestant.objects.get(pk=self.contestant.pk)
        data = OwnFlightSerialiser(contestant, context={"request": Request()}).data
        self.assertEqual(f"/display/maplink/{link.pk}/", data["flight_order_status"]["path"])
        self.assertEqual("ready", data["flight_order_status"]["state"])
        data = OwnFlightSerialiser(contestant, context={"request": OtherRequest()}).data
        self.assertIsNone(data["flight_order_status"])

    def test_the_own_flights_endpoint_lists_it(self):
        response = self.pilot.get(reverse("userprofile-my-future-flights"))
        self.assertEqual(200, response.status_code, response.content)
        flights = [item for item in response.json() if item["id"] == self.contestant.pk]
        if flights:
            self.assertEqual("waiting_for_declaration", flights[0]["flight_order_status"]["state"])


class TestFlightOrderFollowsTheDeclaration(FlightOrderTestBase):
    def test_a_changed_declaration_removes_the_old_flight_order_and_makes_a_new_one(self):
        with patch(APPLY_ASYNC):
            self.save_declaration(self.full_declaration())
        self.make_link()
        self.assertEqual("ready", self.status()["state"])

        changed = self.full_declaration()
        name = self.declared_names()[0]
        changed["known_time_gate_predictions"][name] = "2026-08-01T10:20:00Z"
        with patch(APPLY_ASYNC) as dispatch:
            self.save_declaration(changed)
        self.assertFalse(EmailMapLink.objects.filter(contestant=self.contestant).exists())
        dispatch.assert_called_once()
        self.assertEqual("being_made", self.status()["state"])

    def test_the_same_declaration_again_keeps_the_flight_order(self):
        with patch(APPLY_ASYNC):
            self.save_declaration(self.full_declaration())
        self.make_link()
        with patch(APPLY_ASYNC) as dispatch:
            self.save_declaration(self.full_declaration())
        dispatch.assert_not_called()
        self.assertEqual("ready", self.status()["state"])

    def test_an_incomplete_declaration_removes_the_old_flight_order_and_makes_none(self):
        with patch(APPLY_ASYNC):
            self.save_declaration(self.full_declaration())
        self.make_link()
        first = self.declared_names()[0]
        with patch(APPLY_ASYNC) as dispatch:
            self.save_declaration({"known_time_gate_predictions": {first: "2026-08-01T10:10:00Z"}})
        dispatch.assert_not_called()
        self.assertFalse(EmailMapLink.objects.filter(contestant=self.contestant).exists())
        self.assertEqual("waiting_for_declaration", self.status()["state"])

    def test_an_organiser_changing_it_also_removes_the_old_flight_order(self):
        with patch(APPLY_ASYNC):
            self.save_declaration(self.full_declaration())
        self.make_link()
        changed = self.full_declaration()
        changed["known_time_gate_predictions"][self.declared_names()[0]] = "2026-08-01T10:25:00Z"
        with patch(APPLY_ASYNC):
            self.save_declaration(changed, self.organiser)
        self.assertFalse(EmailMapLink.objects.filter(contestant=self.contestant).exists())

    def test_saving_again_after_a_failure_tries_again(self):
        with patch(APPLY_ASYNC):
            self.save_declaration(self.full_declaration())
        with patch(CONNECTIONS), patch(GENERATE, side_effect=RuntimeError("boom")):
            generate_and_maybe_notify_flight_order(self.contestant.pk, "a@example.com", "A", True)
        self.assertEqual("failed", self.status()["state"])
        with patch(APPLY_ASYNC) as dispatch:
            self.save_declaration(self.full_declaration())
        dispatch.assert_called_once()
        self.assertEqual("being_made", self.status()["state"])

    def test_a_run_that_was_overtaken_by_a_new_declaration_does_not_leave_its_flight_order(self):
        self.complete_declaration()

        def generate(contestant):
            # The pilot saves a changed declaration while this one is being made
            record_flight_order_state(contestant.pk, "queued")
            return b"old pdf"

        with (
            patch(CONNECTIONS),
            patch(GENERATE, side_effect=generate),
            patch.object(EmailMapLink, "send_email") as send,
        ):
            generate_and_maybe_notify_flight_order(self.contestant.pk, "a@example.com", "A", True)
        send.assert_not_called()
        self.assertFalse(EmailMapLink.objects.filter(contestant=self.contestant).exists())
        self.assertEqual("being_made", self.status()["state"])


class TestOptionalDeclarationFlightOrder(FlightOrderTestBase):
    task_subtype = "known_circuit"

    def test_declaring_makes_a_new_flight_order_and_an_incomplete_one_none(self):
        self.make_link()
        name = self.declared_names()[0]
        with patch(APPLY_ASYNC) as dispatch:
            self.save_declaration({"turnpoint_time_overrides": {"NOPE": "2026-08-01T10:10:00Z"}})
        dispatch.assert_not_called()
        self.assertEqual("waiting_for_declaration", self.status()["state"])
        with patch(APPLY_ASYNC) as dispatch:
            self.save_declaration({"turnpoint_time_overrides": {name: "2026-08-01T10:10:00Z"}})
        dispatch.assert_called_once()
        self.assertEqual("being_made", self.status()["state"])


class TestDeclarationEditPath(FlightOrderTestBase):
    def test_a_pilot_gets_their_own_page_and_an_organiser_the_organisers_page(self):
        self.assertEqual(f"/declaration/{self.contestant.pk}", declaration_edit_path(self.contestant, ROLE_PILOT))
        self.assertEqual(f"/declaration/{self.contestant.pk}", declaration_edit_path(self.contestant))
        self.assertEqual(
            f"/contestant-declaration/{self.contest.pk}/{self.navigation_task.pk}/{self.contestant.pk}",
            declaration_edit_path(self.contestant, ROLE_ORGANISER),
        )
        from display.services.declaration_access import declaration_status

        contestant = Contestant.objects.get(pk=self.contestant.pk)
        self.assertEqual(f"/declaration/{contestant.pk}", declaration_status(contestant, self.pilot_user)["edit_url"])
        self.assertTrue(declaration_status(contestant, self.user)["edit_url"].startswith("/contestant-declaration/"))


class TestOrganiserPageAndContestantForm(FlightOrderTestBase):
    def relative(self, **times):
        return {"time_reference": "start_point", "known_time_gate_predictions": times}

    def organiser_save(self, payload):
        self.client.force_login(self.user)
        return self.client.patch(
            reverse(
                "contestants-detail",
                kwargs={
                    "contest_pk": self.contest.pk,
                    "navigationtask_pk": self.navigation_task.pk,
                    "pk": self.contestant.pk,
                },
            ),
            payload,
            content_type="application/json",
        )

    def test_the_organiser_page_keeps_a_relative_declaration_relative(self):
        times = {name: 600 + 120 * i for i, name in enumerate(self.declared_names())}
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            self.put(self.pilot, self.relative(**times))
        stored = self.declaration()["relative_times"]
        # What the organiser's page sends for a declaration it found in seconds: the same seconds, the reference named
        first = self.declared_names()[0]
        times[first] += 30
        response = self.organiser_save({"declaration_payload": self.relative(**times)})
        self.assertEqual(200, response.status_code, response.content)
        payload = self.declaration()
        self.assertEqual("start_point", payload["time_reference"])
        self.assertEqual(stored[first] + 30, payload["relative_times"][first])
        self.assertEqual("complete", declaration_status_state(self.contestant, self.user))

    def test_clock_times_from_the_organiser_page_stay_absolute(self):
        self.organiser_save({"declaration_payload": self.full_declaration()})
        self.assertNotIn("time_reference", self.declaration())

    def test_the_contestant_form_without_a_declaration_leaves_it_as_it_is(self):
        times = {name: 600 + 120 * i for i, name in enumerate(self.declared_names())}
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            self.put(self.pilot, self.relative(**times))
        before = self.declaration()
        response = self.organiser_save({"wind_speed": 5})
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(before, self.declaration())
        self.assertEqual("complete", declaration_status_state(self.contestant, self.user))

    def test_the_contestant_form_keeps_an_absolute_declaration_too(self):
        self.put(self.organiser, self.full_declaration())
        before = self.declaration()
        self.organiser_save({"air_speed": 80})
        self.assertEqual(before, self.declaration())

    def test_an_explicit_empty_declaration_still_clears_it(self):
        self.put(self.organiser, self.full_declaration())
        self.organiser_save({"declaration_payload": {}})
        self.assertEqual({}, self.declaration())


def declaration_status_state(contestant, user) -> str:
    from display.services.declaration_access import declaration_status

    return declaration_status(Contestant.objects.get(pk=contestant.pk), user)["state"]
