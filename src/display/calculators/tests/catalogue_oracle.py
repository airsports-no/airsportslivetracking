"""An independent, pure-Python implementation of the CIMA task catalogue scoring (FAI Section 10, Annex 4, part 2).

The scenario tests fly synthetic tracks through the application and compare the application's final score with what
this module says the catalogue prescribes. It therefore imports nothing from the application: every rule is restated
here from the catalogue (documentation/cima/cima_task_catalog.md and the plan's appendix), taking plain inputs - what
was flown (gates crossed correctly, timing errors in seconds, counts, radii, durations, penalties incurred) - and
returning the raw quality score Q of one pilot.

Final score of a task (Annex 3, 3.4.1 and 2.3.4; S10 4.34):

* P = task_value x Q / Qmax where Qmax is the BEST Q among the pilots of the task (all contestants are one class) and
  task_value is 1000 unless the organiser announced another value. A pilot with Q <= 0 scores 0.
* Tasks with an absolute score are not divided by the best pilot: 2.A7 (P = (Rmin/Rmax - 0.5) x 500, at most 250) and
  2.A8 (Q = 2000 - penalties, P = 1000 x Q / 2000).
* Percentage penalties (50% backtracking for 2.A1-2.A5, 20% altitude for 2.A7, 100% penalties) are applied to P after
  the normalisation; a negative score becomes 0; the result is a whole number with 0.5 rounded up.

Where the catalogue's wording is open the choice made here is stated at the function: Qmax is taken after the pilots'
own point deductions but before any percentage penalty, percentage penalties of one pilot are added up (and capped at
100%), and a time error counts at most Emax.
"""

import math
from typing import Optional, Sequence

TASK_VALUE = 1000.0
EMAX = 180.0  # seconds: the catalogue's "typically 180"
HIDDEN_GATE_VALUE_2A2 = 180.0
BACKTRACKING_PENALTY = 0.5  # 2.A1-2.A5
ALTITUDE_PENALTY = 0.2  # 2.A7
FULL_PENALTY = 1.0

# 2.A6 / 2.B2 (typical values, "briefed prior to the task")
PHOTO_VALUE = 100.0
TIME_GATE_VALUE = 200.0
TIMING_TOLERANCE_S = 10.0
TIMING_PENALTY_PER_SECOND = 10.0

# 2.A7
CIRCLE_MAXIMUM_SCORE = 250.0
CIRCLE_RADIUS_LIMITS_M = (200.0, 750.0)
CIRCLE_ALTITUDE_BAND_FT = 200.0

# 2.A8
ANR_START_POINTS = 2000.0


# ---------------------------------------------------------------------------------------------------------------------
# Final score
# ---------------------------------------------------------------------------------------------------------------------


def round_half_up(value: float) -> int:
    """A whole number, 0.5 rounded up (also for negative values: -0.5 becomes 0)."""
    return int(math.floor(value + 0.5))


def normalised_scores(qs: Sequence[float], task_value: float = TASK_VALUE) -> list[float]:
    """P = task_value x Q / Qmax for every pilot, Qmax being the best Q of the task. Nobody above zero: everybody 0."""
    qmax = max(qs, default=0.0)
    if qmax <= 0:
        return [0.0 for _ in qs]
    return [task_value * q / qmax for q in qs]


def apply_percentage_penalties(score: float, penalties: Sequence[float] = ()) -> float:
    """Take the percentages (0.5 is 50%) off the score; the penalties of one pilot add up, at most 100%."""
    return score * (1.0 - min(1.0, sum(penalties)))


def finish_score(score: float) -> int:
    """The published score: never negative, whole number, 0.5 rounded up."""
    return max(0, round_half_up(score))


def final_scores(
    qs: Sequence[float],
    percentage_penalties: Optional[Sequence[Sequence[float]]] = None,
    task_value: float = TASK_VALUE,
) -> list[int]:
    """The final score P of every pilot of a task from their raw Q and (optional) lists of percentage penalties."""
    penalties = percentage_penalties or [() for _ in qs]
    return [
        finish_score(apply_percentage_penalties(score, pilot_penalties))
        for score, pilot_penalties in zip(normalised_scores(qs, task_value), penalties)
    ]


# ---------------------------------------------------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------------------------------------------------


def time_error(seconds: Optional[float], emax: float = EMAX) -> float:
    """The absolute error of a time gate, at most Emax; a gate that was not flown (None) counts Emax."""
    if seconds is None:
        return emax
    return min(abs(seconds), emax)


def correct_hidden_gates(crossings: Sequence[tuple[int, int]]) -> list[int]:
    """The hidden gates that count, from the crossings in the order they happened.

    Each crossing is (gate number in route order, direction) with direction +1 along the route and -1 against it.
    A gate counts when it was crossed exactly once (a second crossing in any direction invalidates it), in the proper
    direction, and after the gates that counted before it in route order. The catalogue's own example: the sequence
    1-2-4-3-5-6-5-7 is evaluated as 1-2-4-6-7, five correct gates.
    """
    counts: dict[int, int] = {}
    for gate, _ in crossings:
        counts[gate] = counts.get(gate, 0) + 1
    valid: list[int] = []
    for gate, direction in crossings:
        if counts[gate] != 1 or direction != 1:
            continue
        if valid and gate < valid[-1]:
            continue
        valid.append(gate)
    return valid


# ---------------------------------------------------------------------------------------------------------------------
# 2.A1 Curve navigation with time estimation
# ---------------------------------------------------------------------------------------------------------------------


def q_curve_navigation(
    hidden_gates: int,
    hidden_correct: int,
    time_errors: Sequence[Optional[float]],
    emax: float = EMAX,
) -> float:
    """2.A1: Qh = 1000 x H / Nh; Qt = Emax x Nt - Et; Q = Qh + Qt. SP and FP are not time gates of the task.

    `time_errors` has one entry per known time gate, in seconds, None for a gate that was not flown. Without hidden
    gates the spatial part is dropped, and without time gates the time part.
    """
    spatial = 1000.0 * hidden_correct / hidden_gates if hidden_gates else 0.0
    temporal = emax * len(time_errors) - sum(time_error(error, emax) for error in time_errors)
    return spatial + temporal


# ---------------------------------------------------------------------------------------------------------------------
# 2.A2 Precision navigation
# ---------------------------------------------------------------------------------------------------------------------


def q_precision_navigation(
    hidden_correct: int,
    time_errors: Sequence[Optional[float]],
    emax: float = EMAX,
    gate_value: float = HIDDEN_GATE_VALUE_2A2,
) -> float:
    """2.A2: every hidden gate correctly crossed scores 180 (Qp = Emax x Ng); every second of error of a gate scores one
    negative point, at most Emax, Emax for a gate not crossed (Qt = -sum Ei); Q = Qp + Qt."""
    return gate_value * hidden_correct - sum(time_error(error, emax) for error in time_errors)


# ---------------------------------------------------------------------------------------------------------------------
# 2.A3 Contract navigation with time controls
# ---------------------------------------------------------------------------------------------------------------------


def contract_v(flown_in_order: int, not_flown_or_out_of_order: int) -> int:
    """V = N - Ep: N the declared turn points (not SP, MP, FP) flown in order, Ep the declared points not flown or not
    in order, SP, MP and FP included."""
    return flown_in_order - not_flown_or_out_of_order


def q_contract_navigation(
    v: float,
    vmax: float,
    time_errors: Sequence[Optional[float]],
    emax: float = EMAX,
) -> float:
    """2.A3: Qp = 1000 x V / Vmax (Vmax: the best V of the task); Qt = Emax x 3 - Et over SP, MP and FP."""
    spatial = 1000.0 * v / vmax if vmax > 0 else 0.0
    temporal = emax * 3 - sum(time_error(error, emax) for error in time_errors)
    return spatial + temporal


# ---------------------------------------------------------------------------------------------------------------------
# 2.A4 Navigation over a known circuit and 2.A5 Navigation with unknown legs
# ---------------------------------------------------------------------------------------------------------------------


def q_observation_navigation(
    hidden_correct: int,
    time_errors_crossed: Sequence[float],
    *,
    hidden_value: float = 100.0,
    gate_value: float = 180.0,
    speed_value: float = 0.0,
    speed: float = 0.0,
    speed_max: float = 1.0,
) -> float:
    """2.A4 / 2.A5: Qh = Vh x Nh; Qt = sum(Vt - Ei) over the gates crossed (Ei at most Vt, gates not crossed add no
    error and score nothing); Qv = Vs x S / Smax when a speed term is included; Q = Qh + Qt + Qv."""
    spatial = hidden_value * hidden_correct
    temporal = sum(gate_value - min(abs(error), gate_value) for error in time_errors_crossed)
    speed_term = speed_value * speed / speed_max if speed_value else 0.0
    return spatial + temporal + speed_term


# ---------------------------------------------------------------------------------------------------------------------
# 2.A6 Turnpoint hunt and 2.B2 Limited fuel turnpoint hunt
# ---------------------------------------------------------------------------------------------------------------------


def timing_gate_penalty(
    error_seconds: float, tolerance: float = TIMING_TOLERANCE_S, per_second: float = TIMING_PENALTY_PER_SECOND
) -> float:
    """A compulsory timing gate within the tolerance costs nothing; beyond it every second over the tolerance costs
    10 points."""
    return per_second * max(0.0, abs(error_seconds) - tolerance)


def q_turnpoint_hunt(
    photo_values: Sequence[float],
    time_gate_errors: Sequence[Optional[float]],
    *,
    sequence_bonus: float = 0.0,
    full_sequence: bool = False,
    wrong_photo_values: Sequence[float] = (),
    seconds_over_maximum_duration: float = 0.0,
    gate_value: float = TIME_GATE_VALUE,
    tolerance: float = TIMING_TOLERANCE_S,
    per_second: float = TIMING_PENALTY_PER_SECOND,
) -> float:
    """2.A6 (and, without a sequence bonus, 2.B2).

    `photo_values`: the values of the turnpoints correctly identified. `time_gate_errors`: for each of the three timing
    gates the error in seconds, None when it was not flown (it then scores nothing). A gate flown scores 200 minus 10
    points per second beyond the 10 s tolerance. A photo wrongly identified costs 50% of its value, every second over
    the maximum task duration 10 points, and `full_sequence` earns the sequence bonus. The quarantine breach (100%) is
    a percentage penalty: use `final_scores`.
    """
    gates = sum(
        gate_value - timing_gate_penalty(error, tolerance, per_second)
        for error in time_gate_errors
        if error is not None
    )
    bonus = sequence_bonus if full_sequence else 0.0
    return (
        sum(photo_values) + gates + bonus - 0.5 * sum(wrong_photo_values) - per_second * seconds_over_maximum_duration
    )


def q_limited_fuel_turnpoint_hunt(
    photo_values: Sequence[float],
    time_gate_errors: Sequence[Optional[float]],
    **options,
) -> float:
    """2.B2: as 2.A6 but every crossing scores and there is no bonus for a sequence (the order is free)."""
    options.pop("sequence_bonus", None)
    options.pop("full_sequence", None)
    return q_turnpoint_hunt(photo_values, time_gate_errors, **options)


# ---------------------------------------------------------------------------------------------------------------------
# 2.A7 Circle
# ---------------------------------------------------------------------------------------------------------------------


def circle_final_score(
    rmin: float,
    rmax: float,
    *,
    clockwise: bool = False,
    centre_outside_circle: bool = False,
    start_and_centre_overflown: bool = True,
    radius_limits: tuple[float, float] = CIRCLE_RADIUS_LIMITS_M,
    altitude_spread_ft: float = 0.0,
) -> int:
    """2.A7, an absolute score: P = (Rmin/Rmax - 0.5) x 500, at most 250, over the scored 360 degrees.

    A 100% penalty (score 0) when the circle is flown clockwise, CM is outside the flown circle, SP and CM were not
    overflown, the aircraft leaves the radius limits (Rmin below or Rmax above them) or Rmin/Rmax is 0.5 or smaller.
    A 20% penalty when the altitude between lowest and highest point of the circle exceeds 200 ft.
    """
    if (
        clockwise
        or centre_outside_circle
        or not start_and_centre_overflown
        or rmin < radius_limits[0]
        or rmax > radius_limits[1]
        or rmax <= 0
        or rmin / rmax <= 0.5
    ):
        return 0
    score = min(CIRCLE_MAXIMUM_SCORE, (rmin / rmax - 0.5) * 500.0)
    penalties = [ALTITUDE_PENALTY] if altitude_spread_ft > CIRCLE_ALTITUDE_BAND_FT else []
    return finish_score(apply_percentage_penalties(score, penalties))


# ---------------------------------------------------------------------------------------------------------------------
# 2.A8 Precision navigation Air Nav Race
# ---------------------------------------------------------------------------------------------------------------------


def anr_corridor_penalty(seconds_outside: float) -> float:
    """One excursion from the corridor: nothing for the first 5 s, then 3 points per full second beyond them."""
    return 3.0 * max(0, math.floor(seconds_outside) - 5)


def anr_time_penalty(error_seconds: Optional[float]) -> float:
    """SP or FP timing: within one second nothing, then 3 points per full second beyond it, at most 200; the gate not
    crossed (None) costs 200."""
    if error_seconds is None:
        return 200.0
    return min(200.0, 3.0 * max(0, math.floor(abs(error_seconds)) - 1))


def q_anr(
    *,
    corridor_excursions_s: Sequence[float] = (),
    sp_error: Optional[float] = 0.0,
    fp_error: Optional[float] = 0.0,
    backtracking_or_circling: int = 0,
    takeoff_penalty: float = 0.0,
    route_penalties: float = 0.0,
    flight_planning_penalty: float = 0.0,
) -> float:
    """2.A8: Q = 2000 - Pnav - Ptime - Pfpr - Pto - Prr - Pbc (backtracking or circling: 200 each)."""
    navigation = sum(anr_corridor_penalty(seconds) for seconds in corridor_excursions_s)
    timing = anr_time_penalty(sp_error) + anr_time_penalty(fp_error)
    return (
        ANR_START_POINTS
        - navigation
        - timing
        - flight_planning_penalty
        - takeoff_penalty
        - route_penalties
        - 200.0 * backtracking_or_circling
    )


def anr_final_score(q: float, percentage_penalties: Sequence[float] = ()) -> int:
    """2.A8, an absolute score: P = 1000 x Q / 2000, not divided by the best pilot."""
    return finish_score(apply_percentage_penalties(1000.0 * q / ANR_START_POINTS, percentage_penalties))


# ---------------------------------------------------------------------------------------------------------------------
# 2.B3 Duration
# ---------------------------------------------------------------------------------------------------------------------


def q_duration(airborne_seconds: float) -> float:
    """2.B3: the longest flight on the limited fuel wins; Q is the time airborne, so the best pilot scores task_value."""
    return max(0.0, airborne_seconds)
