from __future__ import annotations

from typing import Any

from display.utilities.cima_task_type_definitions import (
    ANR_CATALOGUE,
    CIRCLE,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    DURATION,
    KNOWN_CIRCUIT,
    LEGACY_AIRSPORT_CHALLENGE,
    LEGACY_AIRSPORTS,
    LEGACY_ANR_CORRIDOR,
    LEGACY_LANDING,
    LEGACY_POKER,
    LEGACY_PRECISION,
    LIMITED_FUEL_TURNPOINT_HUNT,
    PRECISION_NAVIGATION,
    TURNPOINT_HUNT,
    UNKNOWN_LEGS,
)
from display.utilities.navigation_task_type_definitions import (
    AIRSPORTS,
    AIRSPORT_CHALLENGE,
    ANR_CORRIDOR,
    LANDING,
    POKER,
    PRECISION,
)


FAMILY_DISPLAY_NAMES = {
    PRECISION: "Precision navigation",
    ANR_CORRIDOR: "ANR corridor",
    AIRSPORTS: "Air Sports Race",
    AIRSPORT_CHALLENGE: "Air Sport Challenge",
    POKER: "Poker run",
    LANDING: "Landing",
}


def _clean_lines(lines: list[str]) -> list[str]:
    return [line.strip() for line in lines if line and line.strip()]


def _format_float(value: Any, decimals: int = 0) -> str:
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


def _precision_family_overrides(navigation_task) -> list[str]:
    scorecard = navigation_task.scorecard
    overrides = []
    try:
        overrides.append(
            "Timed gates currently score "
            f"{_format_float(scorecard.get_penalty_per_second_for_gate_type('tp'))} point(s) per second "
            f"after {_format_float(scorecard.get_graceperiod_after_for_gate_type('tp'))} s grace, "
            f"with maximum {_format_float(scorecard.get_maximum_timing_penalty_for_gate_type('tp'))} points and "
            f"missed-gate penalty {_format_float(scorecard.get_missed_penalty_for_gate_type('tp'))}."
        )
    except Exception:
        pass
    if getattr(scorecard, "backtracking_penalty", None) is not None:
        overrides.append(
            "Backtracking currently penalises deviations beyond "
            f"{_format_float(scorecard.backtracking_bearing_difference)}° for more than "
            f"{_format_float(scorecard.backtracking_grace_time_seconds)} s with "
            f"{_format_float(scorecard.backtracking_penalty)} points."
        )
    return _clean_lines(overrides)


def _anr_family_overrides(navigation_task) -> list[str]:
    scorecard = navigation_task.scorecard
    route = navigation_task.route
    overrides = [
        f"Corridor width is currently {_format_float(route.corridor_width, 2)} NM.",
        "Leaving the corridor is currently scored after "
        f"{_format_float(scorecard.corridor_grace_time)} s grace at "
        f"{_format_float(scorecard.corridor_outside_penalty)} point(s) per second.",
    ]
    if getattr(scorecard, "corridor_maximum_penalty", -1) >= 0:
        per_leg_text = " per leg" if getattr(scorecard, "corridor_maximum_penalty_is_per_leg", False) else ""
        overrides.append(
            f"Maximum corridor penalty is {_format_float(scorecard.corridor_maximum_penalty)} points{per_leg_text}."
        )
    return _clean_lines(overrides)


def _gate_width_range_line(route) -> list[str]:
    widths = [waypoint.width for waypoint in route.waypoints]
    if not widths:
        return []
    low, high = min(widths), max(widths)
    if low == high:
        return [f"Gate width is currently {_format_float(low, 2)} NM."]
    return [f"Gate width currently ranges between {_format_float(low, 2)} and {_format_float(high, 2)} NM."]


def _takeoff_landing_gate_overrides(navigation_task) -> list[str]:
    scorecard = navigation_task.scorecard
    route = navigation_task.route
    overrides = []
    if route.takeoff_gates:
        try:
            penalty = scorecard.get_maximum_timing_penalty_for_gate_type("to")
            if penalty > 0:
                overrides.append(
                    "The route has a takeoff gate - crossing it before the takeoff time or more than one "
                    f"minute after currently gives a penalty of {_format_float(penalty)} points."
                )
        except Exception:
            pass
    if route.landing_gates:
        try:
            penalty = scorecard.get_maximum_timing_penalty_for_gate_type("ldg")
            if penalty > 0:
                overrides.append(
                    "The route has a landing gate - not crossing it by the contestant's finish time currently "
                    f"gives a penalty of {_format_float(penalty)} points."
                )
        except Exception:
            pass
    return overrides


def _legacy_precision_overrides(navigation_task) -> list[str]:
    scorecard = navigation_task.scorecard
    route = navigation_task.route
    overrides = list(_precision_family_overrides(navigation_task))
    overrides.extend(_gate_width_range_line(route))
    try:
        overrides.append(
            "Crossing the extended starting line "
            f"({_format_float(scorecard.get_extended_gate_width_for_gate_type('sp'), 2)} NM wide) backwards "
            f"currently gives a penalty of {_format_float(scorecard.get_bad_crossing_extended_gate_penalty_for_gate_type('sp'))} points."
        )
    except Exception:
        pass
    overrides.extend(_takeoff_landing_gate_overrides(navigation_task))
    return _clean_lines(overrides)


def _legacy_anr_corridor_overrides(navigation_task) -> list[str]:
    scorecard = navigation_task.scorecard
    overrides = list(_anr_family_overrides(navigation_task))
    for gate_type, gate_name in (("sp", "starting point"), ("fp", "finish point")):
        try:
            overrides.append(
                f"Missing the {gate_name} currently gives a penalty of "
                f"{_format_float(scorecard.get_missed_penalty_for_gate_type(gate_type))} points; crossing it more than "
                f"{_format_float(scorecard.get_graceperiod_before_for_gate_type(gate_type))} s early or "
                f"{_format_float(scorecard.get_graceperiod_after_for_gate_type(gate_type))} s late currently gives "
                f"{_format_float(scorecard.get_penalty_per_second_for_gate_type(gate_type))} point(s) per additional second, "
                f"up to a maximum of {_format_float(scorecard.get_maximum_timing_penalty_for_gate_type(gate_type))} points."
            )
        except Exception:
            pass
    overrides.extend(_takeoff_landing_gate_overrides(navigation_task))
    return _clean_lines(overrides)


def _legacy_airsports_family_overrides(navigation_task) -> list[str]:
    scorecard = navigation_task.scorecard
    route = navigation_task.route
    overrides = _gate_width_range_line(route)
    overrides.append(
        "Leaving the corridor currently gives a penalty of "
        f"{_format_float(scorecard.corridor_outside_penalty)} point(s) per second beyond the first "
        f"{_format_float(scorecard.corridor_grace_time)} s grace."
    )
    if getattr(scorecard, "corridor_maximum_penalty", -1) >= 0:
        per_leg_text = " per leg" if getattr(scorecard, "corridor_maximum_penalty_is_per_leg", False) else ""
        overrides.append(
            f"Maximum corridor penalty is {_format_float(scorecard.corridor_maximum_penalty)} points{per_leg_text}."
        )
    overrides.append(
        "Entering a prohibited zone currently gives a one-off penalty of "
        f"{_format_float(scorecard.prohibited_zone_penalty)} points; a penalty zone gives "
        f"{_format_float(scorecard.penalty_zone_penalty_per_second)} point(s) per second beyond the first "
        f"{_format_float(scorecard.penalty_zone_grace_time)} s grace."
        + (
            f" Each penalty zone is capped at {_format_float(scorecard.penalty_zone_maximum)} points."
            if getattr(scorecard, "penalty_zone_maximum", -1) >= 0
            else ""
        )
    )
    for gate_type, gate_name in (("tp", "Regular gates"), ("secret", "Secret gates")):
        try:
            overrides.append(
                f"{gate_name} currently score "
                f"{_format_float(scorecard.get_penalty_per_second_for_gate_type(gate_type))} point(s) per second "
                f"after {_format_float(scorecard.get_graceperiod_after_for_gate_type(gate_type))} s grace, with maximum "
                f"{_format_float(scorecard.get_maximum_timing_penalty_for_gate_type(gate_type))} points and missed-gate "
                f"penalty {_format_float(scorecard.get_missed_penalty_for_gate_type(gate_type))}."
            )
        except Exception:
            pass
    overrides.extend(_takeoff_landing_gate_overrides(navigation_task))
    if getattr(scorecard, "backtracking_penalty", None) is not None:
        overrides.append(
            "Backtracking currently penalises deviations beyond "
            f"{_format_float(scorecard.backtracking_bearing_difference)}° for more than "
            f"{_format_float(scorecard.backtracking_grace_time_seconds)} s with "
            f"{_format_float(scorecard.backtracking_penalty)} points."
        )
    return _clean_lines(overrides)


def build_navigation_task_information(navigation_task) -> dict[str, Any]:
    definition = navigation_task.subtype_definition
    subtype = navigation_task.effective_task_subtype
    scorecard = navigation_task.scorecard
    task_config = navigation_task.task_config or {}
    family_display_name = FAMILY_DISPLAY_NAMES.get(navigation_task.coarse_task_family, navigation_task.coarse_task_family)
    subtype_display_name = definition.display_name if definition else family_display_name

    info = {
        "family_display_name": family_display_name,
        "subtype_key": subtype,
        "subtype_display_name": subtype_display_name,
        "objective": "",
        "summary": [],
        "scoring": [],
        "penalties": [],
        "overrides": [],
    }

    if subtype == CURVE_NAVIGATION_TIME_ESTIMATION:
        info["objective"] = "Precisely fly the drawn course, cross known time gates at declared times, and validate the flown path through hidden gates."
        info["summary"] = _clean_lines([
            "Pilots receive a line drawn on the map plus known time gates where crossing times are declared before take-off.",
            "Navigation starts at SP and ends at FP; hidden gates validate that the route is flown correctly and in order.",
            "If a time gate is crossed more than once, timing is taken from the first crossing.",
        ])
        info["scoring"] = _clean_lines([
            "Spatial precision scores hidden gates correctly crossed in order and direction.",
            "Time precision scores the sum of absolute errors at the known time gates.",
            "Total score is the combined hidden-gate and time-precision result, normalized to the task maximum.",
        ])
        info["penalties"] = ["Backtracking is a 50% penalty."]
        if task_config.get("curve_navigation_tmax_seconds"):
            info["overrides"].append(
                f"Configured Tmax is {int(task_config['curve_navigation_tmax_seconds'])} seconds from SP to FP."
            )
        info["overrides"].extend(_precision_family_overrides(navigation_task))
    elif subtype == PRECISION_NAVIGATION:
        info["objective"] = "Fly the published circuit at constant speed on each leg and hit the declared timing points as accurately as possible."
        info["summary"] = _clean_lines([
            "Competitors declare estimated arrival times at each turn point including finish before take-off.",
            "Each leg must be flown at constant speed, although different legs may use different speeds.",
            "Hidden timing gates may be placed along the course corridors.",
        ])
        info["scoring"] = _clean_lines([
            "Each correctly crossed hidden gate contributes route score.",
            "Each second of timing error reduces the timing component, up to the configured maximum per gate.",
            "Total score combines route precision and timing precision and is normalized to the task maximum.",
        ])
        info["penalties"] = ["Backtracking is a 50% penalty."]
        info["overrides"].extend(_precision_family_overrides(navigation_task))
    elif subtype == CONTRACT_NAVIGATION_TIME_CONTROLS:
        info["objective"] = "Fly a declared ordered sequence of turn points, hit MP at T seconds after SP and FP at 2T seconds after SP, and keep the declared order valid."
        info["summary"] = _clean_lines([
            "SP, MP, and FP are mandatory; pilots declare the rest of the turnpoint order before take-off.",
            "Declared points after MP may not be flown before MP time without becoming invalid.",
            "Turnpoints may only be visited once.",
        ])
        info["scoring"] = _clean_lines([
            "Turnpoint score counts declared points flown in order and deducts points for declared points not validated.",
            "Time score uses the absolute timing error at SP, MP, and FP, each capped by the configured maximum error.",
            "Total score combines ordered-point validity and mandatory time-point precision.",
        ])
        info["penalties"] = ["Backtracking is a 50% penalty."]
        if task_config.get("contract_time_seconds"):
            info["overrides"].append(f"Configured contract time T is {int(task_config['contract_time_seconds'])} seconds.")
        info["overrides"].extend(_precision_family_overrides(navigation_task))
    elif subtype == KNOWN_CIRCUIT:
        info["objective"] = "Follow the known circuit, identify evidence targets correctly, and validate the route with hidden gates and any configured timing or speed elements."
        info["summary"] = _clean_lines([
            "Competitors receive the known route, start/finish definition, and any marker or photo-identification material before flight.",
            "The task may include hidden gates, map placement, optional timing gates, and optional speed elements.",
            "The task may finish with an outlanding and uses quarantine after landing for scoring.",
        ])
        info["scoring"] = _clean_lines([
            "Spatial precision scores hidden gates and correctly placed/identified evidence targets.",
            "If timing is included, each crossed timing gate contributes value minus timing error.",
            "If a speed element is included, the speed component is normalized against the task maximum.",
        ])
        info["penalties"] = _clean_lines([
            "Breach of quarantine is a 100% penalty.",
            "Crossing a hidden gate twice invalidates that gate.",
            "Backtracking is a 50% penalty.",
        ])
        info["overrides"].extend(_precision_family_overrides(navigation_task))
    elif subtype == UNKNOWN_LEGS:
        info["objective"] = "Follow the published initial guidance, identify the unknown-leg transitions correctly, and validate the route and evidence just as flown."
        info["summary"] = _clean_lines([
            "Certain markers or ground features define where a new heading or leg starts.",
            "The task may include hidden gates, optional timing or speed sections, and optional sealed instructions.",
            "The task may finish with an outlanding and uses quarantine after landing for scoring.",
        ])
        info["scoring"] = _clean_lines([
            "Spatial precision scores hidden gates and correctly placed/identified evidence targets.",
            "Optional timing and speed components are added exactly as briefed for the task.",
            "Total score is the sum of the active spatial, timing, and speed components, normalized to the task maximum.",
        ])
        info["penalties"] = _clean_lines([
            "Breach of quarantine is a 100% penalty.",
            "Crossing a hidden gate twice invalidates that gate.",
            "A broken envelope seal penalty may apply when that task option is used.",
            "Backtracking is a 50% penalty.",
        ])
        info["overrides"].extend(_precision_family_overrides(navigation_task))
    elif subtype == TURNPOINT_HUNT:
        tolerance = int(task_config.get("compulsory_timing_tolerance_seconds") or 10)
        info["objective"] = "Visit as many scored targets as possible within the task time, while keeping the declared sequence valid and hitting the three compulsory timing gates accurately."
        info["summary"] = _clean_lines([
            "All target locations and scores are published before take-off.",
            "Pilots declare both the predicted target sequence and the predicted gate times before take-off.",
            "Three compulsory timing gates must be crossed within the configured tolerance; one may require a precision touchdown depending on the briefing.",
        ])
        info["scoring"] = _clean_lines([
            "Turnpoint and gate values are accumulated according to the declared sequence and successfully collected targets.",
            f"Compulsory timing gates currently use a tolerance of {tolerance} seconds before timing penalties apply.",
            "Sequence correctness and collected target values both contribute to the task result.",
        ])
        info["penalties"] = _clean_lines([
            "Breach of quarantine is a 100% penalty.",
            "Wrongly identified photo/map evidence is a 50% penalty of that target score.",
            "Time over maximum task duration is penalized according to the configured task override when enabled.",
        ])
        if task_config.get("maximum_task_duration_minutes") is not None:
            info["overrides"].append(
                "Configured maximum task duration is "
                f"{int(task_config['maximum_task_duration_minutes'])} minutes"
                + (
                    f" with {_format_float(task_config.get('maximum_task_duration_penalty'))} points/second overtime penalty."
                    if task_config.get("maximum_task_duration_penalty") is not None
                    else "."
                )
            )
        info["overrides"].extend(_precision_family_overrides(navigation_task))
    elif subtype == CIRCLE:
        min_radius = task_config.get("circle_radius_min_m", getattr(scorecard, "circle_radius_min_m", 200))
        max_radius = task_config.get("circle_radius_max_m", getattr(scorecard, "circle_radius_max_m", 750))
        info["objective"] = "Fly a precise left-hand circle around the center marker, within the allowed radius band, after entering straight over SP and CM."
        info["summary"] = _clean_lines([
            "The pilot must overfly SP and CM in a straight initial line before banking left into the circle.",
            "The first 180° are for orientation only and are not scored.",
            "Scoring starts after the entry line and covers the next 360°, ending when the entry line is crossed again before leaving toward the next waypoint.",
        ])
        info["scoring"] = _clean_lines([
            "Circle score is based on P = (Rmin / Rmax - 0.5) * 500, capped at 250 points.",
            "The maximum score is achieved by flying a truly circular path within the allowed radius band.",
            "A 20% penalty applies if altitude spread exceeds 200 ft / 61 m between lowest and highest height during the scored circle.",
        ])
        info["penalties"] = _clean_lines([
            "A 100% penalty applies if the circle is flown clockwise.",
            "A 100% penalty applies if CM is outside the flown circle.",
            "A 100% penalty applies if entry is not flown over the briefed SP/CM line limits.",
            "A 100% penalty applies if the aircraft leaves the permitted radius band.",
            "A 100% penalty applies if Rmin / Rmax is 0.5 or smaller.",
        ])
        info["overrides"].append(
            f"Configured radius band is {_format_float(min_radius)} m to {_format_float(max_radius)} m."
        )
    elif subtype == ANR_CATALOGUE:
        info["objective"] = "Fly the published ANR corridor at the briefed speed and timing, including the route to SP and route from FP, while avoiding backtracking and route deviations."
        info["summary"] = _clean_lines([
            "Pilots prepare in quarantine and receive the route corridor, SP/FP timings, and the route to SP and from FP back to the airfield.",
            "SP and FP each use a 0.6 NM gate unless specifically briefed otherwise.",
            "Real-time scoring may be used when the approved live-tracking system is active.",
        ])
        info["scoring"] = _clean_lines([
            "Competitors start with 2000 points; penalties are subtracted for corridor deviations, timing errors, start/take-off issues, route-to-SP / route-from-FP violations, and backtracking/circling.",
            "Timing penalties at SP and FP apply after ±1 second with 3 points per full second up to 200 points per gate.",
            "Route compliance outside the corridor is accumulated according to the configured corridor grace time and penalty rate.",
        ])
        info["penalties"] = _clean_lines([
            "Breach of quarantine is a 100% penalty.",
            "Intentional failure to follow task instructions is a 100% penalty.",
            "Backtracking or circling more than 90° while leaving or re-entering the corridor gives 200 points each.",
        ])
        info["overrides"].extend(_anr_family_overrides(navigation_task))
    elif subtype == LIMITED_FUEL_TURNPOINT_HUNT:
        tolerance = int(task_config.get("compulsory_timing_tolerance_seconds") or 10)
        info["objective"] = "Visit as many scored targets as possible within the task time on limited fuel, while meeting the compulsory timing gates and any configured fuel-compliance conditions."
        info["summary"] = _clean_lines([
            "All target locations and scores are published before take-off together with the specified fuel quantity.",
            "Pilots declare the gate times and predicted target sequence before take-off.",
            "Three compulsory timing gates must be crossed within the configured tolerance; one may require a precision touchdown depending on the briefing.",
        ])
        info["scoring"] = _clean_lines([
            "Turnpoint and gate values are accumulated according to the declared sequence and successfully collected targets.",
            f"Compulsory timing gates currently use a tolerance of {tolerance} seconds before timing penalties apply.",
            "Fuel-compliance effects are applied in addition to the normal turnpoint-hunt sequence and timing scoring.",
        ])
        info["penalties"] = _clean_lines([
            "Breach of quarantine is a 100% penalty.",
            "Wrongly identified photo/map evidence is a 50% penalty of that target score.",
            "Time over maximum task duration is penalized according to the configured task override when enabled.",
        ])
        if task_config.get("maximum_task_duration_minutes") is not None:
            info["overrides"].append(
                "Configured maximum task duration is "
                f"{int(task_config['maximum_task_duration_minutes'])} minutes"
                + (
                    f" with {_format_float(task_config.get('maximum_task_duration_penalty'))} points/second overtime penalty."
                    if task_config.get("maximum_task_duration_penalty") is not None
                    else "."
                )
            )
        if task_config.get("fuel_deadline_penalty") is not None:
            info["overrides"].append(
                f"Configured fuel deadline penalty is {_format_float(task_config['fuel_deadline_penalty'])} points."
            )
        info["overrides"].extend(_precision_family_overrides(navigation_task))
    elif subtype == DURATION:
        info["objective"] = "Fly for as long as possible on the specified fuel, land in the permitted area, and satisfy any residual-fuel requirement if one is configured."
        info["summary"] = _clean_lines([
            "The task is fuel-limited and normally ends with landing in a designated landing area briefed by the organizer.",
            "If a residual-fuel requirement is configured, quarantine fuel checking applies after landing.",
            "Duration scoring currently follows the configured normalization policy in the task configuration.",
        ])
        info["scoring"] = _clean_lines([
            "The duration result is based on airborne duration measured from take-off to landing.",
            "Any configured normalization policy is applied on top of the raw airborne duration.",
            "Landing-area and residual-fuel requirements are enforced through the configured task rules.",
        ])
        info["penalties"] = _clean_lines([
            "Breach of quarantine is a 100% penalty.",
            "Flight in a prohibited area is a 100% penalty.",
            "Landing outside the specified area but inside the airfield boundary is scored as briefed.",
        ])
        if task_config.get("duration_normalization_policy"):
            info["overrides"].append(
                f"Configured duration normalization policy is '{task_config['duration_normalization_policy']}'."
            )
        if task_config.get("duration_residual_fuel_required"):
            info["overrides"].append("Residual fuel is required at landing for this task.")
        if task_config.get("duration_landing_area_polygon"):
            # This task_config value is display-only: it is not read by
            # DurationCalculator or ContestantTaskCompiler, which both derive
            # the actual scored landing area from the EditableRoute's
            # authored duration_landing_area zone. Say so explicitly so this
            # sentence cannot be mistaken for confirmation that setting the
            # task_config value affects scoring.
            info["overrides"].append(
                "A landing area polygon is noted in the task configuration for reference; scoring uses the "
                "landing area zone drawn in the route editor, not this configuration value."
            )
    elif subtype == LEGACY_PRECISION:
        info["objective"] = (
            "Cross each timing gate as close as possible to the declared time while recognising the "
            "provided ground-feature pictures along the route."
        )
        info["summary"] = _clean_lines(
            [
                "The only navigation tools available to the pilot are a paper map annotated with the "
                "prescribed route and the expected passing times for the gates.",
            ]
        )
        info["overrides"].extend(_legacy_precision_overrides(navigation_task))
    elif subtype == LEGACY_ANR_CORRIDOR:
        info["objective"] = (
            "Keep the aircraft inside the predefined corridor and cross the start and finish lines at "
            "the predefined times."
        )
        info["overrides"].extend(_legacy_anr_corridor_overrides(navigation_task))
    elif subtype in (LEGACY_AIRSPORTS, LEGACY_AIRSPORT_CHALLENGE):
        info["objective"] = (
            "Cross the known and secret gates at the declared times while remaining inside the corridor "
            "and avoiding any prohibited or penalty zones."
        )
        info["summary"] = _clean_lines(
            [
                "The only navigation tools available to the pilot are a paper map annotated with the "
                "prescribed route and the expected passing times for the scorecard.",
            ]
        )
        info["overrides"].extend(_legacy_airsports_family_overrides(navigation_task))
    elif subtype == LEGACY_POKER:
        info["objective"] = "Fly the published track and collect a playing card at each waypoint to form the best poker hand."
        info["summary"] = _clean_lines(
            [
                "Each aircraft receives a playing card at each waypoint along a track covering a set of airports or waypoints.",
                "At the end of the run the collected cards are evaluated as a poker hand; the crew with the highest hand wins.",
            ]
        )
    elif subtype == LEGACY_LANDING:
        info["objective"] = "Fly the published landing pattern and cross the landing gate as accurately as possible on each round."
        info["summary"] = _clean_lines(
            [
                "Each successful pass through the landing gate currently scores one point as a completed landing round.",
            ]
        )
    else:
        coarse_family = navigation_task.coarse_task_family or family_display_name
        info["objective"] = f"This task uses the {str(coarse_family).lower()} family."
        info["summary"] = [f"Task subtype: {subtype_display_name}."]
        if navigation_task.coarse_task_family == PRECISION:
            info["overrides"].extend(_precision_family_overrides(navigation_task))
        elif navigation_task.coarse_task_family == ANR_CORRIDOR:
            info["overrides"].extend(_anr_family_overrides(navigation_task))

    info["summary"] = _clean_lines(info["summary"])
    info["scoring"] = _clean_lines(info["scoring"])
    info["penalties"] = _clean_lines(info["penalties"])
    info["overrides"] = _clean_lines(info["overrides"])
    return info


def _escape_latex(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "°": r"$^{\circ}$",
    }
    return "".join(replacements.get(char, char) for char in text)


def build_navigation_task_rules_latex(navigation_task) -> str:
    info = build_navigation_task_information(navigation_task)
    paragraphs = [
        f"Task family: {info['family_display_name']}",
        f"Task subtype: {info['subtype_display_name']}",
        f"Objective: {info['objective']}",
    ]
    if info["summary"]:
        paragraphs.append("Summary: " + " ".join(info["summary"]))
    if info["scoring"]:
        paragraphs.append("Scoring: " + " ".join(info["scoring"]))
    if info["penalties"]:
        paragraphs.append("Penalties: " + " ".join(info["penalties"]))
    if info["overrides"]:
        paragraphs.append("Current task-specific values: " + " ".join(info["overrides"]))
    return "\n\n".join(_escape_latex(paragraph) for paragraph in paragraphs)
