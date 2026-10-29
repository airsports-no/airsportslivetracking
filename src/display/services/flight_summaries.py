"""
AI-written debriefs of scored flights.

A crew member (pilot or co-pilot) of a finished, scored flight may ask for a short written summary of it; superusers may
for any flight. The summary is generated once per version of the scores (see FlightSummary) by a Celery task that sends
the flight's score log to the model, so asking again is free until a restart or an administrative change bumps the
contestant's track_version or score_version. New generations are limited per user per day and by a monthly budget
(settings.FLIGHT_SUMMARY_*), since we pay for every one of them.

Only scoring facts are sent: the contest, task and scorecard, the score and placement, and the score log - no names.
"""

import datetime
import json
import logging
import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from display.models import Contestant, FlightSummary, ScoreLogEntry
from display.models.scoring_models import ANOMALY, INFORMATION

logger = logging.getLogger(__name__)

# Bump whenever the prompt or the facts sent change: every summary written before is then generated anew on request.
PROMPT_VERSION = 1

# A pending generation older than this is taken as lost (the worker died) and may be asked for again.
PENDING_TIMEOUT = datetime.timedelta(minutes=10)

MAX_OUTPUT_TOKENS = 4000

SYSTEM_PROMPT = """You write a short debrief of one flight in a general aviation competition (precision flying, air \
navigation race, rally and similar tasks), for the crew who flew it. You are given the flight's data from the official \
scoring system as JSON.

Rules:
- Use only facts that are in the data. Never guess why a penalty happened (wind, navigation, the aircraft, the crew's \
intentions) and never invent gates, times or events.
- Quote points only as they appear in the data, in the events, in penalty_totals_by_gate or as final_score. Do not add, \
subtract or round them yourself.
- final_score and rank are the official result; state them as given. score_sorting says whether a lower or a higher \
score is better.
- Start with one sentence on the result and the placement. Then describe where points were lost, the largest first, \
naming the gates and saying how early or late the crossing was or what happened. Then mention what went well, such as \
gates passed without penalty. End with one or two concrete things to practise, based only on the penalties.
- 120 to 250 words. Plain text in short paragraphs: no headings, no lists, no markdown. Address the crew as "you". \
Write in English."""


class FlightSummaryRefused(Exception):
    """A summary cannot be asked for. ``status_code`` is the HTTP status the API answers with."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def is_enabled() -> bool:
    return bool(settings.ANTHROPIC_API_KEY)


def is_crew(user, contestant: Contestant) -> bool:
    """Whether the user flew this flight, as pilot or co-pilot."""
    if not user.is_authenticated or not user.email:
        return False
    crew = contestant.team.crew
    return any(member and member.email.lower() == user.email.lower() for member in (crew.member1, crew.member2))


def may_view(user, contestant: Contestant) -> bool:
    return user.is_authenticated and (user.is_superuser or is_crew(user, contestant))


def not_scored_reason(contestant: Contestant) -> str | None:
    """Why the flight cannot be summarised yet, or None when it is over and its scores are final."""
    if contestant.finished_by_time > timezone.now():
        return "The flight is not over yet."
    try:
        track = contestant.contestanttrack
    except ObjectDoesNotExist:
        return "The flight has not been scored."
    if not track.calculator_started:
        return "The flight has not been scored."
    if not track.calculator_finished:
        return "The flight is still being scored."
    return None


def current_summary(contestant: Contestant) -> FlightSummary | None:
    """The summary written for the contestant's current scores, if anyone has asked for it."""
    return FlightSummary.objects.filter(
        contestant=contestant,
        track_version=contestant.track_version,
        score_version=contestant.score_version,
        prompt_version=PROMPT_VERSION,
    ).first()


def remaining_today(user) -> int | None:
    """How many more new summaries the user may ask for in the last 24 hours; None means no limit."""
    if user.is_superuser:
        return None
    used = (
        FlightSummary.objects.filter(requested_by=user, requested_at__gte=timezone.now() - datetime.timedelta(days=1))
        .exclude(status=FlightSummary.STATUS_FAILED)
        .count()
    )
    return max(0, settings.FLIGHT_SUMMARY_DAILY_LIMIT_PER_USER - used)


def spent_this_month() -> Decimal:
    start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return FlightSummary.objects.filter(requested_at__gte=start).aggregate(total=Sum("cost_usd"))["total"] or Decimal(0)


def budget_exhausted() -> bool:
    return spent_this_month() >= Decimal(str(settings.FLIGHT_SUMMARY_MONTHLY_BUDGET_USD))


def _is_lost(summary: FlightSummary) -> bool:
    return summary.status == FlightSummary.STATUS_PENDING and summary.requested_at < timezone.now() - PENDING_TIMEOUT


def _is_being_written(summary: FlightSummary | None) -> bool:
    return summary is not None and summary.status == FlightSummary.STATUS_PENDING and not _is_lost(summary)


def _needs_generation(summary: FlightSummary | None) -> bool:
    return summary is None or summary.status == FlightSummary.STATUS_FAILED or _is_lost(summary)


def _refusal(user, contestant: Contestant, new_generation: bool) -> FlightSummaryRefused | None:
    """Why the user may not have the flight's summary (or, with ``new_generation``, a newly written one)."""
    if not is_enabled():
        return FlightSummaryRefused("AI summaries are not available.", 503)
    if not may_view(user, contestant):
        return FlightSummaryRefused("Only the crew of a flight can ask for its summary.", 403)
    reason = not_scored_reason(contestant)
    if reason:
        return FlightSummaryRefused(reason, 409)
    if new_generation:
        if remaining_today(user) == 0:
            return FlightSummaryRefused("You have used today's AI summaries. Try again tomorrow.", 429)
        if budget_exhausted():
            return FlightSummaryRefused("AI summaries are paused for the rest of the month.", 503)
    return None


def summary_state(user, contestant: Contestant) -> dict:
    """What the website shows for the flight: the summary if there is one, and whether the user may ask for one."""
    summary = current_summary(contestant)
    refusal = _refusal(user, contestant, new_generation=_needs_generation(summary))
    data = {
        "enabled": is_enabled(),
        "status": summary.status if summary else None,
        "text": summary.text if summary and summary.status == FlightSummary.STATUS_DONE else "",
        "requested_at": summary.requested_at if summary else None,
        "can_generate": refusal is None and _needs_generation(summary),
        "can_regenerate": user.is_superuser
        and summary is not None
        and not _is_being_written(summary)
        and _refusal(user, contestant, new_generation=True) is None,
        "reason": str(refusal) if refusal else None,
        "remaining_today": remaining_today(user),
    }
    if user.is_superuser and summary:
        data.update(model=summary.model, cost_usd=str(summary.cost_usd), error=summary.error)
    return data


def request_summary(user, contestant: Contestant, regenerate: bool = False) -> FlightSummary:
    """
    Returns the summary of the flight's current scores, starting its generation when there is none (or the last attempt
    failed). Only a new generation counts against the user's daily quota. ``regenerate`` (superusers) writes it again.
    """
    existing = current_summary(contestant)
    regenerate = regenerate and user.is_superuser
    new_generation = _needs_generation(existing) or (regenerate and not _is_being_written(existing))
    refusal = _refusal(user, contestant, new_generation=new_generation)
    if refusal:
        raise refusal
    if not new_generation:
        return existing

    now = timezone.now()
    try:
        with transaction.atomic():
            if existing:
                FlightSummary.objects.filter(pk=existing.pk).update(
                    status=FlightSummary.STATUS_PENDING, text="", error="", requested_by=user, requested_at=now
                )
                existing.refresh_from_db()
                summary = existing
            else:
                summary = FlightSummary.objects.create(
                    contestant=contestant,
                    track_version=contestant.track_version,
                    score_version=contestant.score_version,
                    prompt_version=PROMPT_VERSION,
                    requested_by=user,
                    requested_at=now,
                )
    except IntegrityError:
        # Someone else asked for the same flight at the same moment: theirs is the one being written
        return current_summary(contestant)

    from display.tasks import generate_flight_summary

    transaction.on_commit(lambda: generate_flight_summary.delay(summary.pk))
    return summary


def _rank(contestant: Contestant, score: float) -> tuple[int, int]:
    """The flight's placement among the task's scored flights, and how many there are."""
    scores = list(
        Contestant.objects.filter(
            navigation_task=contestant.navigation_task, contestanttrack__calculator_finished=True
        ).values_list("contestanttrack__score", flat=True)
    )
    if contestant.navigation_task.score_sorting_direction == "desc":
        better = sum(1 for other in scores if other > score)
    else:
        better = sum(1 for other in scores if other < score)
    return better + 1, len(scores)


def flight_facts(contestant: Contestant) -> dict:
    """The scoring facts the model writes the summary from."""
    navigation_task = contestant.navigation_task
    scorecard = navigation_task.scorecard
    score = contestant.contestanttrack.score
    rank, scored_flights = _rank(contestant, score)
    entries = ScoreLogEntry.objects.filter(contestant=contestant, type__in=(ANOMALY, INFORMATION)).order_by(
        "time", "pk"
    )
    events = []
    totals_by_gate = {}
    for entry in entries:
        event = {"time": entry.time.isoformat(), "gate": entry.gate, "message": entry.message, "points": entry.points}
        if entry.offset_string:
            event["offset"] = entry.offset_string
        if entry.times_string:
            event["times"] = entry.times_string
        events.append(event)
        if entry.points and entry.gate:
            totals_by_gate[entry.gate] = round(totals_by_gate.get(entry.gate, 0) + entry.points, 2)
    penalties = [
        {"category": penalty.get_category_display(), "reason": penalty.reason, "points": penalty.score_log_entry.points}
        for penalty in contestant.administrativepenalty_set.select_related("score_log_entry")
    ]
    return {
        "contest": navigation_task.contest.name,
        "task": navigation_task.name,
        "task_type": scorecard.get_calculator_display(),
        "scorecard": scorecard.name,
        "score_sorting": "higher is better" if navigation_task.score_sorting_direction == "desc" else "lower is better",
        "final_score": score,
        "rank": rank,
        "scored_flights_in_task": scored_flights,
        "events": events,
        "penalty_totals_by_gate": totals_by_gate,
        "administrative_penalties": penalties,
    }


_POINTS_FIGURE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:penalty\s+)?(?:points?|pts)\b", re.IGNORECASE)


def unsupported_point_figures(text: str, facts: dict) -> list[str]:
    """The points figures in the summary that are nowhere in the facts: the model made them up or added them up."""
    known = {abs(facts["final_score"])}
    known.update(abs(event["points"]) for event in facts["events"])
    known.update(abs(total) for total in facts["penalty_totals_by_gate"].values())
    known.update(abs(penalty["points"]) for penalty in facts["administrative_penalties"])
    unsupported = []
    for match in _POINTS_FIGURE.finditer(text):
        value = float(match.group(1).replace(",", "."))
        if not any(abs(value - figure) < 0.05 for figure in known):
            unsupported.append(match.group(0))
    return unsupported


def _cost(input_tokens: int, output_tokens: int) -> Decimal:
    return Decimal(
        str(
            (
                input_tokens * settings.FLIGHT_SUMMARY_INPUT_USD_PER_MTOK
                + output_tokens * settings.FLIGHT_SUMMARY_OUTPUT_USD_PER_MTOK
            )
            / 1_000_000
        )
    ).quantize(Decimal("0.000001"))


def _fail(summary: FlightSummary, error: str):
    logger.warning(f"Flight summary {summary.pk} for contestant {summary.contestant_id} failed: {error}")
    summary.status = FlightSummary.STATUS_FAILED
    summary.error = error[:500]
    summary.save(update_fields=["status", "error", "input_tokens", "output_tokens", "cost_usd", "model"])


def generate(summary: FlightSummary):
    """Writes the summary with the model (the Celery task's work). Failures are stored on the row, not raised."""
    import anthropic

    contestant = summary.contestant
    facts = flight_facts(contestant)
    summary.model = settings.FLIGHT_SUMMARY_MODEL
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=60.0)
    try:
        response = client.messages.create(
            model=settings.FLIGHT_SUMMARY_MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": json.dumps(facts, indent=1)}],
        )
    except anthropic.APIError as e:
        _fail(summary, f"The model could not be reached: {e}")
        return
    # Retried rows keep what the earlier attempts cost, so the monthly budget sees all of it
    summary.input_tokens += response.usage.input_tokens
    summary.output_tokens += response.usage.output_tokens
    summary.cost_usd += _cost(response.usage.input_tokens, response.usage.output_tokens)
    if response.stop_reason == "refusal":
        _fail(summary, "The model declined to write the summary.")
        return
    if response.stop_reason == "max_tokens":
        _fail(summary, "The summary was cut off.")
        return
    text = "\n\n".join(block.text.strip() for block in response.content if block.type == "text").strip()
    if not text:
        _fail(summary, "The model wrote nothing.")
        return
    unsupported = unsupported_point_figures(text, facts)
    if unsupported:
        _fail(summary, f"The summary quotes points that are not in the score log: {', '.join(unsupported)}")
        return
    summary.text = text
    summary.status = FlightSummary.STATUS_DONE
    summary.error = ""
    summary.save(update_fields=["status", "text", "error", "input_tokens", "output_tokens", "cost_usd", "model"])
