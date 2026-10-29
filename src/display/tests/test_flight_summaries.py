import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    ContestantTrack,
    Crew,
    FlightSummary,
    MyUser,
    NavigationTask,
    Person,
    Route,
    ScoreLogEntry,
    Team,
)
from display.models.scoring_models import ANOMALY
from display.services import flight_summaries
from display.utilities.tracking_definitions import TRACKING_PILOT
from utilities.mock_utilities import TraccarMock


def model_response(text, stop_reason="end_turn", input_tokens=2000, output_tokens=400):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


@override_settings(
    ANTHROPIC_API_KEY="test-key",
    FLIGHT_SUMMARY_DAILY_LIMIT_PER_USER=5,
    FLIGHT_SUMMARY_MONTHLY_BUDGET_USD=20,
    FLIGHT_SUMMARY_INPUT_USD_PER_MTOK=0.10,
    FLIGHT_SUMMARY_OUTPUT_USD_PER_MTOK=0.50,
)
class FlightSummaryTest(TestCase):
    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        delay = patch("display.tasks.generate_flight_summary.delay")
        self.delay = delay.start()
        self.addCleanup(delay.stop)
        now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(name="Summary Cup", start_time=now, finish_time=now, is_public=True)
        self.task = NavigationTask.create(
            name="Day 1",
            original_scorecard=get_default_scorecard(),
            start_time=now - datetime.timedelta(days=1),
            finish_time=now + datetime.timedelta(days=1),
            route=Route.objects.create(name="Route"),
            contest=self.contest,
            is_public=True,
        )
        self.pilot_user = MyUser.objects.create(username="pilot", email="pilot@example.com")
        self.copilot_user = MyUser.objects.create(username="copilot", email="copilot@example.com")
        self.stranger = MyUser.objects.create(username="stranger", email="stranger@example.com")
        self.superuser = MyUser.objects.create(username="admin", email="admin@example.com", is_superuser=True)
        crew = Crew.objects.create(
            member1=Person.objects.create(first_name="Pi", last_name="Lot", email="Pilot@example.com"),
            member2=Person.objects.create(first_name="Co", last_name="Pilot", email="copilot@example.com"),
        )
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-SUM"))
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.task,
            tracking_device=TRACKING_PILOT,
            contestant_number=1,
            tracker_start_time=now - datetime.timedelta(hours=5),
            takeoff_time=now - datetime.timedelta(hours=4),
            finished_by_time=now - datetime.timedelta(hours=2),
        )
        self.score(calculator_started=True, calculator_finished=True, score=42)
        ScoreLogEntry.objects.create(
            time=now - datetime.timedelta(hours=3),
            contestant=self.contestant,
            gate="SP",
            message="passing gate",
            points=30,
            offset_string="10 s",
            type=ANOMALY,
        )
        ScoreLogEntry.objects.create(
            time=now - datetime.timedelta(hours=3) + datetime.timedelta(minutes=5),
            contestant=self.contestant,
            gate="TP1",
            message="passing gate",
            points=12,
            offset_string="4 s",
            type=ANOMALY,
        )
        self.client = APIClient()

    def score(self, **fields):
        ContestantTrack.objects.update_or_create(contestant=self.contestant, defaults=fields)
        self.contestant.refresh_from_db()

    def url(self, suffix=""):
        return f"/api/v1/flight_summaries/{self.contestant.pk}/{suffix}"

    def generate(self, user, **data):
        self.client.force_authenticate(user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url("generate/"), data, format="json")

    def done_summary(self, **fields):
        defaults = dict(
            contestant=self.contestant,
            track_version=self.contestant.track_version,
            score_version=self.contestant.score_version,
            prompt_version=flight_summaries.PROMPT_VERSION,
            status=FlightSummary.STATUS_DONE,
            text="A fine flight.",
            requested_by=self.pilot_user,
            requested_at=datetime.datetime.now(datetime.timezone.utc),
        )
        defaults.update(fields)
        return FlightSummary.objects.create(**defaults)

    # Who may ask

    def test_the_pilot_starts_a_summary_whatever_the_case_of_the_email(self):
        response = self.generate(self.pilot_user)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], FlightSummary.STATUS_PENDING)
        summary = FlightSummary.objects.get()
        self.delay.assert_called_once_with(summary.pk)
        self.assertEqual(summary.requested_by, self.pilot_user)

    def test_the_copilot_may_ask_too(self):
        self.assertEqual(self.generate(self.copilot_user).status_code, 202)

    def test_someone_who_did_not_fly_it_gets_a_404_and_nothing_is_written(self):
        self.client.force_authenticate(self.stranger)
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertEqual(self.generate(self.stranger).status_code, 404)
        self.assertFalse(FlightSummary.objects.exists())
        self.delay.assert_not_called()

    def test_anonymous_users_are_refused(self):
        self.assertIn(self.client.get(self.url()).status_code, (401, 403))

    def test_a_superuser_may_ask_for_any_flight_without_a_daily_limit(self):
        for _ in range(6):
            self.done_summary(requested_by=self.superuser, track_version=100 + _)
        self.client.force_authenticate(self.superuser)
        state = self.client.get(self.url()).json()
        self.assertTrue(state["can_generate"])
        self.assertIsNone(state["remaining_today"])
        self.assertEqual(self.generate(self.superuser).status_code, 202)

    # When

    def test_a_flight_that_is_not_over_cannot_be_summarised(self):
        Contestant.objects.filter(pk=self.contestant.pk).update(
            finished_by_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        )
        response = self.generate(self.pilot_user)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(FlightSummary.objects.exists())

    def test_a_flight_still_being_scored_cannot_be_summarised(self):
        self.score(calculator_finished=False)
        self.assertEqual(self.generate(self.pilot_user).status_code, 409)
        self.client.force_authenticate(self.pilot_user)
        state = self.client.get(self.url()).json()
        self.assertFalse(state["can_generate"])
        self.assertEqual(state["reason"], "The flight is still being scored.")

    def test_without_an_api_key_the_feature_is_off(self):
        with override_settings(ANTHROPIC_API_KEY=""):
            self.client.force_authenticate(self.pilot_user)
            self.assertFalse(self.client.get(self.url()).json()["enabled"])
            self.assertEqual(self.generate(self.pilot_user).status_code, 503)

    # Written once per version of the scores

    def test_asking_again_returns_the_written_summary_without_a_new_generation(self):
        self.done_summary(requested_by=self.copilot_user)
        response = self.generate(self.pilot_user)
        self.assertEqual(response.json()["text"], "A fine flight.")
        self.assertEqual(FlightSummary.objects.count(), 1)
        self.delay.assert_not_called()
        self.assertEqual(flight_summaries.remaining_today(self.pilot_user), 5)

    def test_a_summary_being_written_is_not_started_twice(self):
        self.generate(self.pilot_user)
        self.generate(self.copilot_user)
        self.assertEqual(FlightSummary.objects.count(), 1)
        self.assertEqual(self.delay.call_count, 1)

    def test_new_scores_get_a_new_summary(self):
        self.done_summary()
        Contestant.objects.filter(pk=self.contestant.pk).update(score_version=self.contestant.score_version + 1)
        self.client.force_authenticate(self.pilot_user)
        self.assertTrue(self.client.get(self.url()).json()["can_generate"])
        self.assertEqual(self.generate(self.pilot_user).status_code, 202)
        self.assertEqual(FlightSummary.objects.count(), 2)
        self.delay.assert_called_once()

    def test_a_failed_summary_may_be_asked_for_again(self):
        failed = self.done_summary(status=FlightSummary.STATUS_FAILED, text="", error="boom")
        self.assertEqual(self.generate(self.pilot_user).status_code, 202)
        failed.refresh_from_db()
        self.assertEqual(failed.status, FlightSummary.STATUS_PENDING)
        self.delay.assert_called_once_with(failed.pk)

    def test_a_lost_generation_may_be_asked_for_again(self):
        lost = self.done_summary(
            status=FlightSummary.STATUS_PENDING,
            text="",
            requested_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
        )
        self.generate(self.pilot_user)
        self.delay.assert_called_once_with(lost.pk)

    def test_only_a_superuser_can_regenerate_a_written_summary(self):
        summary = self.done_summary()
        self.generate(self.pilot_user, regenerate=True)
        self.delay.assert_not_called()
        self.client.force_authenticate(self.superuser)
        self.assertTrue(self.client.get(self.url()).json()["can_regenerate"])
        self.assertEqual(self.generate(self.superuser, regenerate=True).status_code, 202)
        summary.refresh_from_db()
        self.assertEqual(summary.status, FlightSummary.STATUS_PENDING)
        self.delay.assert_called_once_with(summary.pk)

    # Limits

    def test_a_user_gets_five_new_summaries_a_day_and_failed_ones_do_not_count(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        for version in range(5):
            self.done_summary(track_version=100 + version)
        self.done_summary(track_version=200, status=FlightSummary.STATUS_FAILED)
        self.done_summary(track_version=300, requested_at=now - datetime.timedelta(days=2))
        response = self.generate(self.pilot_user)
        self.assertEqual(response.status_code, 429)
        self.client.force_authenticate(self.pilot_user)
        state = self.client.get(self.url()).json()
        self.assertEqual(state["remaining_today"], 0)
        self.assertFalse(state["can_generate"])
        # The co-pilot has not used theirs
        self.assertEqual(self.generate(self.copilot_user).status_code, 202)

    def test_the_monthly_budget_switches_new_summaries_off(self):
        self.done_summary(track_version=100, requested_by=self.stranger, cost_usd=Decimal("20.000001"))
        self.assertEqual(self.generate(self.pilot_user).status_code, 503)
        self.assertEqual(self.generate(self.superuser).status_code, 503)

    # Writing it

    def summary_row(self):
        return self.done_summary(status=FlightSummary.STATUS_PENDING, text="")

    def run_generation(self, response):
        client = MagicMock()
        client.messages.create.return_value = response
        summary = self.summary_row()
        with patch("anthropic.Anthropic", return_value=client):
            flight_summaries.generate(FlightSummary.objects.select_related("contestant").get(pk=summary.pk))
        summary.refresh_from_db()
        return summary, client.messages.create.call_args.kwargs

    def test_the_summary_is_written_from_the_score_log_without_names(self):
        summary, request = self.run_generation(
            model_response("You scored 42 points, placing 1st. You lost 30 points at SP and 12 points at TP1.")
        )
        self.assertEqual(summary.status, FlightSummary.STATUS_DONE)
        self.assertIn("42 points", summary.text)
        self.assertEqual(summary.input_tokens, 2000)
        self.assertEqual(summary.cost_usd, Decimal("0.000400"))
        self.assertEqual(request["model"], "claude-haiku-5-5")
        sent = request["messages"][0]["content"]
        self.assertIn('"gate": "SP"', sent)
        self.assertIn('"final_score": 42', sent)
        for name in ("Pi", "Lot", "pilot@example.com", "LN-SUM"):
            self.assertNotIn(name, sent)

    def test_points_the_score_log_does_not_have_fail_the_summary(self):
        summary, _ = self.run_generation(model_response("You lost 42 points at SP and 17 points elsewhere."))
        self.assertEqual(summary.status, FlightSummary.STATUS_FAILED)
        self.assertIn("17 points", summary.error)
        self.assertEqual(summary.text, "")
        # It still cost us: the budget counts it
        self.assertEqual(summary.cost_usd, Decimal("0.000400"))

    def test_a_refusal_fails_the_summary(self):
        summary, _ = self.run_generation(model_response("", stop_reason="refusal"))
        self.assertEqual(summary.status, FlightSummary.STATUS_FAILED)

    def test_the_task_skips_a_summary_that_is_no_longer_pending(self):
        from display.tasks import generate_flight_summary

        summary = self.done_summary()
        with patch("display.services.flight_summaries.generate") as generate:
            generate_flight_summary(summary.pk)
        generate.assert_not_called()

    def test_rank_follows_the_scorecard_direction(self):
        facts = flight_summaries.flight_facts(self.contestant)
        self.assertEqual((facts["rank"], facts["scored_flights_in_task"]), (1, 1))
        self.assertEqual(facts["penalty_totals_by_gate"], {"SP": 30, "TP1": 12})
