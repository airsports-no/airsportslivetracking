"""
AI-written debriefs of scored flights.

A crew member (pilot or co-pilot) of a finished, scored flight may ask for a short written summary of it; superusers may
for any flight. The summary is generated once per version of the scores (see FlightSummary) by a Celery task that sends
the flight's score log to the model, so asking again is free until a restart or an administrative change bumps the
contestant's track_version or score_version. New generations are limited per user per day and by a monthly budget
(settings.FLIGHT_SUMMARY_*), since we pay for every one of them.

What is sent: the contest, task and scorecard, the score and placement, the score log, and the analysis of the legs,
wind, weather and the field (display.services.flight_analysis) - which names the crews as the public map and results
do, and of a task that is not public names only this crew. The model answers with a headline and a few titled
sections, which the website shows as cards.
"""

import datetime
import json
import logging
import re
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from display.models import Contestant, FlightSummary, ScoreLogEntry
from display.models.scoring_models import ANOMALY, INFORMATION
from display.services.flight_analysis import analyse_flight

logger = logging.getLogger(__name__)

# Bump whenever the prompt or the facts sent change. A summary written with an earlier version is still shown until the
# flight's scores change (writing them all again would cost us for nothing); superusers can regenerate it.
PROMPT_VERSION = 10

# A pending generation older than this is taken as lost (the worker died) and may be asked for again.
PENDING_TIMEOUT = datetime.timedelta(minutes=10)

MAX_OUTPUT_TOKENS = 6000

# The first answer, and one correction when it quotes points the data does not back
MAX_ATTEMPTS = 2

COMMON_PROMPT = """You write about one flight in a general aviation competition (precision flying, air navigation \
race, rally and similar tasks), for the crew who flew it. You are given the flight's data from the official scoring \
system as JSON, with an analysis of the legs, the wind, the weather and the rest of the field.

The data:
- events and penalty_totals_by_gate are this crew's official score log. final_score and rank are the official result; \
score_sorting says whether a lower or a higher score is better.
- analysis.planned_wind is the wind the gate times were planned with. analysis.legs gives each leg's planned and \
actual time and offset_at_end_seconds (positive: late at the gate at the end of the leg). actual_wind and \
actual_headwind_kt come from a weather model at analysis.wind_height_ft_above_ground. wind_effect_seconds is how much \
later (positive) or earlier that wind alone would have made a crew flying the planned airspeed exactly on that leg, \
compared with the planned wind. you_compared_with_plan and wind_alone_would_have_made_you say the same in words; \
use them to get earlier and later the right way round (a negative wind effect means the wind helped).
- analysis.weather is the weather model's conditions at the start, middle and finish of the flight.
- analysis.crews is every scored crew on the task, best first, with its score and its offset and points at each gate; \
"you": true marks this crew, and compared_with_you says whether each other crew did better or worse (use it to get \
ahead and behind the right way round). analysis.field_at_gates has the other crews' median offset at each gate and \
where this crew's timing ranks there (1 is the most precise). analysis.timing sums up the timing precision of this \
crew and the field. analysis.highlights are extra facts about this crew's flight.

Rules:
- Use only facts in the data. Never invent gates, times, events or causes.
- Quote points as they appear in the data: this crew's events, penalty_totals_by_gate and final_score, and other \
crews' scores and points at gates (name the crew in the same sentence). You may add up some of this crew's own \
penalties into a total, and give the gap between this crew's score and another crew's. Do not compute other figures \
or round them.
- Blame or credit the wind for timing only where the data supports it: a leg's change in offset close to its \
wind_effect_seconds, or most of the field being early or late at the same gates. Say when the crew did better or \
worse than the wind explains. Without wind or weather data, leave them out.
- analysis.wind_difference compares the planned wind with the wind through the flight. When its "big" is true, say \
plainly and early on that the wind was very different from the planned wind, with both (direction and speed, e.g. \
"planned 180° at 13 kt, but it was 252° at 14 kt"), and what that did to the timing - unless the style says otherwise.
- Mention the weather only if it was notable (fog, low cloud, rain, poor visibility, strong gusts), as what the \
weather model suggests, not as fact.
- Compare with the other crews where it tells something: who did best at a gate where this crew lost points, whether \
a problem gate caught everyone, the gap to the crews just above. You may name them.
- Do not give training advice or tell the crew what to practise or do differently: the data is not enough for that. \
Describe and compare; do not coach.
- Keep a light touch of humour, whatever the style: a wry remark or two, never at the expense of accuracy, and never \
mocking the crew (the comedy style may tease, affectionately).

The answer:
- headline: one short sentence, starting with a fitting emoji, as the style below says.
- sections as the style below says. Each has a fitting emoji, a short title and plain text (no markdown) in one or two \
short paragraphs. Leave out a section the flight gives nothing to say in. Address the crew as "you". Write in English.

"""

# The voices to choose from. Each is written and stored on its own (FlightSummary.style).
STYLES = {
    "debrief": {
        "label": "Debrief",
        "prompt": """Style: a friendly, sharp debrief, like an experienced competitor going through the flight with \
you afterwards. Clear and warm.
Headline: the result and placement.
Sections: 2 to 5, by topic, only those the flight has something to say about, most important first. Usually: where \
the points went; the wind and weather (only if they mattered); you and the field; the bright spots (with a fun fact \
from the highlights). 30 to 90 words each.""",
    },
    "pundit": {
        "label": "Pundit",
        "prompt": """Style: a television sports pundit or football commentator taking the viewers through the match \
afterwards. Big moments, drama and momentum: "and that is where it slipped away", "what a crossing at TP 3", the \
rivals around you in the table. Lively and colourful, but every fact from the data.
Headline: the result and placement, as a pundit's line.
Sections: tell it in order, as the story of the match - 3 or 4 phases of the flight (such as the opening from the \
start, the middle of the route, the finish), then the verdict: where it leaves you in the table and against the \
rivals. Title each phase by what happened in it ("Late, late, late at TP 2 and TP 3"), not "The opening". Weave the \
wind and weather into the phase where they mattered. 40 to 90 words each.""",
    },
    "statistics": {
        "label": "Statistics",
        "prompt": """Style: a technical analyst. Precise, compact and full of numbers from the data: offsets in \
seconds, points per gate, the timing figures in analysis.timing, ranks at gates, wind components and wind effects per \
leg. Short sentences; no drama. The page shows the gate and leg tables next to your text, so interpret them rather \
than repeat every row: patterns, outliers, where the points concentrate, how the timing compares with the field.
Headline: the result and placement, with the score.
Sections: 3 or 4 - scoring breakdown; timing precision; wind and legs; comparison with the field. 40 to 100 words \
each.""",
    },
    "comedy": {
        "label": "Comedy",
        "prompt": """Style: comedy, and actually funny. You are a sharp stand-up comedian who flies, doing a short set \
about this flight at the contest's prize-giving dinner. Write jokes, not descriptions with a joke attached: setups \
and punchlines, callbacks to an earlier joke, absurdly precise comparisons, comic exaggeration of how it felt (never \
of the facts), deadpan understatement of the disasters. Pick the two or three funniest things in the data - the most \
expensive moment, an absurd number, the rival who did it effortlessly, the wind if it is funny - build the set around \
them and leave the rest out. You do not have to cover everything, keep any order, or mention the wind.
Roast affectionately, as a friend who flew the same contest would: tease the decisions, the numbers and the luck, \
never the person, their looks or who they are, and no puns on names. Every fact and figure you use is real, from the \
data, so the jokes still tell what happened.
Headline: a punchline about the flight.
Sections: 1 to 3 bits, each titled like the name of a comedy bit, 50 to 120 words each.""",
        # Haiku's jokes were thin even with more effort; Sonnet is funny at low effort (about 10x the cost)
        "model_setting": "FLIGHT_SUMMARY_COMEDY_MODEL",
        # A joke does not have to be about the wind: the big-wind-difference check is skipped
        "states_wind": False,
    },
}
DEFAULT_STYLE = "debrief"


def system_prompt(style: str) -> str:
    return COMMON_PROMPT + STYLES[style]["prompt"]


ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"emoji": {"type": "string"}, "title": {"type": "string"}, "text": {"type": "string"}},
                "required": ["emoji", "title", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["headline", "sections"],
    "additionalProperties": False,
}


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


def summarisable_contestant_ids(user, navigation_task_id: int) -> tuple[bool, list[int]]:
    """
    Whether the user may have the summary of every flight of the task (superusers), and otherwise the flights in it the
    user flew, as pilot or co-pilot: for the live map, which shows the button only on these.
    """
    if user.is_superuser:
        return True, []
    if not user.email:
        return False, []
    flown = Q(team__crew__member1__email__iexact=user.email) | Q(team__crew__member2__email__iexact=user.email)
    return False, list(
        Contestant.objects.filter(flown, navigation_task_id=navigation_task_id).values_list("pk", flat=True)
    )


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


def _summaries_for_scores(
    contestant: Contestant, style: str = DEFAULT_STYLE
) -> tuple[FlightSummary | None, FlightSummary | None]:
    """
    For the contestant's current scores, in the style: the row of this prompt version, and the newest summary written
    before it.
    """
    rows = FlightSummary.objects.filter(
        contestant=contestant,
        track_version=contestant.track_version,
        score_version=contestant.score_version,
        style=style,
    ).order_by("-prompt_version")
    own = older = None
    for row in rows:
        if row.prompt_version == PROMPT_VERSION:
            own = row
        elif older is None and row.prompt_version < PROMPT_VERSION and row.status == FlightSummary.STATUS_DONE:
            older = row
    return own, older


def current_summary(contestant: Contestant, style: str = DEFAULT_STYLE) -> FlightSummary | None:
    """
    The summary of the contestant's current scores to show, if anyone has asked for one: this prompt version's when it
    is written or being written, and otherwise the newest one written with an earlier version.
    """
    own, older = _summaries_for_scores(contestant, style)
    if own and (own.status == FlightSummary.STATUS_DONE or _is_being_written(own)):
        return own
    return older or own


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


def _is_written(contestant: Contestant, style: str) -> bool:
    summary = current_summary(contestant, style)
    return summary is not None and summary.status == FlightSummary.STATUS_DONE


def summary_state(user, contestant: Contestant, style: str = DEFAULT_STYLE) -> dict:
    """What the website shows for the flight: the summary if there is one, and whether the user may ask for one."""
    summary = current_summary(contestant, style)
    refusal = _refusal(user, contestant, new_generation=_needs_generation(summary))
    data = {
        # Who flew it and where, for the heading
        "flight": {
            "crew": str(contestant.team.crew),
            "contestant_number": contestant.contestant_number,
            "task": contestant.navigation_task.name,
            "contest": contestant.navigation_task.contest.name,
        },
        "style": style,
        "styles": [
            {"key": key, "label": definition["label"], "written": _is_written(contestant, key)}
            for key, definition in STYLES.items()
        ],
        "enabled": is_enabled(),
        # A generation whose worker died shows as failed, so it can be asked for again instead of spinning forever
        "status": (FlightSummary.STATUS_FAILED if _is_lost(summary) else summary.status) if summary else None,
        "text": summary.text if summary and summary.status == FlightSummary.STATUS_DONE else "",
        "headline": summary.headline if summary and summary.status == FlightSummary.STATUS_DONE else "",
        "sections": summary.sections if summary and summary.status == FlightSummary.STATUS_DONE else [],
        "analysis": summary.analysis if summary and summary.status == FlightSummary.STATUS_DONE else None,
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


def request_summary(
    user, contestant: Contestant, regenerate: bool = False, style: str = DEFAULT_STYLE
) -> FlightSummary:
    """
    Returns the summary of the flight's current scores, starting its generation when there is none (or the last attempt
    failed). Only a new generation counts against the user's daily quota. ``regenerate`` (superusers) writes it again.
    """
    existing = current_summary(contestant, style)
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
            # The user's generations one at a time, with the quota checked again under the lock: parallel requests for
            # several flights cannot all pass the check
            get_user_model().objects.select_for_update().filter(pk=user.pk).first()
            refusal = _refusal(user, contestant, new_generation=True)
            if refusal:
                raise refusal
            # Always written as this prompt version: an earlier version's summary stays as it is
            own, _ = _summaries_for_scores(contestant, style)
            if own and (_is_being_written(own) or (own.status == FlightSummary.STATUS_DONE and not regenerate)):
                return own
            if own:
                # Only if nobody restarted it since it was read: two retries must not both pay for the model
                started = FlightSummary.objects.filter(
                    pk=own.pk, status=own.status, requested_at=own.requested_at
                ).update(status=FlightSummary.STATUS_PENDING, text="", error="", requested_by=user, requested_at=now)
                if not started:
                    return current_summary(contestant, style)
                own.refresh_from_db()
                summary = own
            else:
                summary = FlightSummary.objects.create(
                    contestant=contestant,
                    track_version=contestant.track_version,
                    score_version=contestant.score_version,
                    prompt_version=PROMPT_VERSION,
                    style=style,
                    requested_by=user,
                    requested_at=now,
                )
    except IntegrityError:
        # Someone else asked for the same flight at the same moment: theirs is the one being written
        return current_summary(contestant, style)

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


def _analysis(contestant: Contestant) -> dict:
    # The score log alone still makes a summary: a route or weather problem must not stop it
    try:
        return analyse_flight(contestant)
    except Exception:
        logger.exception(f"Could not analyse the flight of contestant {contestant.pk}")
        return {}


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
        "analysis": _analysis(contestant),
    }


_POINTS_FIGURE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:penalty\s+)?(?:points?|pts)\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_WINNER_WORDS = re.compile(r"\b(winner|won|wins|first|1st|leader|led|top)\b", re.IGNORECASE)
# Cents, so that sums of points with decimals compare exactly
_SCALE = 100
_MAX_SUMS = 200_000
_TOLERANCE = 5  # 0.05 points


def _scaled(value: float) -> int:
    return round(abs(value) * _SCALE)


def _subset_sums(values: list[float]) -> set[int]:
    """Every total some of the values add up to (bounded: past that, only the values themselves count)."""
    sums = {0}
    for value in (_scaled(value) for value in values if value):
        sums |= {total + value for total in sums}
        if len(sums) > _MAX_SUMS:
            return {_scaled(value) for value in values}
    return sums


def _own_figures(facts: dict) -> tuple[set[int], set[int]]:
    """This crew's points figures, and the totals its own penalty entries can add up to."""
    events = [event["points"] for event in facts["events"]]
    own = {_scaled(facts["final_score"])}
    own.update(_scaled(points) for points in events)
    own.update(_scaled(total) for total in facts["penalty_totals_by_gate"].values())
    own.update(_scaled(penalty["points"]) for penalty in facts["administrative_penalties"])
    return own, _subset_sums(events)


def _crew_figures(crew: dict, own_score: float) -> set[int]:
    figures = {_scaled(crew["score"]), _scaled(crew["score"] - own_score)}
    figures.update(_scaled(gate["points"]) for gate in crew["gates"].values() if "points" in gate)
    return figures


def unsupported_point_figures(text: str, facts: dict) -> list[dict]:
    """
    The points figures in the summary the data does not back, with their sentences. A sentence may quote this crew's own
    figures, or a total of some of its own penalties; a sentence that names another crew (or speaks of the winner) may
    also quote that crew's score and points and the gap to it.
    """
    own, own_sums = _own_figures(facts)
    crews = [crew for crew in facts.get("analysis", {}).get("crews", []) if not crew.get("you")]
    winner = facts.get("analysis", {}).get("crews", [None])[0] if facts.get("analysis", {}).get("crews") else None
    unsupported = []
    for sentence in (part for line in text.splitlines() for part in _SENTENCE_END.split(line)):
        figures = _POINTS_FIGURE.findall(sentence)
        if not figures:
            continue
        allowed = own | own_sums
        lowered = sentence.lower()
        for crew in crews:
            if crew["crew"] and re.search(rf"\b{re.escape(crew['crew'].lower())}\b", lowered):
                allowed |= _crew_figures(crew, facts["final_score"])
        if winner and _WINNER_WORDS.search(sentence):
            allowed |= _crew_figures(winner, facts["final_score"])
        for figure in figures:
            value = _scaled(float(figure.replace(",", ".")))
            if not any(abs(value - known) <= _TOLERANCE for known in allowed):
                unsupported.append({"figure": f"{figure} points", "sentence": sentence.strip()})
    return unsupported


# USD per million input and output tokens of the models a summary can be written by (a style's model, or the model a
# declined request falls back to), for counting what the summaries cost. Keep in step with Anthropic's prices; the
# default model's are in the settings.
MODEL_PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
}
# The API answers with another model if these decline a request (only Sonnet 5.5 of ours has it)
MODELS_WITH_FALLBACK = {"claude-sonnet-5-5"}


def style_model(style: str) -> str:
    setting = STYLES[style].get("model_setting")
    return getattr(settings, setting) if setting else settings.FLIGHT_SUMMARY_MODEL


def _cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    if model == settings.FLIGHT_SUMMARY_MODEL:
        prices = (settings.FLIGHT_SUMMARY_INPUT_USD_PER_MTOK, settings.FLIGHT_SUMMARY_OUTPUT_USD_PER_MTOK)
    else:
        # An unknown model is counted at the dearest known price, so the budget errs on the safe side
        prices = MODEL_PRICES.get(model, max(MODEL_PRICES.values()))
    return Decimal(str((input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000)).quantize(
        Decimal("0.000001")
    )


def _fail(summary: FlightSummary, error: str):
    logger.warning(f"Flight summary {summary.pk} for contestant {summary.contestant_id} failed: {error}")
    summary.status = FlightSummary.STATUS_FAILED
    summary.error = error[:500]
    summary.save(update_fields=["status", "error", "input_tokens", "output_tokens", "cost_usd", "model"])


_KNOTS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:kt|kts|knots?)\b", re.IGNORECASE)
_CALM = re.compile(r"\b(no wind|calm|without wind|zero wind|nil wind)\b", re.IGNORECASE)
_DEGREES = re.compile(r"(\d{1,3})\s*(?:°|degrees)", re.IGNORECASE)


def missing_wind_difference(text: str, facts: dict) -> str | None:
    """
    When the wind was very different from the planned one, the summary must give both: what is missing, or None.
    """
    difference = (facts.get("analysis") or {}).get("wind_difference")
    if not difference or not difference["big"]:
        return None
    knots = [float(value) for value in _KNOTS.findall(text)]
    degrees = [float(value) for value in _DEGREES.findall(text)]

    def stated(wind: dict) -> bool:
        if wind["speed_kt"] < 1:
            # A calm plan has no direction to give
            return bool(_CALM.search(text)) or any(value < 1 for value in knots)
        has_speed = any(abs(value - wind["speed_kt"]) <= 1.5 for value in knots)
        has_direction = any(abs((value - wind["direction"] + 180) % 360 - 180) <= 10 for value in degrees)
        return has_speed and has_direction

    if stated(difference["planned"]) and stated(difference["actual"]):
        return None
    planned, actual = difference["planned"], difference["actual"]
    return (
        "The wind was very different from the planned wind, and the summary must say so plainly and early on, with "
        "both: planned "
        + ("no wind" if planned["speed_kt"] < 1 else f"{planned['direction']:.0f}° at {planned['speed_kt']:.0f} kt")
        + f", and {actual['direction']:.0f}° at {actual['speed_kt']:.0f} kt through the flight."
    )


def _read_answer(response) -> tuple[str, list[dict]]:
    answer = json.loads(next(block.text for block in response.content if block.type == "text"))
    headline = answer["headline"].strip()
    sections = [
        {"emoji": section["emoji"].strip(), "title": section["title"].strip(), "text": section["text"].strip()}
        for section in answer["sections"]
    ]
    return headline, sections


def _as_text(headline: str, sections: list[dict]) -> str:
    # The plain text keeps the whole summary readable where the sections are not shown
    return "\n\n".join([headline] + [f"{s['emoji']} {s['title']}\n{s['text']}" for s in sections]).strip()


def _correction(unsupported: list[dict], missing_wind: str | None) -> str:
    parts = []
    if unsupported:
        problems = "\n".join(f'- "{item["figure"]}" in: "{item["sentence"]}"' for item in unsupported)
        parts.append(
            "These points figures are not in the data (and are not a total of this crew's own penalties, or another "
            f"crew's figures in a sentence that names it):\n{problems}\n"
            "Rewrite only the sentences with them, using figures from the data."
        )
    if missing_wind:
        parts.append(missing_wind)
    parts.append("Keep everything else as it was, and answer with the whole summary again.")
    return "\n\n".join(parts)


def generate(summary: FlightSummary):
    """
    Writes the summary with the model (the Celery task's work). If the answer quotes points the data does not back, the
    model is asked once to correct them. Failures are stored on the row, not raised.
    """
    import anthropic

    if summary.prompt_version != PROMPT_VERSION:
        # Asked for by a newer (or older) web server than this worker: written by the wrong prompt it would be cached
        # under the other version's key
        _fail(summary, f"This worker writes prompt version {PROMPT_VERSION}, not {summary.prompt_version}.")
        return
    contestant = summary.contestant
    facts = flight_facts(contestant)
    model = style_model(summary.style)
    summary.model = model
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=60.0)
    messages = [{"role": "user", "content": json.dumps(facts, indent=1)}]
    for attempt in range(MAX_ATTEMPTS):
        try:
            request = dict(
                model=model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=system_prompt(summary.style),
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": ANSWER_SCHEMA}},
                messages=messages,
            )
            if model in MODELS_WITH_FALLBACK:
                response = client.beta.messages.create(
                    **request, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
                )
            else:
                response = client.messages.create(**request)
        except anthropic.APIError as e:
            _fail(summary, f"The model could not be reached: {e}")
            return
        # Retried rows keep what the earlier attempts cost, so the monthly budget sees all of it
        summary.input_tokens += response.usage.input_tokens
        summary.output_tokens += response.usage.output_tokens
        # Priced as the model that answered: a fallback model has its own rates
        summary.cost_usd += _cost(response.model or model, response.usage.input_tokens, response.usage.output_tokens)
        if response.stop_reason == "refusal":
            _fail(summary, "The model declined to write the summary.")
            return
        if response.stop_reason == "max_tokens":
            _fail(summary, "The summary was cut off.")
            return
        try:
            headline, sections = _read_answer(response)
        except (StopIteration, ValueError, KeyError, TypeError, AttributeError):
            _fail(summary, "The model's answer could not be read.")
            return
        if not headline or not sections:
            _fail(summary, "The model wrote nothing.")
            return
        text = _as_text(headline, sections)
        unsupported = unsupported_point_figures(text, facts)
        missing_wind = missing_wind_difference(text, facts) if STYLES[summary.style].get("states_wind", True) else None
        if not unsupported and not missing_wind:
            break
        logger.info(f"Flight summary {summary.pk}: asking for a correction of {unsupported} {missing_wind or ''}")
        messages += [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": _correction(unsupported, missing_wind)},
        ]
    else:
        if unsupported:
            figures = ", ".join(item["figure"] for item in unsupported)
            _fail(summary, f"The summary quotes points that are not in the data: {figures}")
        else:
            _fail(summary, "The summary does not say how different the wind was from the planned wind.")
        return
    summary.text = text
    summary.headline = headline
    summary.sections = sections
    summary.analysis = facts["analysis"]
    summary.status = FlightSummary.STATUS_DONE
    summary.error = ""
    summary.save(
        update_fields=[
            "status",
            "text",
            "headline",
            "sections",
            "analysis",
            "error",
            "input_tokens",
            "output_tokens",
            "cost_usd",
            "model",
        ]
    )
