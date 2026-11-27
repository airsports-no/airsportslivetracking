"""
Where the flight order of a flight stands, for its own crew and for organisers (S22b of
documentation/PLAN_task_scoring_reliability.md), so that a pilot who has just saved the declaration sees "being made" and
then a download button instead of waiting for an e-mail.

What exists tells "ready": the newest EmailMapLink. Nothing that exists tells "being made" from "never started": the
progress dictionaries of display.tasks (``completed_flight_orders_map_<task>`` ...) are written only by the generating task,
so a task that is still queued leaves no trace, and they are shared by the whole navigation task and expire. So the places
that dispatch and run the generation also record a small per-flight marker here (cache, no model change): "queued" at
dispatch, "running" when the task starts, "done" or "failed" (with a reason for the pilot) when it ends.
"""

import datetime
import logging
from typing import Optional

from django.core.cache import cache

from display.models import Contestant
from display.services.declaration_access import (
    STATE_COMPLETE,
    STATE_INCOMPLETE,
    declaration_role,
    declaration_status,
)
from display.utilities.task_types import DECLARATION_NOT_NEEDED, DECLARATION_OPTIONAL, DECLARATION_REQUIRED

logger = logging.getLogger(__name__)

WAITING_FOR_DECLARATION = "waiting_for_declaration"
BEING_MADE = "being_made"
READY = "ready"
FAILED = "failed"
NOT_AVAILABLE = "not_available"

MARKER_QUEUED = "queued"
MARKER_RUNNING = "running"
MARKER_DONE = "done"
MARKER_FAILED = "failed"

# A flight order takes a minute or two; a marker that says "queued" or "running" for much longer than that belongs to a
# task that died with its worker (or to a rolled back save), and the pilot must be able to try again.
STALE_AFTER = datetime.timedelta(minutes=15)
MARKER_TIMEOUT_SECONDS = 7 * 24 * 3600

REASON_GENERIC = "The flight order could not be made. Ask the contest organiser if it keeps failing."
REASON_TOO_LARGE = "The map of this flight order is too large to make. Ask the contest organiser."
REASON_STALE = "The flight order took too long to make."


def _key(contestant_pk: int) -> str:
    return f"flight_order_state_{contestant_pk}"


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def record_flight_order_state(contestant_pk: int, state: str, reason: Optional[str] = None) -> None:
    """Notes where the generation of the flight order of a flight is. Never fails the caller: the status is only a convenience."""
    try:
        cache.set(
            _key(contestant_pk),
            {"state": state, "at": _utcnow().isoformat(), "reason": reason},
            MARKER_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.warning(f"Could not record the flight order state of contestant {contestant_pk}", exc_info=True)


def read_flight_order_state(contestant_pk: int) -> Optional[dict]:
    try:
        marker = cache.get(_key(contestant_pk))
    except Exception:
        logger.warning(f"Could not read the flight order state of contestant {contestant_pk}", exc_info=True)
        return None
    return marker if isinstance(marker, dict) else None


def last_generation_failed(contestant_pk: int) -> bool:
    marker = read_flight_order_state(contestant_pk)
    return bool(marker and marker.get("state") == MARKER_FAILED)


def _newest_link(contestant: Contestant):
    links = list(contestant.emailmaplink_set.all())
    return max(links, key=lambda link: link.created_at) if links else None


def _declaration_blocks_flight_order(declaration: dict) -> bool:
    """A required declaration that is not complete, or an optional one that was started and is not complete."""
    if declaration["need"] == DECLARATION_REQUIRED:
        return declaration["state"] != STATE_COMPLETE
    if declaration["need"] == DECLARATION_OPTIONAL:
        return declaration["state"] == STATE_INCOMPLETE
    return False


def makes_flight_orders_for_pilot(contestant: Contestant) -> bool:
    """
    Whether the system makes (and e-mails) the flight order of this flight itself: the pilot booked it themselves and
    has an address to send it to. A flight an organiser added gets its flight order when the organiser makes it.
    """
    pilot = contestant.team.crew.member1
    return bool(contestant.self_registered and pilot is not None and pilot.email)


def flight_order_status(contestant: Contestant, user=None, role_cache: Optional[dict] = None) -> Optional[dict]:
    """
    {"state", "path", "created_at", "reason"} for the crew of [contestant] and for organisers, None for anybody else.
    state is one of:
    waiting_for_declaration: the task needs a declaration and it is not complete, the flight order shows the declared route
    being_made: it is queued or being generated
    ready: [path] is the download page, [created_at] when it was made
    failed: [reason] says it in words for the pilot
    not_available: the system does not make it for this flight (an organiser makes those) or it is gone
    A flight order that exists is "ready" whatever else is true: it is the one the organiser made or the last good one, and a
    change of the declaration removes it (see delete_flight_orders_of_changed_declaration).
    """
    if declaration_role(user, contestant, role_cache) is None:
        return None
    declaration = declaration_status(contestant, user, role_cache=role_cache)

    def result(state, path=None, created_at=None, reason=None):
        return {"state": state, "path": path, "created_at": created_at, "reason": reason}

    link = _newest_link(contestant)
    if link is not None:
        return result(READY, f"/display/maplink/{link.pk}/", link.created_at.isoformat())
    if not makes_flight_orders_for_pilot(contestant):
        return result(NOT_AVAILABLE)
    if declaration["need"] != DECLARATION_NOT_NEEDED and _declaration_blocks_flight_order(declaration):
        return result(WAITING_FOR_DECLARATION)

    marker = read_flight_order_state(contestant.pk)
    if marker is None:
        return result(NOT_AVAILABLE)
    if marker["state"] == MARKER_FAILED:
        return result(FAILED, reason=marker.get("reason") or REASON_GENERIC)
    if marker["state"] in (MARKER_QUEUED, MARKER_RUNNING):
        started = datetime.datetime.fromisoformat(marker["at"])
        if _utcnow() - started > STALE_AFTER:
            return result(FAILED, reason=REASON_STALE)
        return result(BEING_MADE)
    # "done", but no flight order: it was removed since (kept five days after the flight)
    return result(NOT_AVAILABLE)
