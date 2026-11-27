"""
S21: the flight's own pilot reads and changes their declaration until take-off, organisers always (D6); the declaration
status; times declared as seconds after the start point; and the messages the declaration's validation gives.
"""

import datetime
import json
from unittest.mock import patch

from dateutil import parser
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from display.models import Contestant, Crew, Person
from display.serialisers import ContestantSerialiser, OwnFlightSerialiser
from display.services.contestant_task_compiler import ContestantTaskCompiler
from display.services.declaration_access import declaration_cutoff, declaration_status
from display.tests import test_curve_precision_navigation_declaration_ui as base_module
from display.utilities.task_types import (
    CURVE_NAVIGATION_TIME_ESTIMATION,
    KNOWN_CIRCUIT,
    PRECISION_NAVIGATION,
    stored_task_type,
)

UTC = datetime.timezone.utc
# The contestant of the base class takes off at 09:55 and starts (SP) at 10:00 on 2026-08-01
BEFORE_TAKEOFF = datetime.datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
AFTER_TAKEOFF = datetime.datetime(2026, 8, 1, 9, 56, tzinfo=UTC)
SP_TIME = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
NOW = "display.services.declaration_access.utcnow"


class PilotDeclarationTestBase(base_module.CurvePrecisionNavigationDeclarationTestBase):
    task_subtype = PRECISION_NAVIGATION

    def setUp(self):
        super().setUp()
        self.contestant = self._create_contestant()
        self.pilot_email = self.contest_team.team.crew.member1.email
        self.pilot = self._login(self.pilot_email)
        self.stranger = self._login("stranger@example.com")
        self.organiser = self._login(self.user.email)
        self.url = reverse("declarations-detail", kwargs={"pk": self.contestant.pk})

    @staticmethod
    def _login(email) -> APIClient:
        user, _ = get_user_model().objects.get_or_create(email=email)
        client = APIClient()
        client.force_authenticate(user)
        return client

    def declared_names(self):
        return [wp.name for wp in self.route.waypoints if wp.type in ("tp", "fp")]

    def declaration(self, contestant=None) -> dict:
        return Contestant.objects.get(
            pk=(contestant or self.contestant).pk
        ).contestanttaskconfiguration.declaration_payload

    def put(self, client, payload, url=None):
        return client.put(url or self.url, {"declaration_payload": payload}, format="json")

    def full_declaration(self) -> dict:
        return {
            "known_time_gate_predictions": {
                name: f"2026-08-01T10:{10 + i}:00Z" for i, name in enumerate(self.declared_names())
            }
        }


class TestWhoMayChangeTheDeclaration(PilotDeclarationTestBase):
    def test_the_pilot_reads_and_writes_before_take_off(self):
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            response = self.pilot.get(self.url)
            self.assertEqual(200, response.status_code, response.content)
            self.assertTrue(response.json()["status"]["can_edit"])
            self.assertEqual("2026-08-01T09:55:00+00:00", response.json()["status"]["edit_until"])
            response = self.put(self.pilot, self.full_declaration())
            self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("complete", response.json()["status"]["state"])
        self.assertEqual(
            self.full_declaration()["known_time_gate_predictions"].keys(),
            self.declaration()["known_time_gate_predictions"].keys(),
        )

    def test_the_co_pilot_counts_as_the_pilot(self):
        co_pilot = Person.objects.create(first_name="Co", last_name="Pilot", email="copilot@example.com")
        crew = Crew.objects.get(pk=self.contest_team.team.crew_id)
        crew.member2 = co_pilot
        crew.save()
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            response = self.put(self._login("copilot@example.com"), self.full_declaration())
        self.assertEqual(200, response.status_code, response.content)

    def test_after_take_off_the_pilot_can_read_but_not_write_and_is_told_why(self):
        with patch(NOW, return_value=AFTER_TAKEOFF):
            read = self.pilot.get(self.url)
            write = self.put(self.pilot, self.full_declaration())
        self.assertEqual(200, read.status_code)
        self.assertFalse(read.json()["status"]["can_edit"])
        self.assertEqual(403, write.status_code)
        message = write.json()["detail"]
        self.assertIn("can no longer be changed", message)
        self.assertIn("organiser", message)
        self.assertEqual({}, self.declaration().get("known_time_gate_predictions", {}))

    def test_once_the_calculator_has_started_the_pilot_cannot_write_even_before_take_off(self):
        self.contestant.contestanttrack.calculator_started = True
        self.contestant.contestanttrack.save()
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            self.assertEqual(403, self.put(self.pilot, self.full_declaration()).status_code)

    def test_somebody_else_gets_nothing_not_even_that_the_flight_exists(self):
        missing = reverse("declarations-detail", kwargs={"pk": self.contestant.pk + 1000})
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            self.assertEqual(404, self.stranger.get(self.url).status_code)
            self.assertEqual(404, self.put(self.stranger, self.full_declaration()).status_code)
            self.assertEqual(404, self.stranger.get(missing).status_code)
        self.assertEqual({}, self.declaration().get("known_time_gate_predictions", {}))

    def test_a_pilot_cannot_reach_the_declaration_of_another_pilots_flight(self):
        other_person = Person.objects.create(first_name="Other", last_name="Pilot", email="other-pilot@example.com")
        other_team = type(self.contest_team.team).objects.create(
            crew=Crew.objects.create(member1=other_person), aeroplane=self.contest_team.team.aeroplane
        )
        other = Contestant.objects.get(pk=self.contestant.pk)
        other.pk = None
        other.team = other_team
        other.contestant_number = 2
        other.save()
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            self.assertEqual(404, self.pilot.get(reverse("declarations-detail", kwargs={"pk": other.pk})).status_code)

    def test_anonymous_is_refused(self):
        client = APIClient()
        self.assertIn(client.get(self.url).status_code, (401, 403))
        self.assertIn(self.put(client, self.full_declaration()).status_code, (401, 403))

    def test_an_organiser_always_may_also_after_take_off(self):
        with patch(NOW, return_value=AFTER_TAKEOFF):
            response = self.put(self.organiser, self.full_declaration())
        self.assertEqual(200, response.status_code, response.content)
        self.assertTrue(response.json()["status"]["can_edit"])
        self.assertIsNone(response.json()["status"]["edit_until"])

    def test_the_pilots_payload_holds_nothing_the_route_keeps_secret(self):
        hidden = [wp.name for wp in self.route.waypoints if wp.type not in ("tp", "fp", "sp")]
        self.assertTrue(hidden, "the test route has hidden gates")
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            body = self.pilot.get(self.url).json()
            self.put(self.pilot, self.full_declaration())
            body_after = self.put(self.pilot, self.full_declaration()).json()
        for payload in (body, body_after):
            text = json.dumps(payload)
            for name in hidden:
                self.assertNotIn(f'"{name}"', text)
            self.assertNotIn("compiled_effective_route_payload", text)
            self.assertNotIn("latitude", text)
            self.assertNotIn("coordinates", text)
        self.assertEqual(self.declared_names(), body["form"]["time_points"])

    def test_the_pilot_does_not_get_the_organisers_route_errors(self):
        from display.models import CompiledNavigationTask

        compiled = CompiledNavigationTask.objects.get(navigation_task=self.navigation_task)
        compiled.compiled_payload = {
            **compiled.compiled_payload,
            "validation_errors": ["Organiser problem with the route."],
        }
        compiled.save()
        config = self.contestant.contestanttaskconfiguration
        config.validation_errors = ["Give a time for FP.", "Organiser problem with the route."]
        config.save()
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            pilot = self.pilot.get(self.url).json()["status"]["errors"]
            organiser = self.organiser.get(self.url).json()["status"]["errors"]
        self.assertEqual(["Give a time for FP."], pilot)
        self.assertIn("Organiser problem with the route.", organiser)


class TestCutOff(PilotDeclarationTestBase):
    def test_the_cut_off_is_the_take_off_time(self):
        self.assertEqual(self.contestant.takeoff_time, declaration_cutoff(self.contestant))

    def test_with_adaptive_start_it_is_the_earlier_of_take_off_and_tracker_start(self):
        contestant = Contestant.objects.get(pk=self.contestant.pk)
        contestant.adaptive_start = True
        self.assertEqual(contestant.tracker_start_time, declaration_cutoff(contestant))
        contestant.tracker_start_time = contestant.takeoff_time + datetime.timedelta(minutes=30)
        self.assertEqual(contestant.takeoff_time, declaration_cutoff(contestant))


class TestDeclarationStatus(PilotDeclarationTestBase):
    def status(self, user=None):
        return declaration_status(Contestant.objects.get(pk=self.contestant.pk), user or self.pilot_user())

    def pilot_user(self):
        return get_user_model().objects.get(email=self.pilot_email)

    def test_required_declaration_goes_from_missing_through_incomplete_to_complete(self):
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            status = self.status()
            self.assertEqual(("required", "missing"), (status["need"], status["state"]))
            self.assertEqual([f"Give a time for {self._names_in_words()}."], status["errors"])
            self.assertTrue(status["can_edit"])
            self.assertEqual(
                f"/contestant-declaration/{self.contest.pk}/{self.navigation_task.pk}/{self.contestant.pk}",
                status["edit_url"],
            )

            first = self.declared_names()[0]
            self.put(self.pilot, {"known_time_gate_predictions": {first: "2026-08-01T10:10:00Z"}})
            status = self.status()
            self.assertEqual("incomplete", status["state"])
            self.assertEqual(1, len(status["errors"]))

            self.put(self.pilot, self.full_declaration())
            status = self.status()
            self.assertEqual(("complete", []), (status["state"], status["errors"]))

    def _names_in_words(self):
        names = self.declared_names()
        return f"{', '.join(names[:-1])} and {names[-1]}"

    def test_after_the_cut_off_the_status_says_it_cannot_be_edited(self):
        with patch(NOW, return_value=AFTER_TAKEOFF):
            status = self.status()
        self.assertFalse(status["can_edit"])
        self.assertEqual("2026-08-01T09:55:00+00:00", status["edit_until"])

    def test_somebody_else_learns_nothing_about_who_may_edit(self):
        status = declaration_status(self.contestant, get_user_model().objects.get(email="stranger@example.com"))
        self.assertEqual((False, None, None), (status["can_edit"], status["edit_until"], status["edit_url"]))
        self.assertEqual(
            (False, None, None),
            tuple(declaration_status(self.contestant, None)[key] for key in ("can_edit", "edit_until", "edit_url")),
        )

    def test_the_organiser_gets_no_time_limit(self):
        status = self.status(self.user)
        self.assertEqual((True, None), (status["can_edit"], status["edit_until"]))

    def test_the_own_flights_data_of_the_apps_carries_the_status(self):
        class FakeRequest:
            user = self.pilot_user()

        with patch(NOW, return_value=BEFORE_TAKEOFF):
            data = OwnFlightSerialiser(
                Contestant.objects.get(pk=self.contestant.pk), context={"request": FakeRequest()}
            ).data
        self.assertEqual(
            {"need", "state", "errors", "can_edit", "edit_until", "edit_url"}, set(data["declaration_status"].keys())
        )
        self.assertEqual("required", data["declaration_status"]["need"])

    def test_the_own_flights_endpoint_lists_it(self):
        response = self.pilot.get(reverse("userprofile-my-previous-flights"))
        self.assertEqual(200, response.status_code, response.content)
        (flight,) = [item for item in response.json() if item["id"] == self.contestant.pk]
        self.assertEqual("missing", flight["declaration_status"]["state"])

    def test_the_contestant_data_adds_the_fields_and_keeps_the_old_ones(self):
        class FakeRequest:
            user = self.pilot_user()

        with patch(NOW, return_value=BEFORE_TAKEOFF):
            data = ContestantSerialiser(
                Contestant.objects.get(pk=self.contestant.pk), context={"request": FakeRequest()}
            ).data
        status = data["declaration_status"]
        self.assertEqual((True, False), (status["required"], status["complete"]))
        self.assertEqual(("required", "missing", True), (status["need"], status["state"], status["can_edit"]))


class TestOptionalDeclaration(PilotDeclarationTestBase):
    task_subtype = KNOWN_CIRCUIT

    def test_it_is_optional_and_missing_without_errors_until_a_time_is_given(self):
        self.assertEqual("optional", stored_task_type(self.navigation_task).declaration_need)
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            status = declaration_status(self.contestant, get_user_model().objects.get(email=self.pilot_email))
            self.assertEqual(("optional", "missing", []), (status["need"], status["state"], status["errors"]))
            name = self.declared_names()[0]
            self.assertEqual(
                200, self.put(self.pilot, {"turnpoint_time_overrides": {name: "2026-08-01T10:10:00Z"}}).status_code
            )
        status = declaration_status(Contestant.objects.get(pk=self.contestant.pk), None)
        self.assertEqual(("optional", "complete"), (status["need"], status["state"]))

    def test_an_unknown_point_is_explained(self):
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            response = self.put(self.pilot, {"turnpoint_time_overrides": {"NOPE": "2026-08-01T10:10:00Z"}})
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("incomplete", response.json()["status"]["state"])
        self.assertEqual(
            ["NOPE is not a point of this circuit. Take the time out."], response.json()["status"]["errors"]
        )


class TestNoDeclaration(PilotDeclarationTestBase):
    task_subtype = None

    def test_a_task_type_without_declaration_needs_none(self):
        self.assertEqual("not_needed", stored_task_type(self.navigation_task).declaration_need)
        status = declaration_status(self.contestant, get_user_model().objects.get(email=self.pilot_email))
        self.assertEqual(
            {
                "need": "not_needed",
                "state": "complete",
                "errors": [],
                "can_edit": False,
                "edit_until": None,
                "edit_url": None,
            },
            status,
        )

    def test_writing_one_is_refused_in_words(self):
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            response = self.put(self.pilot, {"known_time_gate_predictions": {"FP": "2026-08-01T10:10:00Z"}})
        self.assertEqual(400, response.status_code)
        self.assertIn("no declaration", json.dumps(response.json()))


class TestTimesAfterTheStartPoint(PilotDeclarationTestBase):
    def relative(self, **times):
        return {"time_reference": "start_point", "known_time_gate_predictions": times}

    def test_seconds_after_the_start_point_are_accepted_stored_and_converted(self):
        first, *_, last = self.declared_names()
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            response = self.put(self.pilot, self.relative(**{first: 750, last: "20:30"}))
        self.assertEqual(200, response.status_code, response.content)
        payload = self.declaration()
        self.assertEqual("start_point", payload["time_reference"])
        self.assertEqual({first: 750, last: 1230}, payload["relative_times"])
        # SP is at 10:00: the stored timestamps are what the seconds come to
        self.assertEqual(
            SP_TIME + datetime.timedelta(seconds=750), parser.parse(payload["known_time_gate_predictions"][first])
        )
        gate_times = Contestant.objects.get(
            pk=self.contestant.pk
        ).contestanttaskconfiguration.compiled_gate_times_payload
        self.assertEqual(SP_TIME + datetime.timedelta(seconds=1230), parser.parse(gate_times[last]))
        self.assertEqual("2026-08-01T10:12:30+00:00", payload["known_time_gate_predictions"][first])

    def test_a_declaration_of_all_the_points_in_seconds_is_complete(self):
        times = {name: 600 + 120 * i for i, name in enumerate(self.declared_names())}
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            response = self.put(self.pilot, self.relative(**times))
        self.assertEqual("complete", response.json()["status"]["state"])
        self.assertEqual("start_point", response.json()["declaration_payload"]["time_reference"])

    def test_the_absolute_form_is_stored_as_before_and_says_nothing_of_a_reference(self):
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            self.put(self.pilot, self.full_declaration())
        payload = self.declaration()
        self.assertNotIn("time_reference", payload)
        self.assertNotIn("relative_times", payload)
        self.assertEqual(len(self.declared_names()), len(self.contestant_declared_absolute_times()))

    def contestant_declared_absolute_times(self):
        return Contestant.objects.get(pk=self.contestant.pk).get_declared_absolute_times()

    def test_times_in_seconds_do_not_lock_the_schedule_as_clock_times_do(self):
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            self.put(self.pilot, self.relative(**{self.declared_names()[0]: 600}))
        self.assertEqual([], self.contestant_declared_absolute_times())

    def test_the_times_follow_the_start_point_when_it_moves(self):
        first = self.declared_names()[0]
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            self.put(self.pilot, self.relative(**{first: 600}))
        Contestant.objects.filter(pk=self.contestant.pk).update(minutes_to_starting_point=10)
        contestant = Contestant.objects.get(pk=self.contestant.pk)
        config = ContestantTaskCompiler(contestant).compile(
            declaration_payload=contestant.contestanttaskconfiguration.declaration_payload
        )
        self.assertEqual(
            SP_TIME + datetime.timedelta(minutes=5, seconds=600),
            parser.parse(config.declaration_payload["known_time_gate_predictions"][first]),
        )

    def test_nonsense_is_refused_in_words(self):
        first = self.declared_names()[0]
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            for value in ("later", -5, 10**9, True):
                response = self.put(self.pilot, self.relative(**{first: value}))
                self.assertEqual(400, response.status_code, value)
            response = self.put(self.pilot, {"time_reference": "tomorrow", "known_time_gate_predictions": {first: 5}})
        self.assertEqual(400, response.status_code)
        self.assertIn("start_point", json.dumps(response.json()))

    def test_after_an_adaptive_start_the_declared_offsets_are_applied_to_the_actual_start(self):
        Contestant.objects.filter(pk=self.contestant.pk).update(adaptive_start=True)
        first, *middle, last = self.declared_names()
        times = {
            first: 750,
            **{name: 750 + 1050 * (i + 1) // (len(middle) + 1) for i, name in enumerate(middle)},
            last: 1800,
        }
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            response = self.put(self.pilot, self.relative(**times))
        self.assertEqual("complete", response.json()["status"]["state"], response.content)
        contestant = Contestant.objects.get(pk=self.contestant.pk)
        # The start was flown at 10:07 whatever the schedule said
        start = datetime.datetime(2026, 8, 1, 10, 7, tzinfo=UTC)
        gate_times = contestant.adaptive_start_gate_times(start)
        self.assertEqual(start + datetime.timedelta(seconds=750), gate_times[first])
        self.assertEqual(start + datetime.timedelta(seconds=1800), gate_times[last])
        # The hidden gates in between are estimated between the declared times, not left at the route's times
        names = [wp.name for wp in self.route.waypoints]
        between = [name for name in names[names.index(first) + 1 : names.index(last)] if name in gate_times]
        for name in between:
            self.assertTrue(
                start + datetime.timedelta(seconds=750) <= gate_times[name] <= start + datetime.timedelta(seconds=1800)
            )

    def test_a_declaration_in_clock_times_is_not_applied_after_an_adaptive_start(self):
        # Today's behaviour, reported and not changed: the route's times replace the declared clock times
        Contestant.objects.filter(pk=self.contestant.pk).update(adaptive_start=True)
        first = self.declared_names()[0]
        with patch(NOW, return_value=BEFORE_TAKEOFF):
            self.put(self.pilot, {"known_time_gate_predictions": {first: "2026-08-01T10:40:00Z"}})
        contestant = Contestant.objects.get(pk=self.contestant.pk)
        gate_times = contestant.adaptive_start_gate_times(datetime.datetime(2026, 8, 1, 10, 7, tzinfo=UTC))
        self.assertNotEqual(datetime.datetime(2026, 8, 1, 10, 40, tzinfo=UTC), gate_times[first])


class TestMessagesOfTheStrategies(PilotDeclarationTestBase):
    def errors(self, payload) -> list[str]:
        contestant = Contestant.objects.get(pk=self.contestant.pk)
        return ContestantTaskCompiler(contestant).compile(declaration_payload=payload, force=True).validation_errors

    def test_2a2_names_the_points_that_need_a_time(self):
        first, *_, last = self.declared_names()
        errors = self.errors({"known_time_gate_predictions": {first: "2026-08-01T10:10:00Z"}})
        remaining = self.declared_names()[1:]
        words = remaining[0] if len(remaining) == 1 else f"{', '.join(remaining[:-1])} and {remaining[-1]}"
        self.assertEqual([f"Give a time for {words}."], errors)


class TestCurveMessages(PilotDeclarationTestBase):
    task_subtype = CURVE_NAVIGATION_TIME_ESTIMATION

    def test_2a1_without_any_time_says_what_to_give(self):
        contestant = Contestant.objects.get(pk=self.contestant.pk)
        errors = ContestantTaskCompiler(contestant).compile(declaration_payload={}, force=True).validation_errors
        self.assertEqual(["Give the time you expect to be at each turn point and at the finish point."], errors)

    def test_2a1_beyond_tmax_says_which_time_is_too_late(self):
        self.navigation_task.task_config = {"curve_navigation_tmax_seconds": 90}
        self.navigation_task.save(update_fields=["task_config"])
        contestant = Contestant.objects.get(pk=self.contestant.pk)
        errors = (
            ContestantTaskCompiler(contestant)
            .compile(declaration_payload={"known_time_gate_predictions": {"FP": "2026-08-01T10:30:00Z"}}, force=True)
            .validation_errors
        )
        self.assertEqual(1, len(errors))
        self.assertIn("1 min 30 s after SP", errors[0])
        self.assertIn("Give an earlier time for FP.", errors[0])
