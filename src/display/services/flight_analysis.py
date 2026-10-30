"""
The numbers behind a flight summary, worked out here so that the model only has to tell the story: the legs with their
planned and actual times, the wind that was planned against the wind the weather model says was there (and how much
earlier or later that wind alone would have brought a crew flying the planned airspeed), the weather along the route,
how the rest of the field did at each gate, and a few highlights.
"""

import datetime
import math
import statistics

from django.conf import settings
from django.db.models import Max, Min, Sum

from display.models import ActualGateTime, Contestant, ScoreLogEntry
from display.models.scoring_models import ANOMALY, INFORMATION
from display.services import flight_weather
from display.services.contest_visibility import is_navigation_task_public
from display.utilities.calculate_gate_times import calculate_and_get_relative_gate_times

FT_PER_M = 1 / 0.3048

# When the wind the weather model had differs this much from the planned wind, the summary must say so
BIG_WIND_VECTOR_DIFFERENCE_KT = 8
BIG_WIND_SPEED_DIFFERENCE_KT = 5
BIG_WIND_DIRECTION_DIFFERENCE = 40
WIND_SPEED_FOR_DIRECTION_KT = 5

# Enough for any task we run, and it keeps what is sent to the model bounded
MAX_CREWS = 80


def _waypoints(contestant: Contestant) -> list:
    # The same waypoints the planned gate times are calculated over
    return [waypoint for waypoint in contestant.navigation_task.route.waypoints if waypoint.type not in ("dummy",)]


def _headwind(east: float, north: float, track: float) -> float:
    """The part of the wind blowing against the direction of travel (negative: tailwind)."""
    return -(east * math.sin(math.radians(track)) + north * math.cos(math.radians(track)))


def _components(speed: float, direction: float) -> tuple[float, float]:
    return -speed * math.sin(math.radians(direction)), -speed * math.cos(math.radians(direction))


def _seconds(delta: datetime.timedelta | None) -> int | None:
    return round(delta.total_seconds()) if delta is not None else None


def _offsets(contestant: Contestant) -> dict[str, float]:
    """How many seconds late (positive) or early each gate was passed."""
    planned = contestant.gate_times
    return {
        gate: (time - planned[gate]).total_seconds()
        for gate, time in contestant.gate_times_actual.items()
        if planned.get(gate) is not None
    }


def _crew_name(crew: Contestant, contestant: Contestant, public: bool) -> str:
    """
    The crews are named as on the public map and results. Of a task that is not public, no other crew's name goes to
    the model: they did not ask for the summary.
    """
    if public or crew.pk == contestant.pk:
        return str(crew.team.crew)
    return f"Crew #{crew.contestant_number}"


def _field(contestant: Contestant) -> tuple[list[dict], dict[str, dict]]:
    """
    Every scored crew on the task with its result and its offset and points at each gate (named only when the task is
    public, see _crew_name), and per gate the field's median offset and where this crew's timing ranks.
    """
    crews = list(
        Contestant.objects.filter(navigation_task=contestant.navigation_task, contestanttrack__calculator_finished=True)
        .select_related("contestanttrack", "team__crew__member1", "team__crew__member2", "navigation_task__route")
        .order_by("contestant_number")[:MAX_CREWS]
    )
    descending = contestant.navigation_task.score_sorting_direction == "desc"
    public = is_navigation_task_public(contestant.navigation_task)
    ordered = sorted(crews, key=lambda crew: -crew.contestanttrack.score if descending else crew.contestanttrack.score)
    points = {}
    for row in (
        ScoreLogEntry.objects.filter(contestant__in=crews, type__in=(ANOMALY, INFORMATION))
        .values("contestant_id", "gate")
        .annotate(total=Sum("points"))
    ):
        if row["gate"] and row["total"]:
            points.setdefault(row["contestant_id"], {})[row["gate"]] = round(row["total"], 2)
    field = []
    offsets_by_crew = {}
    for crew in ordered:
        offsets = _offsets(crew)
        offsets_by_crew[crew.pk] = offsets
        gates = {}
        # In route order; penalty zones and the like, which are not gates, last
        order = {gate: index for index, gate in enumerate(crew.gate_times)}
        for gate in sorted(set(offsets) | set(points.get(crew.pk, {})), key=lambda name: order.get(name, len(order))):
            gates[gate] = {"offset_seconds": round(offsets[gate]) if gate in offsets else None}
            if gate in points.get(crew.pk, {}):
                gates[gate]["points"] = points[crew.pk][gate]
        entry = {
            "crew": _crew_name(crew, contestant, public),
            "rank": 1
            + sum(
                1
                for other in ordered
                if (
                    other.contestanttrack.score > crew.contestanttrack.score
                    if descending
                    else other.contestanttrack.score < crew.contestanttrack.score
                )
            ),
            "score": crew.contestanttrack.score,
            "gates": gates,
        }
        if crew.pk == contestant.pk:
            entry["you"] = True
        else:
            # In words: with lower-is-better scoring, "273 behind" is easy to get the wrong way round
            gap = round(abs(crew.contestanttrack.score - contestant.contestanttrack.score), 2)
            better = (
                crew.contestanttrack.score > contestant.contestanttrack.score
                if descending
                else crew.contestanttrack.score < contestant.contestanttrack.score
            )
            entry["compared_with_you"] = (
                "the same score as you" if gap == 0 else f"{gap:g} points {'better' if better else 'worse'} than you"
            )
        field.append(entry)

    own = offsets_by_crew.get(contestant.pk, _offsets(contestant))
    by_gate = {}
    for crew_pk, offsets in offsets_by_crew.items():
        if crew_pk == contestant.pk:
            continue
        for gate, offset in offsets.items():
            by_gate.setdefault(gate, []).append(offset)
    at_gates = {}
    for gate, values in by_gate.items():
        at_gates[gate] = {"median_offset_seconds": round(statistics.median(values)), "other_crews": len(values)}
        if gate in own:
            at_gates[gate]["your_rank_by_precision"] = 1 + sum(1 for value in values if abs(value) < abs(own[gate]))
    return field, at_gates


def _weather(waypoints, planned, height_ft) -> tuple[dict | None, list[dict]]:
    """
    The weather model's data for the middle of the route (routes are short enough for one point to do), and the wind
    and conditions there at each gate's planned time.
    """
    times = [planned.get(waypoint.name) for waypoint in waypoints]
    known = [time for time in times if time is not None]
    if not known:
        return None, []
    location = flight_weather.fetch_weather(
        statistics.mean(waypoint.latitude for waypoint in waypoints),
        statistics.mean(waypoint.longitude for waypoint in waypoints),
        min(known),
        max(known),
    )
    if location is None:
        return None, []
    points = []
    for waypoint, time in zip(waypoints, times):
        time = time or known[0]
        wind = flight_weather.wind_components_at(location, time, height_ft)
        points.append({"gate": waypoint.name, "time": time.isoformat(), "wind": wind})
    return location, points


def _legs(contestant, waypoints, planned, actual, weather_points) -> list[dict]:
    planned_wind = _components(contestant.wind_speed, contestant.wind_direction)
    winds = []
    for index in range(len(waypoints) - 1):
        ends = [weather_points[i]["wind"] for i in (index, index + 1)] if weather_points else []
        ends = [wind for wind in ends if wind]
        winds.append((sum(e for e, _ in ends) / len(ends), sum(n for _, n in ends) / len(ends)) if ends else None)

    route = contestant.navigation_task.route
    planned_times = dict(
        calculate_and_get_relative_gate_times(
            route, contestant.air_speed, contestant.wind_speed, contestant.wind_direction
        )
    )
    with_actual_wind = None
    if winds and all(wind is not None for wind in winds):
        with_actual_wind = dict(
            calculate_and_get_relative_gate_times(
                route,
                contestant.air_speed,
                contestant.wind_speed,
                contestant.wind_direction,
                leg_winds=[flight_weather.to_speed_and_direction(*wind) for wind in winds],
            )
        )

    legs = []
    for index, (start, finish) in enumerate(zip(waypoints, waypoints[1:])):
        track = finish.bearing_from_previous
        leg = {
            "from": start.name,
            "to": finish.name,
            "distance_nm": round(finish.distance_previous / 1852, 1),
            "track": round(track),
            "planned_seconds": None,
            "actual_seconds": None,
            "offset_at_end_seconds": None,
            "planned_headwind_kt": round(_headwind(*planned_wind, track), 1),
            "actual_wind": None,
            "actual_headwind_kt": None,
            "wind_effect_seconds": None,
        }
        if planned.get(start.name) and planned.get(finish.name):
            leg["planned_seconds"] = _seconds(planned[finish.name] - planned[start.name])
        if actual.get(start.name) and actual.get(finish.name):
            leg["actual_seconds"] = _seconds(actual[finish.name] - actual[start.name])
        if actual.get(finish.name) and planned.get(finish.name):
            leg["offset_at_end_seconds"] = _seconds(actual[finish.name] - planned[finish.name])
        if winds and winds[index] is not None:
            speed, direction = flight_weather.to_speed_and_direction(*winds[index])
            leg["actual_wind"] = {"speed_kt": speed, "direction": direction}
            leg["actual_headwind_kt"] = round(_headwind(*winds[index], track), 1)
        if with_actual_wind and start.name in planned_times and finish.name in planned_times:
            planned_leg = planned_times[finish.name] - planned_times[start.name]
            actual_wind_leg = with_actual_wind[finish.name] - with_actual_wind[start.name]
            leg["wind_effect_seconds"] = _seconds(actual_wind_leg - planned_leg)
        # In words as well: a signed number of seconds is easy to read the wrong way round
        if leg["planned_seconds"] is not None and leg["actual_seconds"] is not None:
            leg["you_compared_with_plan"] = _earlier_or_later(leg["actual_seconds"] - leg["planned_seconds"], "took")
        if leg["wind_effect_seconds"] is not None:
            leg["wind_alone_would_have_made_you"] = _earlier_or_later(leg["wind_effect_seconds"], "arrive")
        legs.append(leg)
    return legs


def _earlier_or_later(seconds: int, verb: str) -> str:
    if seconds == 0:
        return "exactly as planned"
    if verb == "took":
        return f"{abs(seconds)} s {'longer' if seconds > 0 else 'shorter'} than planned"
    return f"{abs(seconds)} s {'later' if seconds > 0 else 'earlier'} than planned"


def _highlights(contestant, offsets, waypoints, planned, actual) -> dict:
    highlights = {}
    timed = {waypoint.name for waypoint in waypoints if waypoint.time_check}
    timed_offsets = {gate: offset for gate, offset in offsets.items() if gate in timed}
    if timed_offsets:
        gate = min(timed_offsets, key=lambda name: abs(timed_offsets[name]))
        highlights["your_most_precise_gate"] = {"gate": gate, "offset_seconds": round(timed_offsets[gate])}
    penalised = set(
        ScoreLogEntry.objects.filter(contestant=contestant, type__in=(ANOMALY, INFORMATION), points__gt=0).values_list(
            "gate", flat=True
        )
    )
    streak = best = 0
    for waypoint in waypoints:
        if waypoint.name not in actual:
            continue
        streak = 0 if waypoint.name in penalised else streak + 1
        best = max(best, streak)
    highlights["longest_run_of_gates_without_penalty"] = best
    first = actual.get(waypoints[0].name) if waypoints else None
    last = actual.get(waypoints[-1].name) if waypoints else None
    if first and last:
        track = contestant.get_track().filter(time__gte=first, time__lte=last)
        stats = track.aggregate(top_speed=Max("speed"), lowest=Min("altitude"), highest=Max("altitude"))
        if stats["top_speed"]:
            highlights["top_ground_speed_kt"] = round(stats["top_speed"])
        if stats["highest"]:
            highlights["altitude_range_ft_msl"] = [
                round(stats["lowest"] * FT_PER_M),
                round(stats["highest"] * FT_PER_M),
            ]
        minutes, seconds = divmod(_seconds(last - first), 60)
        highlights["time_from_start_to_finish"] = f"{minutes} min {seconds} s"
    return highlights


def wind_difference(planned_speed: float, planned_direction: float, winds: list[dict]) -> dict | None:
    """How the wind through the flight (the mean of the weather model's) compares with the planned wind."""
    winds = [wind for wind in winds if wind]
    if not winds:
        return None
    components = [_components(wind["speed_kt"], wind["direction"]) for wind in winds]
    east = sum(e for e, _ in components) / len(components)
    north = sum(n for _, n in components) / len(components)
    speed, direction = flight_weather.to_speed_and_direction(east, north)
    planned_east, planned_north = _components(planned_speed, planned_direction)
    vector = math.hypot(east - planned_east, north - planned_north)
    speeds = abs(speed - planned_speed)
    directions = abs((direction - planned_direction + 180) % 360 - 180)
    big = (
        vector >= BIG_WIND_VECTOR_DIFFERENCE_KT
        or speeds >= BIG_WIND_SPEED_DIFFERENCE_KT
        or (directions >= BIG_WIND_DIRECTION_DIFFERENCE and min(speed, planned_speed) >= WIND_SPEED_FOR_DIRECTION_KT)
    )
    return {
        "planned": {"speed_kt": planned_speed, "direction": planned_direction},
        "actual": {"speed_kt": speed, "direction": direction},
        "vector_difference_kt": round(vector, 1),
        "speed_difference_kt": round(speed - planned_speed, 1),
        "direction_difference": round(directions),
        "big": big,
    }


def _timing(contestant: Contestant, waypoints, crews: list[dict]) -> dict | None:
    """How precise this crew's timing was at the timed gates, and how the field's compares."""
    timed = {waypoint.name for waypoint in waypoints if waypoint.time_check}

    def precision(crew: dict) -> list[int]:
        return [
            abs(gate["offset_seconds"])
            for name, gate in crew["gates"].items()
            if name in timed and gate.get("offset_seconds") is not None
        ]

    own = next((crew for crew in crews if crew.get("you")), None)
    offsets = precision(own) if own else []
    if not offsets:
        return None
    means = sorted(statistics.mean(values) for values in map(precision, crews) if values)
    mean = statistics.mean(offsets)
    return {
        "timed_gates": len(offsets),
        "mean_absolute_offset_seconds": round(mean, 1),
        "largest_absolute_offset_seconds": max(offsets),
        "gates_within_2_seconds": sum(1 for offset in offsets if offset <= 2),
        "gates_within_5_seconds": sum(1 for offset in offsets if offset <= 5),
        "field_median_of_mean_absolute_offset_seconds": round(statistics.median(means), 1),
        "your_rank_by_mean_absolute_offset": 1 + sum(1 for value in means if value < mean),
        "crews_ranked": len(means),
    }


def analyse_flight(contestant: Contestant) -> dict:
    waypoints = _waypoints(contestant)
    planned = contestant.gate_times
    actual = {item.gate: item.time for item in ActualGateTime.objects.filter(contestant=contestant)}
    height_ft = settings.FLIGHT_SUMMARY_WIND_HEIGHT_AGL_FT
    location, weather_points = _weather(waypoints, planned, height_ft)
    crews, field_at_gates = _field(contestant)
    conditions = []
    if location is not None and weather_points:
        times = [datetime.datetime.fromisoformat(point["time"]) for point in weather_points]
        for label, time in (("start", times[0]), ("middle", times[len(times) // 2]), ("finish", times[-1])):
            wind = flight_weather.wind_components_at(location, time, height_ft)
            speed, direction = flight_weather.to_speed_and_direction(*wind) if wind else (None, None)
            conditions.append(
                {
                    "when": label,
                    "time": time.isoformat(),
                    "wind": {"speed_kt": speed, "direction": direction} if wind else None,
                    **(flight_weather.conditions_at(location, time) or {}),
                }
            )
    return {
        "planned_air_speed_kt": contestant.air_speed,
        "planned_wind": {"speed_kt": contestant.wind_speed, "direction": contestant.wind_direction},
        "weather_source": flight_weather.SOURCE if location else None,
        "wind_height_ft_above_ground": height_ft,
        "weather": conditions,
        "wind_difference": wind_difference(
            contestant.wind_speed, contestant.wind_direction, [condition.get("wind") for condition in conditions]
        ),
        "legs": _legs(contestant, waypoints, planned, actual, weather_points),
        "field_at_gates": field_at_gates,
        "crews": crews,
        "timing": _timing(contestant, waypoints, crews),
        "highlights": _highlights(contestant, _offsets(contestant), waypoints, planned, actual),
    }
