"""
The weight of a gate in the raw quality Q of the tasks that follow the catalogue's formulas literally (2.A1, 2.A2).

One place decides what a gate is worth and what losing it costs, and both the live GateCalculator (the deductions it
logs as the flight goes) and task_scoring (the quality a flight starts from) ask it, so the starting quality and the
sum of everything that can be deducted cannot drift apart.

2.A1: Qh = 1000 x H / Nh (a hidden gate is worth 1000 / Nh), Qt = Emax x Nt - Et (a time gate is worth Emax and loses
      its error, at most Emax; Emax if it was not flown). SP and FP are not time gates, hidden gates are not timed.
2.A2: Qp = Emax x Ng (a hidden gate is worth Emax), Qt = -sum(Ei) (every error deducts, at most Emax, Emax for a gate
      not crossed), so a hidden gate that was not crossed loses its value and Emax. SP is time zero; the hidden gates
      and FP are time gates.
2.A3: Qt = Emax x 3 - Et over SP, MP and FP (each worth Emax and losing its error, Emax if not flown). Qp = 1000 x V /
      Vmax is a share of the best contestant of the task, so here a gate only has a count in V: +1 for a declared turn
      point flown in order, -1 for a declared point (SP, MP and FP included) not flown or not in order. The calculator
      logs that count and task_scoring turns it into points once Vmax is known.
A hidden gate crossed twice, or first crossed against the route, is invalidated: it loses its value. Its time comes
from the first crossing (2.A1: "time will be extracted from the first crossing"), which is charged when it is crossed,
except for a crossing against the route, which is the first and only one and is timed as it happens.

Emax and the points per second of error come from the scorecard's gate scores (the catalogue's "typically 180" and one
point per second), where each gate type keeps its own. Gate types the model does not cover (take-off, landing, ...)
keep the scorecard's flat scores.
"""

import datetime
from typing import Iterable, Optional

from display.utilities.gate_definitions import DUMMY, FINISHPOINT, SECRETPOINT, STARTINGPOINT, TURNPOINT
from display.utilities.task_types import CatalogueGateModel, TaskTypeDefinition

_COVERED_TYPES = (STARTINGPOINT, TURNPOINT, SECRETPOINT, FINISHPOINT)


def _counts(item) -> bool:
    """A waypoint or gate that is part of the route's scoring (not a dummy, not a point on a curved leg)."""
    return item.type != DUMMY and not getattr(item, "on_curved_segment", False)


class CatalogueGateQuality:
    """The points of the gates of one task; `items` are the waypoints (or gates) of the contestant's effective route."""

    def __init__(self, model: CatalogueGateModel, scorecard, items: Iterable):
        self.model = model
        self.scorecard = scorecard
        # Nh: the hidden gates that can be missed.
        self.hidden_gate_count = sum(1 for item in items if self._is_hidden(item) and item.gate_check)

    @classmethod
    def for_task_type(
        cls, definition: TaskTypeDefinition, scorecard, items: Iterable
    ) -> Optional["CatalogueGateQuality"]:
        """The weights of a task type that follows the catalogue's formulas, None for the others."""
        if definition.catalogue_gate_model is None:
            return None
        return cls(definition.catalogue_gate_model, scorecard, [item for item in items if _counts(item)])

    # -- what a gate is -------------------------------------------------------------------------------------------

    @staticmethod
    def _is_hidden(item) -> bool:
        return item.type == SECRETPOINT

    def covers(self, item) -> bool:
        return item.type in _COVERED_TYPES

    def is_timed(self, item) -> bool:
        """Whether the crossing time of the gate scores: it has a time check and is a time gate of the task."""
        if not item.time_check:
            return False
        if not self.covers(item):
            return True  # the scorecard's flat scores decide
        if item.type == TURNPOINT:
            return True
        if item.type == SECRETPOINT:
            return self.model.hidden_gates_timed
        if item.type == FINISHPOINT:
            return self.model.finish_point_timed
        return self.model.start_point_timed

    # -- what it is worth -----------------------------------------------------------------------------------------

    def hidden_gate_value(self, item) -> float:
        """What a hidden gate correctly crossed is worth: 0 for every other gate and for a hidden gate nobody checks."""
        if not self._is_hidden(item) or not item.gate_check:
            return 0.0
        if self.model.hidden_gate_value_is_share_of_total:
            return self.model.hidden_gates_total / self.hidden_gate_count
        return self._timing_cap(item.type)

    def _timing_cap(self, gate_type: str) -> float:
        """Emax of the gate type."""
        return abs(self.scorecard.get_gate_scorecard(gate_type).maximum_penalty)

    def starting_quality(self, item) -> float:
        """What the gate adds to the quality a perfect flight has: its value and, where a time gate is worth Emax, Emax."""
        if not self.covers(item):
            return self._flat_worst_case(item)
        credit = self._timing_cap(item.type) if self.model.time_gate_is_worth_emax and self.is_timed(item) else 0.0
        return self.hidden_gate_value(item) + credit

    def _flat_worst_case(self, item) -> float:
        """The scorecard's worst single deficit of a gate the model does not cover."""
        gate_score = self.scorecard.get_gate_scorecard(item.type)
        worst_if_missed = abs(gate_score.missed_penalty) if item.gate_check else 0
        worst_if_crossed_badly = abs(gate_score.maximum_penalty) if item.time_check else 0
        return max(worst_if_missed, worst_if_crossed_badly)

    # -- what it counts in V (2.A3) -------------------------------------------------------------------------------

    def counts_in_v(self, item) -> bool:
        """Whether the task counts the declared points in V = N - Ep, and `item` is one of them."""
        return self.model.declared_points_count_in_v and self.covers(item) and bool(item.gate_check)

    def v_gain(self, item) -> int:
        """What a declared turn point flown in order adds to V: 1. SP, MP and FP are timed, not turn points of N."""
        return 1 if self.counts_in_v(item) and item.type == TURNPOINT and not item.time_check else 0

    def v_loss(self, item) -> int:
        """What a declared point not flown, or not in order, takes off V: 1, SP, MP and FP included (Ep)."""
        return 1 if self.counts_in_v(item) else 0

    # -- what losing it costs -------------------------------------------------------------------------------------

    def timing_loss(self, item, expected: datetime.datetime, actual: Optional[datetime.datetime]) -> float:
        """The time error of a gate, at most Emax; `actual` None (not flown) is Emax."""
        if actual is None:
            return self._timing_cap(item.type)
        return self.scorecard.get_gate_timing_score_for_gate_type(item.type, expected, actual)

    def missed_loss(self, item) -> float:
        """What a gate that was not crossed costs: its value and, as a time gate, Emax."""
        if not self.covers(item):
            return self.scorecard.get_gate_timing_score_for_gate_type(item.type, None, None) if item.gate_check else 0.0
        if not item.gate_check:
            return 0.0
        timing = self.timing_loss(item, None, None) if self.is_timed(item) else 0.0
        return self.hidden_gate_value(item) + timing

    def invalidated_loss(
        self, item, expected: Optional[datetime.datetime] = None, crossing_time: Optional[datetime.datetime] = None
    ) -> float:
        """
        What a hidden gate that was crossed again or first crossed against the route costs: its value. Given the time of
        a crossing against the route (the only crossing there is, so its time counts) a time gate's error is added.
        """
        loss = self.hidden_gate_value(item)
        if crossing_time is not None and expected is not None and self.is_timed(item):
            loss += self.timing_loss(item, expected, crossing_time)
        return loss
