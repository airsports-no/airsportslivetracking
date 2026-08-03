import datetime

from dateutil import parser
from rest_framework import serializers

from display.models import ContestantTaskConfiguration
from display.services.task_compiler import TaskCompiler
from display.utilities.cima_task_type_definitions import (
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    DURATION,
    KNOWN_CIRCUIT,
    LIMITED_FUEL_TURNPOINT_HUNT,
    PRECISION_NAVIGATION,
    TURNPOINT_HUNT,
    UNKNOWN_LEGS,
)
from display.utilities.route_building_utilities import (
    build_waypoint,
    calculate_and_update_legs,
    correct_gate_directions_to_the_right,
    create_perpendicular_line_at_end_gates,
    create_perpendicular_line_at_end_lonlat,
    insert_gate_ranges,
)


class ContestantTaskCompilerStrategy:
    def __init__(self, compiler: "ContestantTaskCompiler"):
        self.compiler = compiler

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
    def __init__(self, compiler: "ContestantTaskCompiler", subtype: str):
        super().__init__(compiler)
        self.subtype = subtype

    def validate_declaration(self, declaration_payload: dict, compiled_task) -> list[str]:
        predictions = declaration_payload.get("known_time_gate_predictions")
        errors = []
        if not isinstance(predictions, dict) or len(predictions) == 0:
            if self.subtype == CURVE_NAVIGATION_TIME_ESTIMATION:
                errors.append("Curve navigation requires known_time_gate_predictions.")
            else:
                errors.append("Precision navigation requires known_time_gate_predictions.")
            return errors

        if self.subtype == CURVE_NAVIGATION_TIME_ESTIMATION:
            tmax_seconds = int((self.compiler.contestant.navigation_task.task_config or {}).get("curve_navigation_tmax_seconds") or 0)
            fp_prediction = predictions.get("FP")
            if tmax_seconds > 0 and isinstance(fp_prediction, str):
                fp_time = parser.parse(fp_prediction)
                sp_time = self.compiler.contestant.takeoff_time + datetime.timedelta(minutes=self.compiler.contestant.minutes_to_starting_point)
                if (fp_time - sp_time).total_seconds() > tmax_seconds:
                    errors.append("Curve navigation declarations may not exceed Tmax.")
            return errors

        required_names = self.compiler._get_precision_navigation_prediction_names()
        missing = [name for name in required_names if name not in predictions]
        unexpected = sorted(set(predictions.keys()) - set(required_names))
        if missing:
            errors.append(f"Missing precision navigation predictions for: {', '.join(missing)}")
        if unexpected:
            errors.append(f"Unknown precision navigation prediction(s): {', '.join(unexpected)}")
        return errors

    def build_effective_route_payload(self, compiled_task, declaration_payload: dict) -> dict:
        if self.subtype != PRECISION_NAVIGATION:
            return {}
        return {
            "known_time_gate_predictions": declaration_payload.get("known_time_gate_predictions", {}),
            "expected_prediction_names": self.compiler._get_precision_navigation_prediction_names(),
        }

    def update_gate_times(self, gate_times: dict[str, str], declaration_payload: dict, compiled_task, compiled_effective_route_payload: dict) -> dict[str, str]:
        predictions = declaration_payload.get("known_time_gate_predictions", {})
        for key, value in predictions.items():
            if isinstance(value, str):
                gate_times[key] = parser.parse(value).isoformat()
        if self.subtype != PRECISION_NAVIGATION:
            return gate_times
        expected_names = set(self.compiler._get_precision_navigation_prediction_names())
        return {key: value for key, value in gate_times.items() if key in expected_names}

    def build_declaration_payload_from_input(self, declaration_input: dict) -> dict:
        predictions = declaration_input.get("known_time_gate_predictions")
        if predictions is None:
            predictions = declaration_input.get("known_time_gate_prediction")
        if not predictions:
            return {}
        if not isinstance(predictions, dict):
            raise serializers.ValidationError({"known_time_gate_predictions": "Expected a dictionary of gate predictions."})
        normalized_predictions = {}
        for key, value in predictions.items():
            if value in (None, ""):
                continue
            if isinstance(value, str):
                normalized_predictions[key] = parser.parse(value).isoformat()
            elif isinstance(value, datetime.datetime):
                normalized_predictions[key] = value.isoformat()
            else:
                raise serializers.ValidationError({"known_time_gate_predictions": f"Invalid prediction value for {key}."})
        return {"known_time_gate_predictions": normalized_predictions} if normalized_predictions else {}


class ContractNavigationStrategy(ContestantTaskCompilerStrategy):
    def validate_declaration(self, declaration_payload: dict, compiled_task) -> list[str]:
        errors = []
        declared_sequence = declaration_payload.get("declared_sequence")
        if not isinstance(declared_sequence, list) or len(declared_sequence) == 0:
            errors.append("Contract navigation requires declared_sequence.")
        else:
            catalogue_names = set(compiled_task.get_compiled_primitives().get("catalogue_turnpoint", []))
            mandatory_names = {"SP", "MP", "FP"}
            for item in declared_sequence:
                if item not in catalogue_names and item not in mandatory_names:
                    errors.append(f"Unknown declared sequence item: {item}")
            if declared_sequence.count("MP") != 1:
                errors.append("Contract navigation requires exactly one MP in declared_sequence.")
            if declared_sequence.count("FP") != 1:
                errors.append("Contract navigation requires exactly one FP in declared_sequence.")
            if declared_sequence[-1] != "FP":
                errors.append("Contract navigation requires FP to be the last declared sequence item.")

        declared_t_seconds = declaration_payload.get("declared_t_seconds")
        if declared_t_seconds in (None, ""):
            errors.append("Contract navigation requires declared_t_seconds.")
        else:
            try:
                if float(declared_t_seconds) <= 0:
                    errors.append("Contract navigation declared_t_seconds must be greater than zero.")
            except (TypeError, ValueError):
                errors.append("Contract navigation declared_t_seconds must be numeric.")
        return errors

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
        minimum_required = 0 if self.compiler.contestant.navigation_task.task_subtype == LIMITED_FUEL_TURNPOINT_HUNT else 3
        if not isinstance(compulsory_point_times, dict):
            errors.append("Turnpoint hunt requires exactly three compulsory point times.")
        else:
            expected_names = set(compulsory_point_names)
            provided_names = set(compulsory_point_times.keys())
            unexpected = sorted(provided_names - expected_names)
            missing = [name for name in compulsory_point_names if name not in compulsory_point_times]
            if unexpected:
                errors.append(f"Unknown compulsory point time(s): {', '.join(unexpected)}")
            if minimum_required > 0 and missing:
                errors.append(f"Missing compulsory point time(s): {', '.join(missing)}")
            if minimum_required > 0 and len(provided_names) != len(expected_names):
                errors.append("Turnpoint hunt requires exactly three compulsory point times.")
        if declared_sequence:
            if not isinstance(declared_sequence, list):
                errors.append("Turnpoint hunt declared_sequence must be a list.")
            else:
                normalized_sequence = [item for item in declared_sequence if isinstance(item, str)]
                allowed_compulsory_names = set(compulsory_point_names)
                unknown = [item for item in normalized_sequence if item not in expected_free_targets and item not in allowed_compulsory_names]
                if unknown:
                    errors.append(f"Unknown turnpoint hunt target(s): {', '.join(unknown)}")
                duplicates = sorted({item for item in normalized_sequence if normalized_sequence.count(item) > 1})
                if duplicates:
                    errors.append(f"Duplicate turnpoint hunt target(s): {', '.join(duplicates)}")
                compulsory_sequence = [item for item in normalized_sequence if item in allowed_compulsory_names]
                if sorted(compulsory_sequence) != sorted(compulsory_point_names):
                    errors.append("Turnpoint hunt declared_sequence must include each compulsory point exactly once.")
                else:
                    ordered_compulsory_names = self.compiler._get_turnpoint_hunt_ordered_compulsory_point_names(compulsory_point_times, compulsory_point_names)
                    if compulsory_sequence != ordered_compulsory_names:
                        errors.append("Turnpoint hunt compulsory points must appear in predicted-time order.")
        fuel_metadata = declaration_payload.get("fuel_metadata") or {}
        if fuel_metadata and not isinstance(fuel_metadata, dict):
            errors.append("Fuel metadata must be a dictionary.")
        return errors

    def build_effective_route_payload(self, compiled_task, declaration_payload: dict) -> dict:
        compulsory_point_names = self.compiler._get_turnpoint_hunt_compulsory_point_names(compiled_task)
        compulsory_point_times = self.compiler._get_turnpoint_hunt_compulsory_point_times(declaration_payload)
        effective_waypoints = self.compiler._build_turnpoint_hunt_effective_waypoints(compiled_task, compulsory_point_names, declaration_payload)
        free_targets = self.compiler._build_turnpoint_hunt_targets_payload()
        declared_sequence = declaration_payload.get("declared_sequence", [])
        effective_waypoint_names = [item["name"] for item in effective_waypoints]
        compulsory_timing_gate_names = effective_waypoint_names[: len(compulsory_point_names)]
        payload = {
            "compulsory_point_names": compulsory_point_names,
            "compulsory_point_times": compulsory_point_times,
            "declared_sequence": declared_sequence,
            "effective_waypoint_names": effective_waypoint_names,
            "effective_waypoints": effective_waypoints,
            "compulsory_timing_gate_names": compulsory_timing_gate_names,
            "compulsory_timing_tolerance_seconds": int(
                getattr(self.compiler.contestant.navigation_task.scorecard, "compulsory_timing_tolerance_seconds", 10) or 10
            ),
            "free_targets": free_targets,
            "free_target_names": [item["name"] for item in free_targets],
            "free_target_evidence": {
                item["name"]: [evidence["name"] for evidence in item.get("evidence", [])]
                for item in free_targets
            },
            "observation_photos": self.compiler._build_turnpoint_hunt_observation_photos(free_targets),
            "scored_target_values": self.compiler._build_turnpoint_hunt_scored_target_values(free_targets),
        }
        maximum_task_duration_minutes = getattr(
            self.compiler.contestant.navigation_task.scorecard,
            "maximum_task_duration_minutes",
            None,
        )
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
        return gate_times

    def build_declaration_payload_from_input(self, declaration_input: dict) -> dict:
        compulsory_point_times = declaration_input.get("compulsory_point_times")
        if compulsory_point_times is None:
            compulsory_point_times = declaration_input.get("predicted_gate_times") or {}
        fuel_metadata = declaration_input.get("fuel_metadata") or {}
        if not isinstance(compulsory_point_times, dict):
            raise serializers.ValidationError({"compulsory_point_times": "Expected a dictionary of compulsory point times."})
        if not isinstance(fuel_metadata, dict):
            raise serializers.ValidationError({"fuel_metadata": "Expected a dictionary of fuel metadata."})
        declared_sequence = declaration_input.get("declared_sequence") or declaration_input.get("predicted_sequence") or []
        if declared_sequence and not isinstance(declared_sequence, list):
            raise serializers.ValidationError({"declared_sequence": "Expected a list of declared turnpoints."})
        normalized_point_times = {}
        for key, value in compulsory_point_times.items():
            if value in (None, ""):
                continue
            if isinstance(value, str):
                normalized_point_times[key] = parser.parse(value).isoformat()
            elif isinstance(value, datetime.datetime):
                normalized_point_times[key] = value.isoformat()
            else:
                raise serializers.ValidationError({"compulsory_point_times": f"Invalid prediction value for {key}."})
        normalized_sequence = [item for item in declared_sequence if isinstance(item, str) and item]
        payload = {}
        if normalized_point_times:
            payload["compulsory_point_times"] = normalized_point_times
        if normalized_sequence:
            payload["declared_sequence"] = normalized_sequence
        if fuel_metadata:
            payload["fuel_metadata"] = fuel_metadata
        return payload

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


class ObservationEvidenceStrategy(ContestantTaskCompilerStrategy):
    def build_effective_route_payload(self, compiled_task, declaration_payload: dict) -> dict:
        return self.compiler._build_observation_evidence_payload(compiled_task)


class ContestantTaskCompiler:
    def __init__(self, contestant):
        self.contestant = contestant

    def _get_strategy(self) -> ContestantTaskCompilerStrategy:
        subtype = self.contestant.navigation_task.task_subtype
        if subtype in (CURVE_NAVIGATION_TIME_ESTIMATION, PRECISION_NAVIGATION):
            return CurveOrPrecisionNavigationStrategy(self, subtype)
        if subtype == CONTRACT_NAVIGATION_TIME_CONTROLS:
            return ContractNavigationStrategy(self)
        if subtype in (TURNPOINT_HUNT, LIMITED_FUEL_TURNPOINT_HUNT):
            return TurnpointHuntStrategy(self)
        if subtype == DURATION:
            return DurationStrategy(self)
        if subtype in (KNOWN_CIRCUIT, UNKNOWN_LEGS):
            return ObservationEvidenceStrategy(self)
        return ContestantTaskCompilerStrategy(self)

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
            "expected_prediction_names": self._get_precision_navigation_prediction_names(),
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
            "compulsory_timing_tolerance_seconds": int(
                getattr(self.contestant.navigation_task.scorecard, "compulsory_timing_tolerance_seconds", 10) or 10
            ),
            "free_targets": free_targets,
            "free_target_names": [item["name"] for item in free_targets],
            "free_target_evidence": {
                item["name"]: [evidence["name"] for evidence in item.get("evidence", [])]
                for item in free_targets
            },
            "observation_photos": self._build_turnpoint_hunt_observation_photos(free_targets),
            "scored_target_values": self._build_turnpoint_hunt_scored_target_values(free_targets),
        }
        maximum_task_duration_minutes = getattr(
            self.contestant.navigation_task.scorecard,
            "maximum_task_duration_minutes",
            None,
        )
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
        if getattr(self.contestant.navigation_task.scorecard, "duration_normalization_policy", ""):
            duration_review["duration_normalization_policy"] = self.contestant.navigation_task.scorecard.duration_normalization_policy
        task_config = self.contestant.navigation_task.task_config or {}
        editable_route = self.contestant.navigation_task.editable_route
        if editable_route is not None:
            duration_polygons = editable_route.get_duration_landing_area_polygons()
            if duration_polygons:
                polygon = duration_polygons[0].get("geometry", {}).get("coordinates", [[]])[0]
                if len(polygon) > 1 and polygon[0] == polygon[-1]:
                    polygon = polygon[:-1]
                duration_review["duration_landing_area_polygon"] = polygon
        if task_config.get("duration_residual_fuel_required") or getattr(
            self.contestant.navigation_task.scorecard,
            "duration_residual_fuel_required",
            False,
        ):
            duration_review["duration_residual_fuel_required"] = True
        return {"duration_review": duration_review} if duration_review else {}

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

        base_time = self.contestant.takeoff_time + datetime.timedelta(minutes=self.contestant.minutes_to_starting_point)
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
        mp_time = datetime.datetime.fromisoformat(gate_times["MP"])
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

    def _build_turnpoint_hunt_effective_waypoints(self, compiled_task, compulsory_point_names: list[str], declaration_payload: dict | None = None) -> list[dict]:
        base_waypoints = self.contestant.navigation_task.route.waypoints
        if not base_waypoints:
            return []

        compulsory_point_times = self._get_turnpoint_hunt_compulsory_point_times(declaration_payload or {})
        ordered_compulsory_names = self._get_turnpoint_hunt_ordered_compulsory_point_names(compulsory_point_times, compulsory_point_names)
        compulsory_backbone_count = len(compulsory_point_names) if compulsory_point_names else 3
        effective_waypoints = list(base_waypoints[:compulsory_backbone_count])
        declared_sequence = [item for item in ((declaration_payload or {}).get("declared_sequence") or []) if isinstance(item, str)]
        if declared_sequence:
            route_waypoint_names = {waypoint.name for waypoint in effective_waypoints if getattr(waypoint, "name", None)}
            route_waypoints_by_name = {waypoint.name: waypoint for waypoint in effective_waypoints if getattr(waypoint, "name", None)}
            filtered_sequence = [item for item in declared_sequence if item in route_waypoint_names]
            free_target_names = [item for item in declared_sequence if item not in route_waypoint_names]
            ordered_waypoints = []
            target_payload = {item["name"]: item for item in self._build_turnpoint_hunt_targets_payload()}
            reference_waypoint = effective_waypoints[1] if len(effective_waypoints) > 1 else effective_waypoints[0]
            seen_names = set()
            for item in filtered_sequence:
                if item in seen_names:
                    continue
                seen_names.add(item)
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
        if self.contestant.tracker_start_time <= self.contestant.takeoff_time:
            return
        self.contestant.schedule_locked = True
        self.contestant.save(update_fields=["schedule_locked"])

    def build_declaration_payload_from_input(self, declaration_input: dict | None = None) -> dict:
        declaration_input = declaration_input or {}
        return self._get_strategy().build_declaration_payload_from_input(declaration_input)
