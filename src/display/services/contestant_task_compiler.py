import datetime

from dateutil import parser
from django.utils.module_loading import import_string
from rest_framework import serializers

from display.calculators.calculator_utilities import round_time_second
from display.models import ContestantTaskConfiguration
from display.services.task_compiler import TaskCompiler
from display.utilities.cima_scoring_config import CimaScoringConfig
from display.utilities.task_types import CURVE_NAVIGATION_TIME_ESTIMATION, PRECISION_NAVIGATION, stored_task_type
from display.utilities.gate_definitions import (
    CIRCLE_CENTER,
    CIRCLE_ENTRY,
    CIRCLE_EXIT,
    CIRCLE_START,
    DUMMY,
    FINISHPOINT,
    STARTINGPOINT,
    TURNPOINT,
    UNKNOWN_LEG,
)
from display.utilities.route_building_utilities import (
    build_waypoint,
    calculate_and_update_legs,
    correct_gate_directions_to_the_right,
    create_perpendicular_line_at_end_gates,
    create_perpendicular_line_at_end_lonlat,
    insert_gate_ranges,
)


# declaration_payload["time_reference"]: how the declared times were given. "start_point": as seconds after the start
# point (kept in declaration_payload["relative_times"]; the timestamps under the task type's time key are what those
# seconds come to for the current start, recalculated by every compile). Otherwise: as the timestamps themselves.
TIME_REFERENCE = "time_reference"
TIME_REFERENCE_START_POINT = "start_point"
TIME_REFERENCE_ABSOLUTE = "absolute"
RELATIVE_TIMES = "relative_times"


def _join_names(names) -> str:
    """"TP1", "TP1 and TP2", "TP1, TP2 and FP"."""
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


class ContestantTaskCompilerStrategy:
    def __init__(self, compiler: "ContestantTaskCompiler"):
        self.compiler = compiler

    def declaration_form(self, compiled_task) -> dict:
        """
        What a crew needs to fill in the declaration: names only, so that nothing the route keeps secret (hidden gates,
        positions) is given away. The organiser's page reads the compiled route payload instead.
        """
        return {}

    def validate_declaration(self, declaration_payload: dict, compiled_task) -> list[str]:
        return []

    def build_effective_route_payload(self, compiled_task, declaration_payload: dict) -> dict:
        return {}

    def update_gate_times(self, gate_times: dict[str, str], declaration_payload: dict, compiled_task, compiled_effective_route_payload: dict) -> dict[str, str]:
        return gate_times

    def build_declaration_payload_from_input(self, declaration_input: dict) -> dict:
        return {}

    def normalize_declaration_payload(self, declaration_payload: dict, compiled_task) -> dict:
        return declaration_payload


class CurveOrPrecisionNavigationStrategy(ContestantTaskCompilerStrategy):
    def __init__(self, compiler: "ContestantTaskCompiler"):
        super().__init__(compiler)
        self.subtype = compiler.contestant.navigation_task.task_subtype

    def validate_declaration(self, declaration_payload: dict, compiled_task) -> list[str]:
        predictions = declaration_payload.get("known_time_gate_predictions")
        errors = []
        if not isinstance(predictions, dict) or len(predictions) == 0:
            if self.subtype == CURVE_NAVIGATION_TIME_ESTIMATION:
                errors.append("Give the time you expect to be at each turn point and at the finish point.")
            else:
                errors.append(
                    f"Give a time for {_join_names(self.compiler._get_declared_time_gate_names())}."
                )
            return errors

        if self.subtype == CURVE_NAVIGATION_TIME_ESTIMATION:
            tmax_seconds = int((self.compiler.contestant.navigation_task.task_config or {}).get("curve_navigation_tmax_seconds") or 0)
            fp_prediction = predictions.get("FP")
            if tmax_seconds > 0 and isinstance(fp_prediction, str):
                fp_time = parser.parse(fp_prediction)
                sp_time = self.compiler.contestant.takeoff_time + datetime.timedelta(minutes=self.compiler.contestant.minutes_to_starting_point)
                if (fp_time - sp_time).total_seconds() > tmax_seconds:
                    errors.append(
                        f"The time you gave for FP is more than {tmax_seconds // 60} min {tmax_seconds % 60:02d} s "
                        "after SP, the longest time allowed (Tmax). Give an earlier time for FP."
                    )
            return errors

        # 2.A2: the pilot declares the visible turn points and the finish point. Times of other points in a declaration
        # (the start point and hidden gates, which earlier declarations asked for) are ignored, not an error.
        required_names = self.compiler._get_declared_time_gate_names()
        missing = [name for name in required_names if name not in predictions]
        if missing:
            errors.append(f"Give a time for {_join_names(missing)}.")
        return errors

    def build_effective_route_payload(self, compiled_task, declaration_payload: dict) -> dict:
        if self.subtype != PRECISION_NAVIGATION:
            return {}
        required_names = self.compiler._get_declared_time_gate_names()
        predictions = declaration_payload.get("known_time_gate_predictions", {})
        return {
            "known_time_gate_predictions": {name: value for name, value in predictions.items() if name in required_names},
            "expected_prediction_names": required_names,
        }

    def update_gate_times(self, gate_times: dict[str, str], declaration_payload: dict, compiled_task, compiled_effective_route_payload: dict) -> dict[str, str]:
        predictions = declaration_payload.get("known_time_gate_predictions", {})
        if self.subtype != PRECISION_NAVIGATION:
            for key, value in predictions.items():
                if isinstance(value, str):
                    gate_times[key] = parser.parse(value).isoformat()
            return gate_times
        # 2.A2: only the declared turn points and the finish point take the pilot's times; the organisation estimates
        # the times of the hidden gates (and keeps the start point's) by interpolating along the route between them.
        declared = {
            name: parser.parse(value)
            for name, value in predictions.items()
            if name in self.compiler._get_declared_time_gate_names() and isinstance(value, str)
        }
        gate_times.update(
            {name: time.isoformat() for name, time in self.compiler._interpolate_gate_times(gate_times, declared).items()}
        )
        # takeoff/landing gate times still need to survive this filter -
        # TakeoffAndLandingGateCalculator.initiate_takeoff_and_landing_gates does an unguarded
        # gate_times[gate.name] lookup for every route.takeoff_gates/landing_gates entry and KeyErrors at calculator
        # construction otherwise.
        expected_names = set(self.compiler._get_precision_navigation_prediction_names())
        route = self.compiler.contestant.navigation_task.route
        expected_names |= {gate.name for gate in route.takeoff_gates} | {gate.name for gate in route.landing_gates}
        return {key: value for key, value in gate_times.items() if key in expected_names}

    def build_declaration_payload_from_input(self, declaration_input: dict) -> dict:
        predictions = declaration_input.get("known_time_gate_predictions")
        if predictions is None:
            predictions = declaration_input.get("known_time_gate_prediction")
        if not predictions:
            return {}
        if not isinstance(predictions, dict):
            raise serializers.ValidationError({"known_time_gate_predictions": "Expected a dictionary of gate predictions."})
        # 2.A2 asks for the turn points and the finish point only: times of other points are dropped, not rejected.
        declared_names = (
            set(self.compiler._get_declared_time_gate_names()) if self.subtype == PRECISION_NAVIGATION else None
        )
        return self.compiler.declared_times_payload(
            declaration_input, "known_time_gate_predictions", predictions, accepted_names=declared_names
        )

    def declaration_form(self, compiled_task) -> dict:
        return {"time_points": self.compiler._get_declared_time_gate_names()}


class ContractNavigationStrategy(ContestantTaskCompilerStrategy):
    def validate_declaration(self, declaration_payload: dict, compiled_task) -> list[str]:
        errors = []
        declared_sequence = declaration_payload.get("declared_sequence")
        if not isinstance(declared_sequence, list) or len(declared_sequence) == 0:
            errors.append(
                "Choose the turn points you will fly, in order: before MP, and between MP and FP."
            )
        else:
            catalogue_names = set(compiled_task.get_compiled_primitives().get("catalogue_turnpoint", []))
            mandatory_names = {"SP", "MP", "FP"}
            for item in declared_sequence:
                if item not in catalogue_names and item not in mandatory_names:
                    errors.append(f"{item} is not a turn point of this task. Take it out of your sequence.")
            if declared_sequence.count("MP") != 1:
                errors.append("Your sequence must have MP exactly once.")
            if declared_sequence.count("FP") != 1:
                errors.append("Your sequence must have FP exactly once.")
            if declared_sequence[-1] != "FP":
                errors.append("Your sequence must end with FP.")

        declared_t_seconds = declaration_payload.get("declared_t_seconds")
        if declared_t_seconds in (None, ""):
            errors.append("Give your period T: the time you will use from SP to MP, and again from MP to FP.")
        else:
            try:
                if float(declared_t_seconds) <= 0:
                    errors.append("Your period T must be longer than zero.")
            except (TypeError, ValueError):
                errors.append("Your period T must be a number of seconds.")
        return errors

    def declaration_form(self, compiled_task) -> dict:
        names = compiled_task.get_compiled_primitives().get("catalogue_turnpoint", [])
        return {
            "mandatory_points": ["SP", "MP", "FP"],
            "turnpoints": [name for name in names if isinstance(name, str)],
            # The period T (declared_t_seconds) is asked for besides the sequence
            "asks_for_period": True,
        }

    def build_effective_route_payload(self, compiled_task, declaration_payload: dict) -> dict:
        declared_sequence = declaration_payload.get("declared_sequence", [])
        declared_t_seconds = declaration_payload.get("declared_t_seconds")
        effective_waypoints = self.compiler._build_contract_navigation_effective_waypoints(compiled_task, declared_sequence)
        payload = {
            "declared_sequence": declared_sequence,
            "effective_waypoint_names": [item["name"] for item in effective_waypoints],
            "effective_waypoints": effective_waypoints,
            "time_model": self.compiler._build_contract_navigation_time_model(declared_sequence, declared_t_seconds),
        }
        if declared_t_seconds not in (None, ""):
            payload["declared_t_seconds"] = int(float(declared_t_seconds))
        return payload

    def update_gate_times(self, gate_times: dict[str, str], declaration_payload: dict, compiled_task, compiled_effective_route_payload: dict) -> dict[str, str]:
        gate_times.update(
            self.compiler._build_contract_navigation_declared_gate_times(compiled_effective_route_payload)
        )
        return gate_times

    def build_declaration_payload_from_input(self, declaration_input: dict) -> dict:
        declared_sequence = declaration_input.get("declared_sequence")
        declared_t_seconds = declaration_input.get("declared_t_seconds")
        if declared_sequence is None:
            before_values = declaration_input.get("declared_before_mp") or []
            after_values = declaration_input.get("declared_after_mp") or []
            if not isinstance(before_values, list) or not isinstance(after_values, list):
                raise serializers.ValidationError(
                    {"declared_sequence": "Expected declared_before_mp and declared_after_mp to be lists."}
                )
            declared_sequence = [value for value in before_values if value]
            declared_sequence.append("MP")
            declared_sequence.extend(value for value in after_values if value)
            declared_sequence.append("FP")
        if not isinstance(declared_sequence, list):
            raise serializers.ValidationError({"declared_sequence": "Expected a list of declared turnpoints."})
        normalized_sequence = [item for item in declared_sequence if item not in (None, "")]
        payload: dict = {"declared_sequence": normalized_sequence} if normalized_sequence else {}
        if declared_t_seconds not in (None, ""):
            try:
                payload["declared_t_seconds"] = int(float(declared_t_seconds))
            except (TypeError, ValueError):
                raise serializers.ValidationError({"declared_t_seconds": "Expected a numeric T in seconds."})
        return payload


class TurnpointHuntStrategy(ContestantTaskCompilerStrategy):
    def validate_declaration(self, declaration_payload: dict, compiled_task) -> list[str]:
        compulsory_point_names = self.compiler._get_turnpoint_hunt_compulsory_point_names(compiled_task)
        compulsory_point_times = self.compiler._get_turnpoint_hunt_compulsory_point_times(declaration_payload)
        declared_sequence = declaration_payload.get("declared_sequence") or []
        expected_free_targets = [item["name"] for item in self.compiler._build_turnpoint_hunt_targets_payload()]
        errors = []
        # Where the declaration is optional, no compulsory time is required either.
        minimum_required = 3 if stored_task_type(self.compiler.contestant.navigation_task).declaration_required else 0
        if not isinstance(compulsory_point_times, dict):
            errors.append(f"Give a time for each of the compulsory points: {_join_names(compulsory_point_names)}.")
        else:
            expected_names = set(compulsory_point_names)
            provided_names = set(compulsory_point_times.keys())
            unexpected = sorted(provided_names - expected_names)
            missing = [name for name in compulsory_point_names if name not in compulsory_point_times]
            if unexpected:
                errors.append(
                    f"{_join_names(unexpected)} {'is' if len(unexpected) == 1 else 'are'} not "
                    f"{'a compulsory point' if len(unexpected) == 1 else 'compulsory points'} of this task. "
                    "Take the time out."
                )
            if minimum_required > 0 and missing:
                errors.append(f"Give a time for {_join_names(missing)}.")
        if declared_sequence:
            if not isinstance(declared_sequence, list):
                errors.append("Give your sequence as a list of the points in the order you will fly them.")
            else:
                normalized_sequence = [item for item in declared_sequence if isinstance(item, str)]
                allowed_compulsory_names = set(compulsory_point_names)
                unknown = [item for item in normalized_sequence if item not in expected_free_targets and item not in allowed_compulsory_names]
                if unknown:
                    errors.append(
                        f"{_join_names(unknown)} {'is not a target' if len(unknown) == 1 else 'are not targets'} of this "
                        "task. Take it out of your sequence."
                    )
                duplicates = sorted({item for item in normalized_sequence if normalized_sequence.count(item) > 1})
                if duplicates:
                    errors.append(
                        f"{_join_names(duplicates)} is in your sequence more than once. List each point once."
                    )
                compulsory_sequence = [item for item in normalized_sequence if item in allowed_compulsory_names]
                if sorted(compulsory_sequence) != sorted(compulsory_point_names):
                    errors.append(
                        f"Your sequence must have each compulsory point ({_join_names(compulsory_point_names)}) exactly once."
                    )
                else:
                    ordered_compulsory_names = self.compiler._get_turnpoint_hunt_ordered_compulsory_point_names(compulsory_point_times, compulsory_point_names)
                    if compulsory_sequence != ordered_compulsory_names:
                        errors.append(
                            f"Put the compulsory points in the order of the times you gave: {_join_names(ordered_compulsory_names)}. "
                            "Change the times or the sequence."
                        )
        fuel_metadata = declaration_payload.get("fuel_metadata") or {}
        if fuel_metadata and not isinstance(fuel_metadata, dict):
            errors.append("Give your fuel endurance as a number of minutes.")
        return errors

    def build_effective_route_payload(self, compiled_task, declaration_payload: dict) -> dict:
        compulsory_point_names = self.compiler._get_turnpoint_hunt_compulsory_point_names(compiled_task)
        compulsory_point_times = self.compiler._get_turnpoint_hunt_compulsory_point_times(declaration_payload)
        effective_waypoints = self.compiler._build_turnpoint_hunt_effective_waypoints(compiled_task, compulsory_point_names, declaration_payload)
        free_targets = self.compiler._build_turnpoint_hunt_targets_payload()
        declared_sequence = declaration_payload.get("declared_sequence", [])
        effective_waypoint_names = [item["name"] for item in effective_waypoints]
        # Not a positional slice of effective_waypoint_names (was `effective_waypoint_names[:
        # len(compulsory_point_names)]`) - that assumed the 3 compulsory gates always sort first
        # in the effective sequence, which only held when there was no declared_sequence at all.
        # With one (the normal case - validation requires every compulsory name to appear in
        # it), the contestant can freely interleave compulsory and free targets ("CP1, A, CP2,
        # B, CP3"), so a positional slice silently picked up free targets instead of (or as well
        # as) real compulsory names. compulsory_point_names is already exactly the right set,
        # computed independently of ordering - just reuse it, matching the sibling
        # (no-declaration) codepath below, which never had this bug.
        compulsory_timing_gate_names = compulsory_point_names
        payload = {
            "compulsory_point_names": compulsory_point_names,
            "compulsory_point_times": compulsory_point_times,
            "declared_sequence": declared_sequence,
            "effective_waypoint_names": effective_waypoint_names,
            "effective_waypoints": effective_waypoints,
            "compulsory_timing_gate_names": compulsory_timing_gate_names,
            "compulsory_timing_tolerance_seconds": self.compiler.cima_config.compulsory_timing_tolerance_seconds,
            "free_targets": free_targets,
            "free_target_names": [item["name"] for item in free_targets],
            "free_target_evidence": {
                item["name"]: [evidence["name"] for evidence in item.get("evidence", [])]
                for item in free_targets
            },
            "observation_photos": self.compiler._build_turnpoint_hunt_observation_photos(free_targets),
            "scored_target_values": self.compiler._build_turnpoint_hunt_scored_target_values(free_targets),
        }
        maximum_task_duration_minutes = self.compiler.cima_config.maximum_task_duration_minutes
        if maximum_task_duration_minutes is not None:
            payload["maximum_task_duration_minutes"] = int(maximum_task_duration_minutes)
            payload["maximum_task_duration_deadline"] = (
                self.compiler.contestant.takeoff_time + datetime.timedelta(minutes=int(maximum_task_duration_minutes))
            ).isoformat()
        if fuel_metadata := declaration_payload.get("fuel_metadata"):
            payload["fuel_metadata"] = fuel_metadata
            declared_endurance_minutes = fuel_metadata.get("declared_endurance_minutes")
            if declared_endurance_minutes is not None:
                payload["fuel_deadline"] = (
                    self.compiler.contestant.takeoff_time + datetime.timedelta(minutes=int(declared_endurance_minutes))
                ).isoformat()
        return payload

    def update_gate_times(self, gate_times: dict[str, str], declaration_payload: dict, compiled_task, compiled_effective_route_payload: dict) -> dict[str, str]:
        compulsory_point_times = self.compiler._get_turnpoint_hunt_compulsory_point_times(declaration_payload)
        for key, value in compulsory_point_times.items():
            if isinstance(value, str):
                gate_times[key] = parser.parse(value).isoformat()
        gate_times.update(self.compiler._build_turnpoint_hunt_declared_gate_times(compiled_effective_route_payload, declaration_payload))
        # Every gate of the effective route needs an expected time (GateCalculator.create_gates). A free target the
        # declared sequence does not place (no sequence, or a target left out of it) has no time of its own and is never
        # scored on one, so it takes the earliest declared time; 2.B2 flies such targets in any order.
        known = [parser.parse(value) for name, value in gate_times.items() if name in compulsory_point_times and isinstance(value, str)]
        placeholder = (min(known) if known else self.compiler.contestant.gate_time_anchor()).isoformat()
        for name in compiled_effective_route_payload.get("effective_waypoint_names") or []:
            gate_times.setdefault(name, placeholder)
        return gate_times

    def build_declaration_payload_from_input(self, declaration_input: dict) -> dict:
        compulsory_point_times = declaration_input.get("compulsory_point_times")
        if compulsory_point_times is None:
            compulsory_point_times = declaration_input.get("predicted_gate_times") or {}
        fuel_metadata = declaration_input.get("fuel_metadata") or {}
        if not isinstance(compulsory_point_times, dict):
            raise serializers.ValidationError({"compulsory_point_times": "Give the times as a list of compulsory points with a time each."})
        if not isinstance(fuel_metadata, dict):
            raise serializers.ValidationError({"fuel_metadata": "Give the fuel endurance as a number of minutes."})
        declared_sequence = declaration_input.get("declared_sequence") or declaration_input.get("predicted_sequence") or []
        if declared_sequence and not isinstance(declared_sequence, list):
            raise serializers.ValidationError({"declared_sequence": "Expected a list of declared turnpoints."})
        payload = self.compiler.declared_times_payload(declaration_input, "compulsory_point_times", compulsory_point_times)
        normalized_sequence = [item for item in declared_sequence if isinstance(item, str) and item]
        if normalized_sequence:
            payload["declared_sequence"] = normalized_sequence
        if fuel_metadata:
            payload["fuel_metadata"] = fuel_metadata
        return payload

    def declaration_form(self, compiled_task) -> dict:
        return {
            "compulsory_points": self.compiler._get_turnpoint_hunt_compulsory_point_names(compiled_task),
            "targets": [item["name"] for item in self.compiler._build_turnpoint_hunt_targets_payload()],
            "asks_for_fuel_endurance": stored_task_type(self.compiler.contestant.navigation_task).has_fuel_deadline,
        }

    def normalize_declaration_payload(self, declaration_payload: dict, compiled_task) -> dict:
        normalized_payload = dict(declaration_payload or {})
        compulsory_point_times = self.compiler._get_turnpoint_hunt_compulsory_point_times(normalized_payload)
        declared_sequence = [item for item in (normalized_payload.get("declared_sequence") or []) if isinstance(item, str)]
        compulsory_point_names = self.compiler._get_turnpoint_hunt_compulsory_point_names(compiled_task)
        ordered_compulsory_names = self.compiler._get_turnpoint_hunt_ordered_compulsory_point_names(compulsory_point_times, compulsory_point_names)
        if declared_sequence and ordered_compulsory_names:
            declared_free_targets = [item for item in declared_sequence if item not in compulsory_point_names]
            declared_compulsory_names = [item for item in declared_sequence if item in compulsory_point_names]
            if sorted(declared_compulsory_names) == sorted(ordered_compulsory_names):
                free_target_names = set(item["name"] for item in self.compiler._build_turnpoint_hunt_targets_payload())
                free_targets_are_unique = len(set(declared_free_targets)) == len(declared_free_targets)
                if free_targets_are_unique and all(item in free_target_names for item in declared_free_targets):
                    relative_slots = []
                    for target_name in declared_free_targets:
                        target_index = declared_sequence.index(target_name)
                        slot = len([name for name in declared_compulsory_names if declared_sequence.index(name) < target_index])
                        relative_slots.append((slot, target_name))
                    free_targets_by_slot = {}
                    for slot, target_name in relative_slots:
                        free_targets_by_slot.setdefault(slot, []).append(target_name)
                    rebuilt_sequence = []
                    for slot in range(0, len(ordered_compulsory_names) + 1):
                        rebuilt_sequence.extend(free_targets_by_slot.get(slot, []))
                        if slot < len(ordered_compulsory_names):
                            rebuilt_sequence.append(ordered_compulsory_names[slot])
                    normalized_payload["declared_sequence"] = rebuilt_sequence
        return normalized_payload


class DurationStrategy(ContestantTaskCompilerStrategy):
    def build_effective_route_payload(self, compiled_task, declaration_payload: dict) -> dict:
        return self.compiler._build_duration_payload()

    def validate_declaration(self, declaration_payload: dict, compiled_task) -> list[str]:
        return []


class CircleStrategy(ContestantTaskCompilerStrategy):
    """2.A7: no route backbone - the four circle markers (start/entry/center/exit)
    are free-map points. Without this strategy, compiled_effective_route_payload
    carries no effective_waypoints, GateCalculator.create_gates() has nothing to
    build gates from, and CircleCalculator.on_gate_passed is never reached.
    """

    def build_effective_route_payload(self, compiled_task, declaration_payload: dict) -> dict:
        return self.compiler._build_circle_effective_route_payload()

    def update_gate_times(
        self,
        gate_times: dict[str, str],
        declaration_payload: dict,
        compiled_task,
        compiled_effective_route_payload: dict,
    ) -> dict[str, str]:
        # Circle waypoints are gate_check-only (time_check=False, see
        # _build_circle_effective_route_payload), so these times are never
        # scored - they only need to exist so create_gates()'s
        # expected_times[item.name] lookup does not KeyError.
        base_time = self.compiler.contestant.takeoff_time + datetime.timedelta(
            minutes=self.compiler.contestant.minutes_to_starting_point
        )
        for name in compiled_effective_route_payload.get("effective_waypoint_names", []):
            gate_times.setdefault(name, base_time.isoformat())
        return gate_times

    def validate_declaration(self, declaration_payload: dict, compiled_task) -> list[str]:
        return []


class ObservationEvidenceStrategy(ContestantTaskCompilerStrategy):
    def build_effective_route_payload(self, compiled_task, declaration_payload: dict) -> dict:
        return self.compiler._build_observation_evidence_payload(compiled_task)


class KnownCircuitStrategy(ContestantTaskCompilerStrategy):
    """2.A4: contestant flies a known circuit at a declared uniform speed, with the
    option to declare a specific time at individual turnpoints. Overridden points use
    that declared time instead of the speed-derived one; every other point still
    follows the uniform-speed chain (Contestant.calculate_missing_gate_times).
    """

    def validate_declaration(self, declaration_payload: dict, compiled_task) -> list[str]:
        overrides = declaration_payload.get("turnpoint_time_overrides")
        if not overrides:
            return []
        if not isinstance(overrides, dict):
            return ["Give the turn point times as a list of turn points with a time each."]
        valid_names = set(self.compiler._get_precision_navigation_prediction_names())
        unknown = sorted(set(overrides.keys()) - valid_names)
        if unknown:
            return [
                f"{_join_names(unknown)} {'is not a point' if len(unknown) == 1 else 'are not points'} of this "
                "circuit. Take the time out."
            ]
        return []

    def declaration_form(self, compiled_task) -> dict:
        return {"time_points": self.compiler._get_declared_time_gate_names()}

    def build_effective_route_payload(self, compiled_task, declaration_payload: dict) -> dict:
        payload = self.compiler._build_observation_evidence_payload(compiled_task)
        overrides = declaration_payload.get("turnpoint_time_overrides") or {}
        payload["overridden_gate_names"] = sorted(overrides.keys())
        return payload

    def update_gate_times(
        self,
        gate_times: dict[str, str],
        declaration_payload: dict,
        compiled_task,
        compiled_effective_route_payload: dict,
    ) -> dict[str, str]:
        overrides = declaration_payload.get("turnpoint_time_overrides") or {}
        for key, value in overrides.items():
            if isinstance(value, str):
                gate_times[key] = parser.parse(value).isoformat()
        return gate_times

    def build_declaration_payload_from_input(self, declaration_input: dict) -> dict:
        overrides = declaration_input.get("turnpoint_time_overrides")
        if not overrides:
            return {}
        if not isinstance(overrides, dict):
            raise serializers.ValidationError(
                {"turnpoint_time_overrides": "Give the turn point times as a list of turn points with a time each."}
            )
        return self.compiler.declared_times_payload(declaration_input, "turnpoint_time_overrides", overrides)


class UnknownLegsStrategy(ContestantTaskCompilerStrategy):
    def build_effective_route_payload(self, compiled_task, declaration_payload: dict) -> dict:
        payload = self.compiler._build_observation_evidence_payload(compiled_task)
        payload.update(self.compiler._build_unknown_legs_payload(compiled_task))
        return payload


class ContestantTaskCompiler:
    def __init__(self, contestant):
        self.contestant = contestant

    @property
    def cima_config(self) -> CimaScoringConfig:
        return CimaScoringConfig.from_scorecard(self.contestant.navigation_task.scorecard)

    def _require_declared_times_within_contestant_window(self, normalized_times: dict[str, str], field_name: str) -> None:
        """
        Predicted gate times are declared as absolute timestamps (not offsets from takeoff), so
        entering one outside the contestant's own [takeoff_time, finished_by_time] window would
        produce a declaration that's already stale the moment it's saved. See
        ABSOLUTE_TIME_DECLARATION_SUBTYPES for the other half of this guard, which stops the
        window itself from being moved out from under an already-declared time.
        """
        takeoff_time = self.contestant.takeoff_time
        finished_by_time = self.contestant.finished_by_time
        out_of_window = []
        for key, value in normalized_times.items():
            declared_time = parser.parse(value)
            if declared_time < takeoff_time or declared_time > finished_by_time:
                out_of_window.append(key)
        if out_of_window:
            raise serializers.ValidationError(
                {
                    field_name: (
                        f"The time for {_join_names(out_of_window)} is outside this flight, which is from take-off at "
                        f"{takeoff_time.astimezone(datetime.timezone.utc):%Y-%m-%d %H:%M} UTC to "
                        f"{finished_by_time.astimezone(datetime.timezone.utc):%Y-%m-%d %H:%M} UTC. Give a time "
                        "during the flight."
                    )
                }
            )

    def declared_times_payload(
        self, declaration_input: dict, key: str, raw_times: dict, accepted_names: set | None = None
    ) -> dict:
        """
        The declaration_payload part for the declared times [raw_times] (point name to a timestamp, or to seconds after the
        start point when declaration_input["time_reference"] is "start_point"). Always holds the timestamps under [key],
        which is what the rest of the compiler reads; a declaration in seconds also keeps them (relative_times) and says so
        (time_reference), so that they follow the start point when it moves. Names outside [accepted_names] are dropped.
        """
        reference = declaration_input.get(TIME_REFERENCE) or TIME_REFERENCE_ABSOLUTE
        if reference not in (TIME_REFERENCE_ABSOLUTE, TIME_REFERENCE_START_POINT):
            raise serializers.ValidationError(
                {TIME_REFERENCE: f'Use "{TIME_REFERENCE_START_POINT}" for times in seconds after the start point, or '
                 f'"{TIME_REFERENCE_ABSOLUTE}" for clock times.'}
            )
        relative = reference == TIME_REFERENCE_START_POINT
        times: dict[str, str] = {}
        offsets: dict[str, float] = {}
        anchor = self.contestant.gate_time_anchor()
        longest = (self.contestant.finished_by_time - self.contestant.takeoff_time).total_seconds()
        for name, value in raw_times.items():
            if value in (None, "") or (accepted_names is not None and name not in accepted_names):
                continue
            if relative:
                seconds = self._parse_seconds_after_start(name, value, key)
                if seconds < 0 or seconds > longest:
                    raise serializers.ValidationError(
                        {key: f"The time for {name} is outside the flight. Give the time after the start point, "
                              f"between 0 and {int(longest // 60)} minutes."}
                    )
                offsets[name] = int(seconds) if float(seconds).is_integer() else seconds
                times[name] = (anchor + datetime.timedelta(seconds=seconds)).isoformat()
            elif isinstance(value, str):
                try:
                    times[name] = parser.parse(value).isoformat()
                except (ValueError, OverflowError):
                    raise serializers.ValidationError({key: f"The time for {name} is not a valid date and time."})
            elif isinstance(value, datetime.datetime):
                times[name] = value.isoformat()
            else:
                raise serializers.ValidationError({key: f"The time for {name} is not a valid date and time."})
        # With an adaptive start the clock time of the start is not known yet: the offsets are checked above instead.
        if not (relative and self.contestant.adaptive_start):
            self._require_declared_times_within_contestant_window(times, key)
        if not times:
            return {}
        if relative:
            return {key: times, TIME_REFERENCE: TIME_REFERENCE_START_POINT, RELATIVE_TIMES: offsets}
        return {key: times}

    @staticmethod
    def _parse_seconds_after_start(name: str, value, key: str) -> float:
        """Seconds from a number, a numeric string or a "minutes:seconds" / "hours:minutes:seconds" string."""
        message = {key: f'The time for {name} must be the time after the start point, like "12:30" or 750 seconds.'}
        if isinstance(value, bool):
            raise serializers.ValidationError(message)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                parts = [float(part) for part in value.strip().split(":")]
            except ValueError:
                raise serializers.ValidationError(message)
            if 1 <= len(parts) <= 3 and all(part >= 0 for part in parts):
                seconds = 0.0
                for part in parts:
                    seconds = seconds * 60 + part
                return seconds
        raise serializers.ValidationError(message)

    def materialise_relative_times(self, declaration_payload: dict, anchor: datetime.datetime | None = None) -> dict:
        """
        The declaration with the timestamps of a declaration made in seconds after the start point calculated from those
        seconds and [anchor] (default: the start point as known now: planned, or with an adaptive start the real crossing
        once there is one and else a placeholder at midnight). Other declarations are returned as they are.
        """
        if not isinstance(declaration_payload, dict) or declaration_payload.get(TIME_REFERENCE) != TIME_REFERENCE_START_POINT:
            return declaration_payload
        key = stored_task_type(self.contestant.navigation_task).absolute_time_declaration_key
        offsets = declaration_payload.get(RELATIVE_TIMES)
        if not key or not isinstance(offsets, dict):
            return declaration_payload
        anchor = anchor or self.contestant.gate_time_anchor()
        materialised = dict(declaration_payload)
        materialised[key] = {
            name: (anchor + datetime.timedelta(seconds=float(seconds))).isoformat() for name, seconds in offsets.items()
        }
        return materialised

    def gate_times_for_adaptive_start(
        self, gate_times: dict[str, datetime.datetime], starting_point_time: datetime.datetime
    ) -> dict[str, datetime.datetime]:
        """
        [gate_times] (calculated from the route for a start at [starting_point_time]) with the times the crew declared as
        seconds after the start point applied to that start. A declaration in clock times, or none, leaves them as they are.
        """
        config = getattr(self.contestant, "contestanttaskconfiguration", None)
        declaration = (config.declaration_payload or {}) if config and config.is_valid else {}
        if declaration.get(TIME_REFERENCE) != TIME_REFERENCE_START_POINT:
            return gate_times
        declaration = self.materialise_relative_times(declaration, starting_point_time)
        compiled_task = TaskCompiler(self.contestant.navigation_task).compile()
        effective = self._build_effective_route_payload(compiled_task, declaration)
        updated = self._get_strategy().update_gate_times(
            {name: time.isoformat() for name, time in gate_times.items()}, declaration, compiled_task, effective
        )
        return {name: parser.parse(value) if isinstance(value, str) else value for name, value in updated.items()}

    def declaration_form(self) -> dict:
        """The points a crew declares, by name (see ContestantTaskCompilerStrategy.declaration_form)."""
        compiled_task = TaskCompiler(self.contestant.navigation_task).compile()
        return self._get_strategy().declaration_form(compiled_task)

    def _get_strategy(self) -> ContestantTaskCompilerStrategy:
        strategy_path = stored_task_type(self.contestant.navigation_task).contestant_compiler_strategy
        if strategy_path is None:
            return ContestantTaskCompilerStrategy(self)
        return import_string(strategy_path)(self)

    def compile(self, declaration_payload: dict | None = None, force: bool = False) -> ContestantTaskConfiguration:
        declaration_payload = declaration_payload or {}
        # Dependency order matters here:
        # 1) compile shared task primitives first,
        # 2) normalize declaration payload against the compiled task snapshot,
        # 3) build contestant-specific effective route payload from those primitives,
        # 4) derive gate times from the compiled effective payload,
        # 5) validate against compiled primitives/effective data before persisting.
        # Every phase below intentionally uses the same compiled-task snapshot
        # so subtype validation, payload synthesis, and gate-time overrides all
        # depend on one authoritative view of task primitives/config.
        compiled_task = TaskCompiler(self.contestant.navigation_task).compile()
        declaration_payload = self.materialise_relative_times(declaration_payload)
        declaration_payload = self._get_strategy().normalize_declaration_payload(declaration_payload, compiled_task)
        compiled_effective_route_payload = self._build_effective_route_payload(compiled_task, declaration_payload)
        compiled_gate_times_payload = self._build_gate_times_payload(
            declaration_payload,
            compiled_task,
            compiled_effective_route_payload,
        )
        validation_errors = self._validate_declaration(declaration_payload, compiled_task)
        validation_errors.extend(compiled_task.compiled_payload.get("validation_errors", []))
        is_valid = len(validation_errors) == 0

        config, _ = ContestantTaskConfiguration.objects.get_or_create(
            contestant=self.contestant,
            defaults={
                "task_subtype": self.contestant.navigation_task.task_subtype or "",
                "declaration_payload": declaration_payload,
                "compiled_effective_route_payload": compiled_effective_route_payload,
                "compiled_gate_times_payload": compiled_gate_times_payload,
                "validation_errors": validation_errors,
                "is_valid": is_valid,
            },
        )
        needs_refresh = force or any(
            (
                config.task_subtype != (self.contestant.navigation_task.task_subtype or ""),
                config.declaration_payload != declaration_payload,
                config.compiled_effective_route_payload != compiled_effective_route_payload,
                config.compiled_gate_times_payload != compiled_gate_times_payload,
                config.validation_errors != validation_errors,
                config.is_valid != is_valid,
            )
        )
        if needs_refresh:
            config.task_subtype = self.contestant.navigation_task.task_subtype or ""
            config.declaration_payload = declaration_payload
            config.compiled_effective_route_payload = compiled_effective_route_payload
            config.compiled_gate_times_payload = compiled_gate_times_payload
            config.validation_errors = validation_errors
            config.is_valid = is_valid
            config.save()
        self._lock_if_needed(config)
        return config

    def _validate_declaration(self, declaration_payload: dict, compiled_task) -> list[str]:
        if not isinstance(declaration_payload, dict):
            return ["Declaration payload must be a dictionary."]

        return self._get_strategy().validate_declaration(declaration_payload, compiled_task)

    def _base_effective_route_payload(self, compiled_task) -> dict:
        route = self.contestant.navigation_task.route
        return {
            "route_id": route.pk,
            "waypoint_names": [item.name for item in route.waypoints],
            "compiled_task_primitives": compiled_task.get_compiled_primitives(),
            "compiled_auxiliary_paths": (compiled_task.compiled_payload or {}).get("compiled_auxiliary_paths", {}),
        }

    def _build_precision_navigation_payload(self, declaration_payload: dict) -> dict:
        return {
            "known_time_gate_predictions": declaration_payload.get("known_time_gate_predictions", {}),
            "expected_prediction_names": self._get_declared_time_gate_names(),
        }

    def _build_contract_navigation_payload(self, compiled_task, declaration_payload: dict) -> dict:
        declared_sequence = declaration_payload.get("declared_sequence", [])
        declared_t_seconds = declaration_payload.get("declared_t_seconds")
        effective_waypoints = self._build_contract_navigation_effective_waypoints(compiled_task, declared_sequence)
        payload = {
            "declared_sequence": declared_sequence,
            "effective_waypoint_names": [item["name"] for item in effective_waypoints],
            "effective_waypoints": effective_waypoints,
            "time_model": self._build_contract_navigation_time_model(declared_sequence, declared_t_seconds),
        }
        if declared_t_seconds not in (None, ""):
            payload["declared_t_seconds"] = int(float(declared_t_seconds))
        return payload

    def _build_turnpoint_hunt_payload(self, compiled_task, declaration_payload: dict) -> dict:
        compulsory_point_names = self._get_turnpoint_hunt_compulsory_point_names(compiled_task)
        compulsory_point_times = self._get_turnpoint_hunt_compulsory_point_times(declaration_payload)
        effective_waypoints = self._build_turnpoint_hunt_effective_waypoints(compiled_task, compulsory_point_names)
        free_targets = self._build_turnpoint_hunt_targets_payload()
        payload = {
            "compulsory_point_names": compulsory_point_names,
            "compulsory_point_times": compulsory_point_times,
            "effective_waypoint_names": [item["name"] for item in effective_waypoints],
            "effective_waypoints": effective_waypoints,
            "compulsory_timing_gate_names": compulsory_point_names,
            "compulsory_timing_tolerance_seconds": self.cima_config.compulsory_timing_tolerance_seconds,
            "free_targets": free_targets,
            "free_target_names": [item["name"] for item in free_targets],
            "free_target_evidence": {
                item["name"]: [evidence["name"] for evidence in item.get("evidence", [])]
                for item in free_targets
            },
            "observation_photos": self._build_turnpoint_hunt_observation_photos(free_targets),
            "scored_target_values": self._build_turnpoint_hunt_scored_target_values(free_targets),
        }
        maximum_task_duration_minutes = self.cima_config.maximum_task_duration_minutes
        if maximum_task_duration_minutes is not None:
            payload["maximum_task_duration_minutes"] = int(maximum_task_duration_minutes)
            payload["maximum_task_duration_deadline"] = (
                self.contestant.takeoff_time + datetime.timedelta(minutes=int(maximum_task_duration_minutes))
            ).isoformat()
        if fuel_metadata := declaration_payload.get("fuel_metadata"):
            payload["fuel_metadata"] = fuel_metadata
            declared_endurance_minutes = fuel_metadata.get("declared_endurance_minutes")
            if declared_endurance_minutes is not None:
                payload["fuel_deadline"] = (
                    self.contestant.takeoff_time + datetime.timedelta(minutes=int(declared_endurance_minutes))
                ).isoformat()
        return payload

    def _build_duration_payload(self) -> dict:
        duration_review = {}
        if self.cima_config.duration_normalization_policy:
            duration_review["duration_normalization_policy"] = self.cima_config.duration_normalization_policy
        task_config = self.contestant.navigation_task.task_config or {}
        editable_route = self.contestant.navigation_task.editable_route
        if editable_route is not None:
            duration_polygons = editable_route.get_duration_landing_area_polygons()
            if duration_polygons:
                polygon = duration_polygons[0].get("geometry", {}).get("coordinates", [[]])[0]
                if len(polygon) > 1 and polygon[0] == polygon[-1]:
                    polygon = polygon[:-1]
                duration_review["duration_landing_area_polygon"] = polygon
        if task_config.get("duration_residual_fuel_required") or self.cima_config.duration_residual_fuel_required:
            duration_review["duration_residual_fuel_required"] = True
        return {"duration_review": duration_review} if duration_review else {}

    def _build_circle_markers(self) -> dict[str, dict]:
        """First circle marker feature of each role, keyed by gate_definitions
        type. Exactly one of each is required (the circle task type's
        required_primitives); if authoring left one out we return {} and let
        build_effective_route_payload fall back to no effective route rather
        than build a partial/broken one.
        """
        editable_route = self.contestant.navigation_task.editable_route
        if editable_route is None:
            return {}
        accessors = {
            CIRCLE_START: editable_route.get_circle_start_markers,
            CIRCLE_ENTRY: editable_route.get_circle_entry_markers,
            CIRCLE_CENTER: editable_route.get_circle_center_markers,
            CIRCLE_EXIT: editable_route.get_circle_exit_markers,
        }
        markers = {}
        for marker_type, accessor in accessors.items():
            features = accessor()
            if features:
                markers[marker_type] = features[0]
        return markers

    def _build_circle_effective_route_payload(self) -> dict:
        order = [CIRCLE_START, CIRCLE_ENTRY, CIRCLE_CENTER, CIRCLE_EXIT]
        markers = self._build_circle_markers()
        if not all(marker_type in markers for marker_type in order):
            return {}

        effective_waypoints = []
        for marker_type in order:
            feature = markers[marker_type]
            properties = feature.get("properties", {})
            coordinates = feature.get("geometry", {}).get("coordinates", [])
            if len(coordinates) != 2:
                return {}
            lon, lat = coordinates
            width_nm = float(properties.get("width") or 1852) / 1852
            # time_check=False, gate_check=False: a circle is scored on
            # geometry (radius, direction, altitude spread) by
            # CircleCalculator, not on GateCalculator's crossing-time/missed-gate
            # scoring - see CircleStrategy.update_gate_times and the
            # CIRCLE_CENTER exclusion in GateCalculator.create_gates.
            effective_waypoints.append(
                build_waypoint(properties.get("name") or marker_type, lat, lon, marker_type, width_nm, False, False)
            )

        self._apply_effective_gate_lines(effective_waypoints)
        calculate_and_update_legs(effective_waypoints, self.contestant.navigation_task.route.use_procedure_turns)
        insert_gate_ranges(effective_waypoints)

        # Each waypoint's `type` is one of CIRCLE_START/CIRCLE_ENTRY/CIRCLE_CENTER/
        # CIRCLE_EXIT (see the build_waypoint call above), so CircleCalculator can
        # recover full role/name/coordinate geometry straight from
        # effective_waypoints - no separate geometry block needed.
        return {
            "effective_waypoint_names": [waypoint.name for waypoint in effective_waypoints],
            "effective_waypoints": [self._serialise_waypoint(waypoint) for waypoint in effective_waypoints],
        }

    def _build_effective_route_payload(self, compiled_task, declaration_payload: dict) -> dict:
        payload = self._base_effective_route_payload(compiled_task)
        payload.update(self._get_strategy().build_effective_route_payload(compiled_task, declaration_payload))
        return payload

    def _build_observation_evidence_payload(self, compiled_task) -> dict:
        editable_route = self.contestant.navigation_task.editable_route
        if editable_route is None:
            return {"observation_photos": [], "hidden_gate_names": [], "unknown_leg_names": []}
        observation_photos = [
            {
                "name": item.get("properties", {}).get("name"),
                "coordinates": item.get("geometry", {}).get("coordinates", []),
                "evidence_category": "observation",
            }
            for item in editable_route.get_observation_photos()
        ]
        return {
            "observation_judging_mode": "external_manual",
            "manual_adjudication_categories": ["observation", "map"],
            "observation_photos": observation_photos,
            "hidden_gate_names": compiled_task.get_compiled_primitives().get("hidden_gate", []),
            "unknown_leg_names": compiled_task.get_compiled_primitives().get("unknown_leg", []),
        }

    def _build_unknown_legs_payload(self, compiled_task) -> dict:
        payload = (compiled_task.compiled_payload or {}) if compiled_task else {}
        return {
            "segments": payload.get("unknown_legs_segments", []),
            "actual_route": payload.get(
                "unknown_legs_actual_route",
                {"waypoint_names": [], "waypoints": [], "unknown_leg_connectors": []},
            ),
            "hidden_gates": payload.get("unknown_legs_hidden_gates", []),
            "map_rendering_mode": "unknown_legs_split",
        }

    def _get_turnpoint_hunt_compulsory_point_names(self, compiled_task) -> list[str]:
        primitive_names = [name for name in compiled_task.get_compiled_primitives().get("known_time_gate", []) if name]
        if len(primitive_names) == 3:
            return primitive_names
        editable_route = self.contestant.navigation_task.editable_route
        if editable_route is not None:
            authored_waypoints = editable_route.get_ordered_track_waypoints()
            if len(authored_waypoints) == 3:
                return [
                    item.get("properties", {}).get("name")
                    for item in authored_waypoints
                    if item.get("properties", {}).get("name")
                ]
        base_waypoints = self.contestant.navigation_task.route.waypoints
        return [waypoint.name for waypoint in base_waypoints[:3] if getattr(waypoint, "name", None)]

    def _get_turnpoint_hunt_compulsory_point_times(self, declaration_payload: dict) -> dict:
        point_times = declaration_payload.get("compulsory_point_times")
        if point_times is None:
            point_times = declaration_payload.get("predicted_gate_times")
        return point_times or {}

    def _get_turnpoint_hunt_ordered_compulsory_point_names(self, compulsory_point_times: dict, compulsory_point_names: list[str]) -> list[str]:
        ordered_pairs = []
        for index, name in enumerate(compulsory_point_names):
            raw_value = compulsory_point_times.get(name)
            if isinstance(raw_value, str):
                ordered_pairs.append((parser.parse(raw_value), index, name))
        if len(ordered_pairs) != len(compulsory_point_names):
            return [name for name in compulsory_point_names if name in compulsory_point_times]
        ordered_pairs.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in ordered_pairs]

    def _build_turnpoint_hunt_targets_payload(self) -> list[dict]:
        # This compiled target payload is the shared compatibility bridge for
        # turnpoint-hunt declarations. Payload builders, synthetic gate-time
        # generation, and evidence/value extraction all read the same normalized
        # structure so they cannot drift on target names/evidence association.
        editable_route = self.contestant.navigation_task.editable_route
        if editable_route is None:
            return []
        photos = editable_route.get_observation_photos()
        targets = []
        for target in editable_route.get_catalogue_turnpoints():
            properties = target.get("properties", {})
            name = properties.get("name")
            if not name:
                continue
            evidence = []
            for photo in photos:
                photo_props = photo.get("properties", {})
                target_name = photo_props.get("targetName") or photo_props.get("name")
                if target_name == name:
                    evidence.append(
                        {
                            "name": photo_props.get("name"),
                            "coordinates": photo.get("geometry", {}).get("coordinates", []),
                        }
                    )
            targets.append(
                {
                    "name": name,
                    "coordinates": target.get("geometry", {}).get("coordinates", []),
                    "score_value": float(properties.get("scoreValue")) if properties.get("scoreValue") not in (None, "") else None,
                    "evidence": evidence,
                }
            )
        return targets

    def _build_turnpoint_hunt_observation_photos(self, free_targets: list[dict]) -> list[dict]:
        observation_photos = []
        for target in free_targets:
            for evidence in target.get("evidence", []):
                observation_photos.append(
                    {
                        "name": evidence.get("name"),
                        "target_name": target.get("name"),
                        "coordinates": evidence.get("coordinates", []),
                        "evidence_category": "observation",
                    }
                )
        return observation_photos

    def _build_turnpoint_hunt_scored_target_values(self, free_targets: list[dict]) -> dict[str, float]:
        scored_values = {}
        for item in free_targets:
            score_value = item.get("score_value")
            if score_value is not None:
                scored_values[item["name"]] = float(score_value)
        return scored_values

    def _get_precision_navigation_prediction_names(self) -> list[str]:
        return [
            waypoint.name
            for waypoint in self.contestant.navigation_task.route.waypoints
            if getattr(waypoint, "name", None)
        ]

    def _get_declared_time_gate_names(self) -> list[str]:
        """2.A2: the points the pilot declares a time for, the visible turn points and the finish point, in route order."""
        return [
            waypoint.name
            for waypoint in self.contestant.navigation_task.route.waypoints
            if getattr(waypoint, "name", None)
            and waypoint.type in (TURNPOINT, FINISHPOINT)
            and not getattr(waypoint, "on_curved_segment", False)
        ]

    def _interpolate_gate_times(self, gate_times: dict[str, str], declared: dict[str, datetime.datetime]) -> dict:
        """
        The times of the route's waypoints with the declared times as given and every other point between two known
        times (the declared points and the start point at its scheduled time) interpolated between them. The pilot
        flies each leg at a constant speed (2.A2), so a point on a leg is estimated at the same share of the time
        between the leg's ends as it has in the scheduled times, which follow the route (turns, wind): a pilot who
        declares the scheduled times gets the scheduled times of the hidden gates. Points after the last known time keep
        their scheduled times.
        """
        waypoints = [w for w in self.contestant.navigation_task.route.waypoints if w.name in gate_times]
        if not waypoints:
            return {}
        scheduled = {w.name: parser.parse(gate_times[w.name]) for w in waypoints}
        known = {waypoints[0].name: scheduled[waypoints[0].name], **declared}
        times = {}
        previous_known = None
        for index, waypoint in enumerate(waypoints):
            name = waypoint.name
            if name in known:
                times[name] = known[name]
                previous_known = name
                continue
            following = next((w.name for w in waypoints[index + 1 :] if w.name in known), None)
            if previous_known is None or following is None:
                continue
            scheduled_span = (scheduled[following] - scheduled[previous_known]).total_seconds()
            share = (scheduled[name] - scheduled[previous_known]).total_seconds() / scheduled_span if scheduled_span else 0
            # Whole seconds, like the scheduled times
            times[name] = round_time_second(known[previous_known] + (known[following] - known[previous_known]) * share)
        return times

    def _build_contract_navigation_effective_waypoints(self, compiled_task, declared_sequence: list) -> list[dict]:
        base_waypoints = self.contestant.navigation_task.route.waypoints
        if not base_waypoints:
            return []

        primitive_names = compiled_task.get_compiled_primitives().get("catalogue_turnpoint", [])
        editable_route = self.contestant.navigation_task.editable_route
        primitive_features = editable_route.get_catalogue_turnpoints() if editable_route else []
        primitive_by_name = {
            feature["properties"].get("name"): feature for feature in primitive_features if feature["properties"].get("name") in primitive_names
        }

        sp = base_waypoints[0]
        fp = base_waypoints[-1]
        reference = base_waypoints[min(1, len(base_waypoints) - 1)]

        effective_waypoints = [sp]
        for item in declared_sequence:
            if not isinstance(item, str) or item == "SP":
                continue
            if item == "FP":
                if effective_waypoints[-1].name != fp.name:
                    effective_waypoints.append(fp)
                continue
            if item == "MP":
                # Compatibility bridge: MP semantics currently live on the
                # shared three-point backbone, so contract-navigation payloads
                # synthesize the contestant-specific MP waypoint from the
                # reference route geometry instead of a dedicated authored
                # primitive.
                waypoint = build_waypoint(
                    "MP",
                    reference.latitude,
                    reference.longitude,
                    "tp",
                    reference.width,
                    True,
                    True,
                )
                waypoint.gate_line = [list(reference.gate_line[0]), list(reference.gate_line[1])] if reference.gate_line else []
                waypoint.elevation = getattr(reference, "elevation", 0)
                effective_waypoints.append(waypoint)
                continue
            feature = primitive_by_name.get(item)
            if feature:
                lon, lat = feature["geometry"]["coordinates"]
                # Declared catalogue turnpoints are route/gate checkpoints only.
                # Contract timing still belongs exclusively to SP, MP, and FP.
                waypoint = build_waypoint(item, lat, lon, "tp", reference.width, False, True)
                waypoint.gate_line = [list(reference.gate_line[0]), list(reference.gate_line[1])] if reference.gate_line else []
                waypoint.elevation = getattr(reference, "elevation", 0)
                effective_waypoints.append(waypoint)
        if effective_waypoints[-1].name != fp.name:
            effective_waypoints.append(fp)

        calculate_and_update_legs(effective_waypoints, self.contestant.navigation_task.route.use_procedure_turns)
        self._apply_effective_gate_lines(effective_waypoints)
        insert_gate_ranges(effective_waypoints)

        return [self._serialise_waypoint(waypoint) for waypoint in effective_waypoints]

    def _build_contract_navigation_time_model(self, declared_sequence: list, declared_t_seconds=None) -> dict:
        t_seconds = int(float(declared_t_seconds)) if declared_t_seconds not in (None, "") else 0
        before_mp = []
        after_mp = []
        seen_mp = False
        for item in declared_sequence:
            if item == "MP":
                seen_mp = True
                continue
            if item in ("FP", "SP"):
                continue
            if seen_mp:
                after_mp.append(item)
            else:
                before_mp.append(item)
        return {
            "t_seconds": t_seconds,
            "sp_offset_seconds": 0,
            "mp_offset_seconds": t_seconds,
            "fp_offset_seconds": 2 * t_seconds,
            "before_mp_sequence": before_mp,
            "after_mp_sequence": after_mp,
        }

    def _build_contract_navigation_declared_gate_times(self, compiled_effective_route_payload: dict) -> dict[str, str]:
        declared_sequence = compiled_effective_route_payload.get("declared_sequence", []) or []
        effective_waypoints = compiled_effective_route_payload.get("effective_waypoints", []) or []
        if not declared_sequence or not effective_waypoints:
            return {}

        # Same anchor as every other gate time: with adaptive start the midnight placeholder until the start is known
        base_time = self.contestant.gate_time_anchor()
        time_model = compiled_effective_route_payload.get("time_model") or {}
        t_seconds = int(time_model.get("t_seconds") or 0)
        if t_seconds <= 0:
            return {}

        by_name = {
            item.get("name"): item
            for item in effective_waypoints
            if isinstance(item, dict) and item.get("name")
        }
        before_names = [name for name in time_model.get("before_mp_sequence", []) if isinstance(name, str)]
        after_names = [name for name in time_model.get("after_mp_sequence", []) if isinstance(name, str)]

        def distance_for_leg(start_name: str, end_name: str, sequence: list[str]) -> float:
            names = [start_name, *sequence, end_name]
            distance = 0.0
            for current_name, next_name in zip(names, names[1:]):
                next_waypoint = by_name.get(next_name)
                if not next_waypoint:
                    continue
                distance += float(next_waypoint.get("distance_previous") or 0.0)
            return distance

        before_distance = distance_for_leg("SP", "MP", before_names)
        after_distance = distance_for_leg("MP", "FP", after_names)

        def build_segment_times(sequence: list[str], end_name: str, start_time: datetime.datetime, segment_seconds: float, segment_distance: float) -> dict[str, str]:
            times: dict[str, str] = {}
            current_time = start_time
            names = [*sequence, end_name]
            for next_name in names:
                next_waypoint = by_name.get(next_name)
                if not next_waypoint:
                    continue
                leg_distance = float(next_waypoint.get("distance_previous") or 0.0)
                leg_seconds = segment_seconds * leg_distance / segment_distance if segment_distance > 0 and leg_distance > 0 else 0.0
                current_time = current_time + datetime.timedelta(seconds=leg_seconds)
                times[next_name] = current_time.isoformat()
            return times

        gate_times = {"SP": base_time.isoformat()}
        gate_times.update(build_segment_times(before_names, "MP", base_time, float(t_seconds), before_distance))
        mp_gate_time = gate_times.get("MP")
        if mp_gate_time is None:
            # No "MP" in effective_waypoints - normally impossible (effective waypoints are
            # synthesized to always include it), but the REST API path lets a client post
            # declared_sequence directly, skipping that synthesis. Return what we have instead
            # of KeyError-ing here: _validate_declaration (ContractNavigationStrategy, which
            # requires exactly one "MP" in declared_sequence) runs right after this and turns
            # the real problem into a proper validation error instead of a 500.
            return gate_times
        mp_time = datetime.datetime.fromisoformat(mp_gate_time)
        gate_times.update(build_segment_times(after_names, "FP", mp_time, float(t_seconds), after_distance))
        return gate_times

    def _build_turnpoint_hunt_declared_gate_times(self, compiled_effective_route_payload: dict, declaration_payload: dict) -> dict[str, str]:
        gate_times: dict[str, str] = {}
        compulsory_point_times = compiled_effective_route_payload.get("compulsory_point_times") or declaration_payload.get("compulsory_point_times") or {}
        for key, value in compulsory_point_times.items():
            if isinstance(value, str):
                gate_times[key] = parser.parse(value).isoformat()

        declared_sequence = [item for item in (compiled_effective_route_payload.get("declared_sequence") or []) if isinstance(item, str)]
        effective_waypoints = compiled_effective_route_payload.get("effective_waypoints") or []
        if not declared_sequence or not effective_waypoints:
            return gate_times

        by_name = {
            item.get("name"): item
            for item in effective_waypoints
            if isinstance(item, dict) and item.get("name")
        }
        compulsory_point_names = [name for name in (compiled_effective_route_payload.get("compulsory_point_names") or []) if isinstance(name, str)]
        ordered_compulsory_names = self._get_turnpoint_hunt_ordered_compulsory_point_names(compulsory_point_times, compulsory_point_names)
        if len(ordered_compulsory_names) != 3:
            return gate_times

        first_compulsory, middle_compulsory, last_compulsory = ordered_compulsory_names
        compulsory_indices = {name: index for index, name in enumerate(declared_sequence) if name in ordered_compulsory_names}
        if any(name not in compulsory_indices for name in ordered_compulsory_names):
            return gate_times
        if not (compulsory_indices[first_compulsory] < compulsory_indices[middle_compulsory] < compulsory_indices[last_compulsory]):
            return gate_times

        before_names = declared_sequence[: compulsory_indices[middle_compulsory]]
        between_names = declared_sequence[compulsory_indices[middle_compulsory] + 1 : compulsory_indices[last_compulsory]]
        before_names = [name for name in before_names if name not in ordered_compulsory_names]
        between_names = [name for name in between_names if name not in ordered_compulsory_names]
        first_time_raw = compulsory_point_times.get(first_compulsory)
        middle_time_raw = compulsory_point_times.get(middle_compulsory)
        last_time_raw = compulsory_point_times.get(last_compulsory)
        if not all(isinstance(value, str) for value in (first_time_raw, middle_time_raw, last_time_raw)):
            return gate_times

        first_time = parser.parse(first_time_raw)
        middle_time = parser.parse(middle_time_raw)
        last_time = parser.parse(last_time_raw)

        def distance_for_leg(start_name: str, end_name: str, sequence: list[str]) -> float:
            names = [start_name, *sequence, end_name]
            distance = 0.0
            for current_name, next_name in zip(names, names[1:]):
                next_waypoint = by_name.get(next_name)
                if not next_waypoint:
                    continue
                distance += float(next_waypoint.get("distance_previous") or 0.0)
            return distance

        before_distance = distance_for_leg(first_compulsory, middle_compulsory, before_names)
        after_distance = distance_for_leg(middle_compulsory, last_compulsory, between_names)

        def build_segment_times(sequence: list[str], end_name: str, start_time: datetime.datetime, end_time: datetime.datetime, segment_distance: float) -> None:
            current_time = start_time
            total_seconds = (end_time - start_time).total_seconds()
            names = [*sequence, end_name]
            for next_name in names:
                next_waypoint = by_name.get(next_name)
                if not next_waypoint:
                    continue
                leg_distance = float(next_waypoint.get("distance_previous") or 0.0)
                leg_seconds = total_seconds * leg_distance / segment_distance if segment_distance > 0 and leg_distance > 0 else 0.0
                current_time = current_time + datetime.timedelta(seconds=leg_seconds)
                if next_name not in gate_times:
                    gate_times[next_name] = current_time.isoformat()

        build_segment_times(before_names, middle_compulsory, first_time, middle_time, before_distance)
        build_segment_times(between_names, last_compulsory, middle_time, last_time, after_distance)
        return gate_times

    def _build_turnpoint_hunt_compulsory_targets_payload(self) -> list[dict]:
        # 2.A6/2.B2 have no route backbone: the three compulsory (timed)
        # points are standalone known_time_gate markers. This mirrors
        # _build_turnpoint_hunt_targets_payload's shape for the free
        # catalogue targets.
        editable_route = self.contestant.navigation_task.editable_route
        if editable_route is None:
            return []
        targets = []
        for item in editable_route.get_known_time_gates():
            properties = item.get("properties", {})
            name = properties.get("name")
            if not name:
                continue
            targets.append(
                {
                    "name": name,
                    "coordinates": item.get("geometry", {}).get("coordinates", []),
                    "width": properties.get("width") or 1852,
                }
            )
        return targets

    def _build_turnpoint_hunt_compulsory_waypoints(self, compulsory_point_names: list[str]) -> list:
        targets_by_name = {item["name"]: item for item in self._build_turnpoint_hunt_compulsory_targets_payload()}
        waypoints = []
        for name in compulsory_point_names:
            target = targets_by_name.get(name)
            if not target:
                continue
            coordinates = target.get("coordinates") or []
            if len(coordinates) != 2:
                continue
            lon, lat = coordinates
            width_nm = float(target.get("width") or 1852) / 1852
            # gate_line is fully recomputed for every waypoint in this list
            # by _apply_effective_gate_lines below, so a placeholder here is
            # fine - these points have no natural flight-leg direction of
            # their own (no backbone), so that shared recomputation (based
            # on neighboring points in the eventual ordered sequence) is the
            # only sensible source of a well-formed crossing line.
            waypoints.append(build_waypoint(name, lat, lon, "tp", width_nm, True, True))
        return waypoints

    def _build_turnpoint_hunt_effective_waypoints(self, compiled_task, compulsory_point_names: list[str], declaration_payload: dict | None = None) -> list[dict]:
        effective_waypoints = self._build_turnpoint_hunt_compulsory_waypoints(compulsory_point_names)
        if not effective_waypoints:
            return []

        compulsory_point_times = self._get_turnpoint_hunt_compulsory_point_times(declaration_payload or {})
        ordered_compulsory_names = self._get_turnpoint_hunt_ordered_compulsory_point_names(compulsory_point_times, compulsory_point_names)
        declared_sequence = [item for item in ((declaration_payload or {}).get("declared_sequence") or []) if isinstance(item, str)]
        if declared_sequence:
            route_waypoint_names = {waypoint.name for waypoint in effective_waypoints if getattr(waypoint, "name", None)}
            route_waypoints_by_name = {waypoint.name: waypoint for waypoint in effective_waypoints if getattr(waypoint, "name", None)}
            known_time_gate_names = [name for name in compiled_task.get_compiled_primitives().get("known_time_gate", []) if isinstance(name, str)]
            free_target_names = [
                item for item in declared_sequence
                if item not in route_waypoint_names and item not in known_time_gate_names
            ]
            ordered_waypoints = []
            target_payload = {item["name"]: item for item in self._build_turnpoint_hunt_targets_payload()}
            reference_waypoint = effective_waypoints[1] if len(effective_waypoints) > 1 else effective_waypoints[0]
            seen_names = set()
            for item in declared_sequence:
                if item in seen_names:
                    continue
                seen_names.add(item)
                # A compulsory (timed) point still needs its own real Gate - create_gates()
                # (gate_calculator.py) builds calculator.gates EXCLUSIVELY from this method's
                # output (via get_effective_route_waypoints), so skipping it here entirely (as
                # this branch used to) meant a compulsory gate the contestant correctly declared
                # and validation required them to include - see validate_declaration's
                # "declared_sequence must include each compulsory point exactly once" - could
                # never actually be scored: no Gate object, no on_gate_passed event, no
                # _score_turnpoint_hunt_compulsory_timing call, ever. route_waypoints_by_name
                # already holds the real compulsory waypoint (see comment on that dict above),
                # so just place it at its declared position like any other waypoint instead of
                # dropping it.
                if item in known_time_gate_names:
                    if item in route_waypoints_by_name:
                        ordered_waypoints.append(route_waypoints_by_name[item])
                    continue
                if item in route_waypoints_by_name:
                    ordered_waypoints.append(route_waypoints_by_name[item])
                    continue
                target = target_payload.get(item)
                if not target:
                    continue
                coordinates = target.get("coordinates") or []
                if len(coordinates) != 2:
                    continue
                lon, lat = coordinates
                waypoint = build_waypoint(item, lat, lon, "tp", reference_waypoint.width, False, True)
                waypoint.gate_line = [list(reference_waypoint.gate_line[0]), list(reference_waypoint.gate_line[1])] if reference_waypoint.gate_line else []
                waypoint.elevation = getattr(reference_waypoint, "elevation", 0)
                ordered_waypoints.append(waypoint)
            if ordered_waypoints:
                effective_waypoints = ordered_waypoints
            elif ordered_compulsory_names:
                effective_waypoints = [route_waypoints_by_name[name] for name in ordered_compulsory_names if name in route_waypoints_by_name]
        else:
            free_target_names = []
        if free_target_names and not declared_sequence:
            target_payload = {item["name"]: item for item in self._build_turnpoint_hunt_targets_payload()}
            reference_waypoint = effective_waypoints[1] if len(effective_waypoints) > 1 else effective_waypoints[0]
            seen_free_targets = set()
            for target_name in free_target_names:
                if target_name in seen_free_targets:
                    continue
                seen_free_targets.add(target_name)
                target = target_payload.get(target_name)
                if not target:
                    continue
                coordinates = target.get("coordinates") or []
                if len(coordinates) != 2:
                    continue
                lon, lat = coordinates
                waypoint = build_waypoint(target_name, lat, lon, "tp", reference_waypoint.width, False, True)
                waypoint.gate_line = [list(reference_waypoint.gate_line[0]), list(reference_waypoint.gate_line[1])] if reference_waypoint.gate_line else []
                waypoint.elevation = getattr(reference_waypoint, "elevation", 0)
                effective_waypoints.append(waypoint)
        if effective_waypoints and stored_task_type(self.contestant.navigation_task).free_order_gate_matching:
            # 2.B2: every target flown scores, whether or not the declared sequence names it, so every target is a gate.
            present = {waypoint.name for waypoint in effective_waypoints}
            reference_waypoint = effective_waypoints[1] if len(effective_waypoints) > 1 else effective_waypoints[0]
            for target in self._build_turnpoint_hunt_targets_payload():
                coordinates = target.get("coordinates") or []
                if target["name"] in present or len(coordinates) != 2:
                    continue
                lon, lat = coordinates
                # A target on top of a gate has no leg to draw its crossing line from (and cannot be told apart from
                # that gate by a crossing anyway): the gate already there is the one that is crossed.
                if any(abs(waypoint.latitude - lat) < 1e-6 and abs(waypoint.longitude - lon) < 1e-6 for waypoint in effective_waypoints):
                    continue
                present.add(target["name"])
                waypoint = build_waypoint(target["name"], lat, lon, "tp", reference_waypoint.width, False, True)
                waypoint.gate_line = [list(reference_waypoint.gate_line[0]), list(reference_waypoint.gate_line[1])] if reference_waypoint.gate_line else []
                waypoint.elevation = getattr(reference_waypoint, "elevation", 0)
                effective_waypoints.append(waypoint)
        if not effective_waypoints:
            return []
        if len(effective_waypoints) == 1:
            return [self._serialise_waypoint(effective_waypoints[0])]

        calculate_and_update_legs(effective_waypoints, self.contestant.navigation_task.route.use_procedure_turns)
        self._apply_effective_gate_lines(effective_waypoints)
        insert_gate_ranges(effective_waypoints)

        return [self._serialise_waypoint(waypoint) for waypoint in effective_waypoints]

    def _serialise_waypoint(self, waypoint) -> dict:
        return {
            "name": waypoint.name,
            "latitude": waypoint.latitude,
            "longitude": waypoint.longitude,
            "type": waypoint.type,
            "width": waypoint.width,
            "gate_line": waypoint.gate_line,
            "time_check": waypoint.time_check,
            "gate_check": waypoint.gate_check,
            "distance_next": waypoint.distance_next,
            "distance_previous": waypoint.distance_previous,
            "bearing_next": waypoint.bearing_next,
            "bearing_from_previous": waypoint.bearing_from_previous,
            "procedure_turn_points": waypoint.procedure_turn_points,
            "inside_distance": waypoint.inside_distance,
            "outside_distance": waypoint.outside_distance,
            "is_procedure_turn": waypoint.is_procedure_turn,
            "is_steep_turn": waypoint.is_steep_turn,
            "end_curved": waypoint.end_curved,
            "elevation": waypoint.elevation,
        }

    def _apply_effective_gate_lines(self, effective_waypoints) -> None:
        if len(effective_waypoints) < 2:
            return

        for index, waypoint in enumerate(effective_waypoints):
            width_nm = getattr(waypoint, "width", 0.1)
            if index == 0:
                next_waypoint = effective_waypoints[index + 1]
                line = create_perpendicular_line_at_end_lonlat(
                    next_waypoint.longitude,
                    next_waypoint.latitude,
                    waypoint.longitude,
                    waypoint.latitude,
                    width_nm * 1852,
                )
                line[0].reverse()
                line[1].reverse()
                line.reverse()
                waypoint.gate_line = line
                continue

            waypoint.gate_line = create_perpendicular_line_at_end_gates(
                effective_waypoints[index - 1],
                waypoint,
                width_nm,
            )

        correct_gate_directions_to_the_right(effective_waypoints)

    def _build_gate_times_payload(self, declaration_payload: dict, compiled_task, compiled_effective_route_payload: dict) -> dict[str, str]:
        # calculate_missing_gate_times({}) anchors an adaptive-start contestant's times on the
        # real starting-line crossing once it has one (see Contestant._actual_starting_line_crossing_time),
        # instead of always reproducing the midnight-anchored placeholder - otherwise any later
        # compile() call (e.g. the compiled_evidence endpoint, or a declaration PATCH) would
        # overwrite the already-correct absolute times back to that placeholder.
        gate_times = {
            key: value.isoformat() for key, value in self.contestant.calculate_missing_gate_times({}).items()
        }
        # Subtype strategies may add synthesized declaration times here as a
        # compatibility bridge for the existing gate-based calculators. Keeping
        # that synthesis in the compiler prevents downstream consumers from
        # re-deriving slightly different timing assumptions.
        return self._get_strategy().update_gate_times(
            gate_times,
            declaration_payload,
            compiled_task,
            compiled_effective_route_payload,
        )

    def _lock_if_needed(self, config: ContestantTaskConfiguration) -> None:
        # Once a contestant has a real compiled declaration, the scheduler must not silently
        # re-time them (schedule_contestants.py excludes schedule_locked contestants) - doing so
        # would invalidate gate times/timing the declaration already committed to. An invalid
        # config isn't a real declaration yet, so leave scheduling eligibility open until it is.
        #
        # Task types that don't require a contestant-specific declaration at all (the majority -
        # everything except contract navigation/turnpoint hunt/etc.) have no "real declaration" to
        # protect: config.is_valid is trivially True with zero validation errors regardless of
        # what, if anything, was ever declared. Without this guard, every contestant on those
        # tasks got auto-locked the instant compile() ran for them - including from the scheduler
        # creating them in the first place, which defeated the organizer's ability to freely
        # re-run it and adjust the schedule afterward.
        if not self.contestant.navigation_task.requires_contestant_task_configuration():
            return
        # Some subtypes that DO require configuration still have an optional declaration (known
        # circuit's turnpoint_time_overrides, limited fuel turnpoint hunt's compulsory_point_times
        # - see their strategies' validate_declaration) - is_valid is trivially True for these too
        # when nothing was declared, for the same reason as above. Requiring a non-empty payload
        # as well means those contestants stay open to bulk rescheduling until they actually
        # commit to something.
        if not config.is_valid or not config.declaration_payload or self.contestant.schedule_locked:
            return
        self.contestant.schedule_locked = True
        self.contestant.save(update_fields=["schedule_locked"])

    def build_declaration_payload_from_input(self, declaration_input: dict | None = None) -> dict:
        declaration_input = declaration_input or {}
        return self._get_strategy().build_declaration_payload_from_input(declaration_input)
