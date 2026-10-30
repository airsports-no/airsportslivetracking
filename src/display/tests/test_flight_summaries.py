import datetime
import json
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


def model_response(text, stop_reason="end_turn", input_tokens=2000, output_tokens=400, raw=None, model=None):
    """The model's answer: a headline and one section holding the text."""
    answer = (
        raw
        if raw is not None
        else json.dumps(
            {
                "headline": "🏁 You finished 1st.",
                "sections": [{"emoji": "📉", "title": "Where the points went", "text": text}],
            }
        )
    )
    return SimpleNamespace(
        model=model,
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=answer)],
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
        # No weather from the network in tests: the analysis goes on without it
        weather = patch("display.services.flight_weather.fetch_weather", return_value=None)
        weather.start()
        self.addCleanup(weather.stop)
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
        self.assertEqual(
            response.json()["flight"],
            {"crew": "Pi Lot and Co Pilot", "contestant_number": 1, "task": "Day 1", "contest": "Summary Cup"},
        )
        summary = FlightSummary.objects.get()
        self.delay.assert_called_once_with(summary.pk)
        self.assertEqual(summary.requested_by, self.pilot_user)

    def test_a_browser_session_can_ask_for_a_summary(self):
        # Logged in by session, as the website is: request.user is then a lazy wrapper, not the user model itself
        self.client.force_login(self.pilot_user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url("generate/"), {"style": "pundit"}, format="json")
        self.assertEqual(response.status_code, 202)
        self.delay.assert_called_once()

    def test_the_live_map_learns_which_flights_the_user_may_summarise(self):
        url = f"/api/v1/flight_summaries/available/?navigation_task={self.task.pk}"
        for user, expected in (
            (self.copilot_user, {"enabled": True, "all": False, "contestant_ids": [self.contestant.pk]}),
            (self.stranger, {"enabled": True, "all": False, "contestant_ids": []}),
            (self.superuser, {"enabled": True, "all": True, "contestant_ids": []}),
        ):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(url).json(), expected)
        self.assertEqual(self.client.get("/api/v1/flight_summaries/available/").status_code, 400)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(url).status_code, (401, 403))

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
        # Shown as failed, so the modal offers to try again instead of spinning
        self.client.force_authenticate(self.pilot_user)
        state = self.client.get(self.url()).json()
        self.assertEqual(state["status"], FlightSummary.STATUS_FAILED)
        self.assertTrue(state["can_generate"])
        self.generate(self.pilot_user)
        self.delay.assert_called_once_with(lost.pk)

    def test_a_failed_summary_restarted_by_someone_else_meanwhile_is_not_started_again(self):
        failed = self.done_summary(status=FlightSummary.STATUS_FAILED, text="")
        read = flight_summaries._summaries_for_scores
        reads = []

        def read_then_restarted_elsewhere(*args):
            rows = read(*args)
            reads.append(rows)
            if len(reads) == 2:
                # Under the lock: this request has read the failed row, and another one restarts it before this one does
                FlightSummary.objects.filter(pk=failed.pk).update(
                    status=FlightSummary.STATUS_PENDING, requested_at=datetime.datetime.now(datetime.timezone.utc)
                )
            return rows

        with patch(
            "display.services.flight_summaries._summaries_for_scores", side_effect=read_then_restarted_elsewhere
        ):
            self.generate(self.copilot_user)
        self.delay.assert_not_called()
        # The other request's restart stands: this one did not take the row over
        failed.refresh_from_db()
        self.assertEqual(failed.requested_by, self.pilot_user)

    def test_the_quota_is_checked_again_under_the_lock(self):
        # Another request used the last summary of the day after this one passed the first check
        checks = iter([None, flight_summaries.FlightSummaryRefused("You have used today's AI summaries.", 429)])
        with patch("display.services.flight_summaries._refusal", side_effect=lambda *args, **kwargs: next(checks)):
            response = self.generate(self.pilot_user)
        self.assertEqual(response.status_code, 429)
        self.assertFalse(FlightSummary.objects.exists())
        self.delay.assert_not_called()

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

    def test_a_summary_written_with_an_earlier_prompt_is_shown_without_a_new_generation(self):
        self.done_summary(prompt_version=flight_summaries.PROMPT_VERSION - 1, text="An older summary.")
        response = self.generate(self.pilot_user)
        self.assertEqual(response.json()["text"], "An older summary.")
        self.assertFalse(response.json()["can_generate"])
        self.delay.assert_not_called()

    def test_regenerating_an_earlier_prompts_summary_writes_a_new_one_and_keeps_the_old(self):
        older = self.done_summary(prompt_version=flight_summaries.PROMPT_VERSION - 1, text="An older summary.")
        self.generate(self.superuser, regenerate=True)
        new = FlightSummary.objects.get(prompt_version=flight_summaries.PROMPT_VERSION)
        self.delay.assert_called_once_with(new.pk)
        older.refresh_from_db()
        self.assertEqual(older.text, "An older summary.")
        # While the new one is written it is what is shown; if it fails, the older one is shown again
        self.assertEqual(flight_summaries.current_summary(self.contestant), new)
        FlightSummary.objects.filter(pk=new.pk).update(status=FlightSummary.STATUS_FAILED)
        self.assertEqual(flight_summaries.current_summary(self.contestant), older)

    # Styles

    def test_each_style_is_a_summary_of_its_own(self):
        self.done_summary(text="A debrief.")
        self.client.force_authenticate(self.pilot_user)
        styles = self.client.get(self.url()).json()["styles"]
        self.assertEqual(
            [(style["key"], style["written"]) for style in styles],
            [("debrief", True), ("pundit", False), ("statistics", False), ("comedy", False)],
        )
        self.assertTrue(self.client.get(self.url() + "?style=pundit").json()["can_generate"])
        response = self.generate(self.pilot_user, style="pundit")
        self.assertEqual(response.json()["style"], "pundit")
        pundit = FlightSummary.objects.get(style="pundit")
        self.delay.assert_called_once_with(pundit.pk)
        self.assertEqual(self.client.get(self.url()).json()["text"], "A debrief.")

    def test_an_unknown_style_is_refused(self):
        self.client.force_authenticate(self.pilot_user)
        self.assertEqual(self.client.get(self.url() + "?style=limerick").status_code, 400)
        self.assertEqual(self.generate(self.pilot_user, style="limerick").status_code, 400)
        self.assertFalse(FlightSummary.objects.exists())

    def test_the_style_picks_the_voice_and_no_style_coaches(self):
        client = MagicMock()
        client.messages.create.return_value = model_response("You lost 30 points at SP.")
        summary = self.done_summary(status=FlightSummary.STATUS_PENDING, text="", style="pundit")
        with patch("anthropic.Anthropic", return_value=client):
            flight_summaries.generate(FlightSummary.objects.select_related("contestant").get(pk=summary.pk))
        system = client.messages.create.call_args.kwargs["system"]
        self.assertIn("pundit", system)
        self.assertIn("Do not give training advice", system)
        for style in flight_summaries.STYLES:
            self.assertNotIn("practise", flight_summaries.STYLES[style]["prompt"])

    @override_settings(FLIGHT_SUMMARY_COMEDY_MODEL="claude-sonnet-5-5")
    def test_comedy_is_written_by_its_own_model_with_a_fallback_and_priced_as_the_model_that_answered(self):
        client = MagicMock()
        client.beta.messages.create.return_value = model_response(
            "You lost 30 points at SP.", input_tokens=10_000, output_tokens=1_000, model="claude-sonnet-5-5"
        )
        summary = self.done_summary(status=FlightSummary.STATUS_PENDING, text="", style="comedy")
        with patch("anthropic.Anthropic", return_value=client):
            flight_summaries.generate(FlightSummary.objects.select_related("contestant").get(pk=summary.pk))
        summary.refresh_from_db()
        self.assertEqual(summary.status, FlightSummary.STATUS_DONE)
        client.messages.create.assert_not_called()
        request = client.beta.messages.create.call_args.kwargs
        self.assertEqual(request["model"], "claude-sonnet-5-5")
        self.assertEqual(request["fallbacks"], "default")
        self.assertEqual(summary.model, "claude-sonnet-5-5")
        # 10k in at $2 and 1k out at $10 per million
        self.assertEqual(summary.cost_usd, Decimal("0.030000"))

    def test_a_fallback_model_is_priced_at_its_own_rates(self):
        self.assertEqual(flight_summaries._cost("claude-opus-5-5", 1_000_000, 0), Decimal("4.000000"))
        # Unknown: the dearest known price, so the budget errs on the safe side
        self.assertEqual(flight_summaries._cost("claude-next", 1_000_000, 0), Decimal("5.000000"))

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

    def run_generation(self, response, attempts=1):
        client = MagicMock()
        client.messages.create.side_effect = [response] * attempts
        summary = self.summary_row()
        with patch("anthropic.Anthropic", return_value=client):
            flight_summaries.generate(FlightSummary.objects.select_related("contestant").get(pk=summary.pk))
        summary.refresh_from_db()
        return summary, client.messages.create.call_args.kwargs

    def test_the_summary_is_written_in_sections_from_the_score_log(self):
        summary, request = self.run_generation(
            model_response("You scored 42 points, placing 1st. You lost 30 points at SP and 12 points at TP1.")
        )
        self.assertEqual(summary.status, FlightSummary.STATUS_DONE)
        self.assertEqual(summary.headline, "🏁 You finished 1st.")
        self.assertEqual(summary.sections[0]["title"], "Where the points went")
        self.assertIn("42 points", summary.text)
        self.assertEqual(request["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(summary.input_tokens, 2000)
        self.assertEqual(summary.cost_usd, Decimal("0.000400"))
        self.assertEqual(request["model"], "claude-haiku-5-5")
        sent = request["messages"][0]["content"]
        self.assertIn('"gate": "SP"', sent)
        self.assertIn('"final_score": 42', sent)
        self.assertIn('"analysis"', sent)
        self.assertIsNone(summary.analysis["weather_source"])
        # Crews are named, as on the public map and results, but never with their e-mail or aeroplane
        self.assertIn("Pi Lot and Co Pilot", sent)
        for private in ("pilot@example.com", "LN-SUM"):
            self.assertNotIn(private, sent)

    def test_points_the_score_log_does_not_have_fail_the_summary(self):
        summary, _ = self.run_generation(
            model_response("You lost 42 points at SP and 17 points elsewhere."), attempts=2
        )
        self.assertEqual(summary.status, FlightSummary.STATUS_FAILED)
        self.assertIn("17 points", summary.error)
        self.assertEqual(summary.text, "")
        # Both attempts still cost us: the budget counts them
        self.assertEqual(summary.cost_usd, Decimal("0.000800"))

    def test_an_answer_that_is_not_the_schema_fails_the_summary(self):
        summary, _ = self.run_generation(model_response("", raw="Here is your summary!"))
        self.assertEqual(summary.status, FlightSummary.STATUS_FAILED)

    # Checking the points figures

    def facts(self):
        return {
            "final_score": 42,
            "events": [{"points": 30}, {"points": 12}, {"points": 9}],
            "penalty_totals_by_gate": {"SP": 30, "TP1": 21},
            "administrative_penalties": [],
            "analysis": {
                "crews": [
                    {"crew": "Ann Ace", "score": 17, "gates": {"SP": {"offset_seconds": 3, "points": 8}}},
                    {"crew": "Pi Lot and Co Pilot", "score": 42, "gates": {}, "you": True},
                    {"crew": "Bo Late", "score": 140, "gates": {"SP": {"offset_seconds": 50, "points": 77}}},
                ]
            },
        }

    def unsupported(self, text):
        return [item["figure"] for item in flight_summaries.unsupported_point_figures(text, self.facts())]

    def test_own_figures_and_totals_of_own_penalties_pass(self):
        self.assertEqual(self.unsupported("You scored 42 points. SP and TP1 cost you 39 points together."), [])

    def test_a_wrong_total_fails(self):
        self.assertEqual(self.unsupported("SP and TP1 cost you 40 points together."), ["40 points"])

    def test_figures_in_words_are_checked_too(self):
        self.assertEqual(self.unsupported("SP and TP1 cost you thirty-nine points together."), [])
        self.assertEqual(self.unsupported("You scored forty two points."), [])
        self.assertEqual(self.unsupported("SP cost you sixty-nine points."), ["sixty-nine points"])
        self.assertEqual(self.unsupported("Bo Late lost seventy-seven points at SP."), [])
        self.assertEqual(flight_summaries._number("one hundred and forty"), 140)

    def test_another_crews_figures_pass_only_in_a_sentence_that_names_it(self):
        self.assertEqual(self.unsupported("Bo Late lost 77 points at SP."), [])
        self.assertEqual(self.unsupported("Someone lost 77 points at SP."), ["77 points"])
        self.assertEqual(self.unsupported("Ann Ace lost 77 points at SP."), ["77 points"])

    def test_the_gap_to_a_named_crew_and_the_winners_score_pass(self):
        self.assertEqual(self.unsupported("You were 98 points ahead of Bo Late."), [])
        self.assertEqual(self.unsupported("The winner had 17 points. You were 25 points behind Ann Ace."), [])

    # Saying how different the wind was

    def wind_facts(self, planned=(13, 180), actual=(14, 252)):
        from display.services.flight_analysis import wind_difference

        return {
            "analysis": {
                "wind_difference": wind_difference(*planned, [{"speed_kt": actual[0], "direction": actual[1]}])
            }
        }

    def test_a_big_wind_difference_is_found(self):
        self.assertTrue(self.wind_facts()["analysis"]["wind_difference"]["big"])
        self.assertTrue(self.wind_facts(planned=(5, 270), actual=(15, 270))["analysis"]["wind_difference"]["big"])
        self.assertFalse(self.wind_facts(planned=(10, 250), actual=(12, 260))["analysis"]["wind_difference"]["big"])
        # Light winds: a different direction hardly matters
        self.assertFalse(self.wind_facts(planned=(3, 90), actual=(4, 200))["analysis"]["wind_difference"]["big"])

    def test_a_big_wind_difference_must_be_stated_with_both_winds(self):
        facts = self.wind_facts()
        self.assertIsNone(
            flight_summaries.missing_wind_difference("Planned 180° at 13 kt, but it blew 252° at 14 kt.", facts)
        )
        self.assertIn("planned 180° at 13 kt", flight_summaries.missing_wind_difference("It was windy.", facts))
        calm = self.wind_facts(planned=(0, 0), actual=(15, 250))
        self.assertIsNone(
            flight_summaries.missing_wind_difference("No wind was planned, but it was 250 degrees at 15 kt.", calm)
        )
        # Nothing to say when the wind was as planned
        self.assertIsNone(flight_summaries.missing_wind_difference("", self.wind_facts(actual=(13, 185))))

    def test_a_summary_that_leaves_out_a_big_wind_difference_is_corrected(self):
        from display.services.flight_analysis import wind_difference

        client = MagicMock()
        client.messages.create.side_effect = [
            model_response("You lost 30 points at SP."),
            model_response("You lost 30 points at SP. The plan had 180° at 13 kt, but it was 252° at 14 kt."),
        ]
        summary = self.summary_row()
        difference = wind_difference(13, 180, [{"speed_kt": 14, "direction": 252}])
        with (
            patch("anthropic.Anthropic", return_value=client),
            patch("display.services.flight_analysis.wind_difference", return_value=difference),
        ):
            flight_summaries.generate(FlightSummary.objects.select_related("contestant").get(pk=summary.pk))
        summary.refresh_from_db()
        self.assertEqual(summary.status, FlightSummary.STATUS_DONE)
        self.assertEqual(client.messages.create.call_count, 2)
        self.assertIn("very different", client.messages.create.call_args.kwargs["messages"][2]["content"])

    def test_comedy_does_not_have_to_mention_the_wind(self):
        from display.services.flight_analysis import wind_difference

        client = MagicMock()
        client.beta.messages.create.return_value = model_response("You lost 30 points at SP. Twice as funny.")
        summary = self.done_summary(status=FlightSummary.STATUS_PENDING, text="", style="comedy")
        difference = wind_difference(13, 180, [{"speed_kt": 14, "direction": 252}])
        with (
            patch("anthropic.Anthropic", return_value=client),
            patch("display.services.flight_analysis.wind_difference", return_value=difference),
        ):
            flight_summaries.generate(FlightSummary.objects.select_related("contestant").get(pk=summary.pk))
        summary.refresh_from_db()
        self.assertEqual(summary.status, FlightSummary.STATUS_DONE)
        self.assertEqual(client.beta.messages.create.call_count, 1)

    # Correcting the answer

    def test_points_the_data_does_not_have_are_corrected_once(self):
        client = MagicMock()
        client.messages.create.side_effect = [
            model_response("You lost 17 points elsewhere."),
            model_response("You lost 30 points at SP and 12 points at TP1."),
        ]
        summary = self.summary_row()
        with patch("anthropic.Anthropic", return_value=client):
            flight_summaries.generate(FlightSummary.objects.select_related("contestant").get(pk=summary.pk))
        summary.refresh_from_db()
        self.assertEqual(summary.status, FlightSummary.STATUS_DONE)
        self.assertIn("30 points at SP", summary.text)
        self.assertEqual(client.messages.create.call_count, 2)
        messages = client.messages.create.call_args.kwargs["messages"]
        self.assertEqual([message["role"] for message in messages], ["user", "assistant", "user"])
        self.assertIn('"17 points"', messages[2]["content"])
        # Both answers cost us
        self.assertEqual(summary.cost_usd, Decimal("0.000800"))

    def test_a_summary_that_wrote_a_different_prompt_version_is_refused(self):
        summary = self.done_summary(status=FlightSummary.STATUS_PENDING, text="", prompt_version=1)
        with patch("anthropic.Anthropic") as anthropic_client:
            flight_summaries.generate(FlightSummary.objects.select_related("contestant").get(pk=summary.pk))
        anthropic_client.assert_not_called()
        summary.refresh_from_db()
        self.assertEqual(summary.status, FlightSummary.STATUS_FAILED)

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
