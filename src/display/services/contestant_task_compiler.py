import datetime

from dateutil import parser
from rest_framework import serializers

from display.models import ContestantTaskConfiguration
from display.services.task_compiler import TaskCompiler
from display.utilities.cima_task_type_definitions import (
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    KNOWN_CIRCUIT,
    LIMITED_FUEL_TURNPOINT_HUNT,
    PRECISION_NAVIGATION,
    TURNPOINT_HUNT,
    UNKNOWN_LEGS,
)
from display.utilities.route_building_utilities import build_waypoint, calculate_and_update_legs, insert_gate_ranges


class ContestantTaskCompiler:
    def __init__(self, contestant):
        self.contestant = contestant

    def compile(self, declaration_payload: dict | None = None, force: bool = False) -> ContestantTaskConfiguration:
        declaration_payload = declaration_payload or {}
        compiled_task = TaskCompiler(self.contestant.navigation_task).compile()
        compiled_gate_times_payload = self._build_gate_times_payload(declaration_payload)
        compiled_effective_route_payload = self._build_effective_route_payload(compiled_task, declaration_payload)
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
        if force or config.declaration_payload != declaration_payload:
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

        subtype = self.contestant.navigation_task.task_subtype
        errors = []
        if subtype == CURVE_NAVIGATION_TIME_ESTIMATION:
            predictions = declaration_payload.get("known_time_gate_predictions")
            if not isinstance(predictions, dict) or len(predictions) == 0:
                errors.append("Curve navigation requires known_time_gate_predictions.")
            else:
                tmax_seconds = int((self.contestant.navigation_task.task_config or {}).get("curve_navigation_tmax_seconds") or 0)
                fp_prediction = predictions.get("FP")
                if tmax_seconds > 0 and isinstance(fp_prediction, str):
                    fp_time = parser.parse(fp_prediction)
                    sp_time = self.contestant.takeoff_time + datetime.timedelta(minutes=self.contestant.minutes_to_starting_point)
                    if (fp_time - sp_time).total_seconds() > tmax_seconds:
                        errors.append("Curve navigation declarations may not exceed Tmax.")
        elif subtype == PRECISION_NAVIGATION:
            predictions = declaration_payload.get("known_time_gate_predictions")
            if not isinstance(predictions, dict) or len(predictions) == 0:
                errors.append("Precision navigation requires known_time_gate_predictions.")
            else:
                required_names = self._get_precision_navigation_prediction_names()
                missing = [name for name in required_names if name not in predictions]
                unexpected = sorted(set(predictions.keys()) - set(required_names))
                if missing:
                    errors.append(f"Missing precision navigation predictions for: {', '.join(missing)}")
                if unexpected:
                    errors.append(f"Unknown precision navigation prediction(s): {', '.join(unexpected)}")
        elif subtype in (TURNPOINT_HUNT, LIMITED_FUEL_TURNPOINT_HUNT):
            compulsory_point_names = self._get_turnpoint_hunt_compulsory_point_names(compiled_task)
            compulsory_point_times = self._get_turnpoint_hunt_compulsory_point_times(declaration_payload)
            if not isinstance(compulsory_point_times, dict) or len(compulsory_point_times) != 3:
                errors.append("Turnpoint hunt requires exactly three compulsory point times.")
            else:
                unexpected = sorted(set(compulsory_point_times.keys()) - set(compulsory_point_names))
                missing = [name for name in compulsory_point_names if name not in compulsory_point_times]
                if unexpected:
                    errors.append(f"Unknown compulsory point time(s): {', '.join(unexpected)}")
                if missing:
                    errors.append(f"Missing compulsory point time(s): {', '.join(missing)}")
            fuel_metadata = declaration_payload.get("fuel_metadata") or {}
            if fuel_metadata and not isinstance(fuel_metadata, dict):
                errors.append("Fuel metadata must be a dictionary.")
        elif subtype == CONTRACT_NAVIGATION_TIME_CONTROLS:
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
        return errors

    def _build_effective_route_payload(self, compiled_task, declaration_payload: dict) -> dict:
        route = self.contestant.navigation_task.route
        payload = {
            "route_id": route.pk,
            "waypoint_names": [item.name for item in route.waypoints],
            "compiled_task_primitives": compiled_task.get_compiled_primitives(),
            "compiled_auxiliary_paths": (compiled_task.compiled_payload or {}).get("compiled_auxiliary_paths", {}),
        }
        subtype = self.contestant.navigation_task.task_subtype
        if subtype == PRECISION_NAVIGATION:
            payload["known_time_gate_predictions"] = declaration_payload.get("known_time_gate_predictions", {})
            payload["expected_prediction_names"] = self._get_precision_navigation_prediction_names()
        elif subtype == CONTRACT_NAVIGATION_TIME_CONTROLS:
            declared_sequence = declaration_payload.get("declared_sequence", [])
            effective_waypoints = self._build_contract_navigation_effective_waypoints(compiled_task, declared_sequence)
            payload["declared_sequence"] = declared_sequence
            payload["effective_waypoint_names"] = [item["name"] for item in effective_waypoints]
            payload["effective_waypoints"] = effective_waypoints
            payload["time_model"] = self._build_contract_navigation_time_model(declared_sequence)
        elif subtype in (TURNPOINT_HUNT, LIMITED_FUEL_TURNPOINT_HUNT):
            compulsory_point_names = self._get_turnpoint_hunt_compulsory_point_names(compiled_task)
            compulsory_point_times = self._get_turnpoint_hunt_compulsory_point_times(declaration_payload)
            effective_waypoints = self._build_turnpoint_hunt_effective_waypoints(compiled_task, compulsory_point_names)
            free_targets = self._build_turnpoint_hunt_free_targets()
            payload["compulsory_point_names"] = compulsory_point_names
            payload["compulsory_point_times"] = compulsory_point_times
            payload["effective_waypoint_names"] = [item["name"] for item in effective_waypoints]
            payload["effective_waypoints"] = effective_waypoints
            payload["compulsory_timing_gate_names"] = compulsory_point_names
            payload["compulsory_timing_tolerance_seconds"] = int(
                getattr(self.contestant.navigation_task.scorecard, "compulsory_timing_tolerance_seconds", 10) or 10
            )
            payload["free_targets"] = free_targets
            payload["free_target_names"] = [item["name"] for item in free_targets]
            payload["free_target_evidence"] = {
                item["name"]: [evidence["name"] for evidence in item.get("evidence", [])]
                for item in free_targets
            }
            payload["observation_photos"] = self._build_turnpoint_hunt_observation_photos(free_targets)
            payload["scored_target_values"] = self._build_turnpoint_hunt_scored_target_values(free_targets)
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
        elif subtype == "duration":
            duration_review = {}
            if getattr(self.contestant.navigation_task.scorecard, "duration_normalization_policy", ""):
                duration_review["duration_normalization_policy"] = self.contestant.navigation_task.scorecard.duration_normalization_policy
            editable_route = self.contestant.navigation_task.editable_route
            if editable_route is not None:
                duration_polygons = editable_route.get_duration_landing_area_polygons()
                if duration_polygons:
                    polygon = duration_polygons[0].get("geometry", {}).get("coordinates", [[]])[0]
                    if len(polygon) > 1 and polygon[0] == polygon[-1]:
                        polygon = polygon[:-1]
                    duration_review["duration_landing_area_polygon"] = polygon
            if getattr(self.contestant.navigation_task.scorecard, "duration_residual_fuel_required", False):
                duration_review["duration_residual_fuel_required"] = True
            if duration_review:
                payload["duration_review"] = duration_review
        elif subtype in (KNOWN_CIRCUIT, UNKNOWN_LEGS):
            payload.update(self._build_observation_evidence_payload(compiled_task))
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
        return [name for name in compiled_task.get_compiled_primitives().get("known_time_gate", []) if name][:3]

    def _get_turnpoint_hunt_compulsory_point_times(self, declaration_payload: dict) -> dict:
        point_times = declaration_payload.get("compulsory_point_times")
        if point_times is None:
            point_times = declaration_payload.get("predicted_gate_times")
        return point_times or {}

    def _build_turnpoint_hunt_free_targets(self) -> list[dict]:
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

    def _build_contract_navigation_effective_waypoint_names(self, declared_sequence: list) -> list[str]:
        return [item["name"] for item in self._build_contract_navigation_effective_waypoints(
            TaskCompiler(self.contestant.navigation_task).compile(), declared_sequence
        )]

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
                waypoint = build_waypoint(item, lat, lon, "tp", reference.width, False, True)
                waypoint.gate_line = [list(reference.gate_line[0]), list(reference.gate_line[1])] if reference.gate_line else []
                waypoint.elevation = getattr(reference, "elevation", 0)
                effective_waypoints.append(waypoint)
        if effective_waypoints[-1].name != fp.name:
            effective_waypoints.append(fp)

        calculate_and_update_legs(effective_waypoints, self.contestant.navigation_task.route.use_procedure_turns)
        insert_gate_ranges(effective_waypoints)

        return [self._serialise_waypoint(waypoint) for waypoint in effective_waypoints]

    def _build_contract_navigation_time_model(self, declared_sequence: list) -> dict:
        t_seconds = int(self.contestant.navigation_task.task_config.get("contract_time_seconds", 0) or 0)
        before_mp = []
        after_mp = []
        seen_mp = False
        for item in declared_sequence:
            if item == "MP":
                seen_mp = True
                continue
            if item == "FP":
                continue
            if item == "SP":
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

    def _build_turnpoint_hunt_effective_waypoints(self, compiled_task, compulsory_point_names: list[str]) -> list[dict]:
        base_waypoints = self.contestant.navigation_task.route.waypoints
        if not base_waypoints:
            return []

        editable_route = self.contestant.navigation_task.editable_route
        known_time_gate_features = editable_route.get_known_time_gates() if editable_route else []
        primitive_by_name = {
            feature["properties"].get("name"): feature for feature in known_time_gate_features
        }

        sp = base_waypoints[0]
        fp = base_waypoints[-1]
        reference = base_waypoints[min(1, len(base_waypoints) - 1)]
        effective_waypoints = [sp]

        for item in compulsory_point_names:
            feature = primitive_by_name.get(item)
            if not feature:
                continue
            lon, lat = feature["geometry"]["coordinates"]
            waypoint = build_waypoint(item, lat, lon, "tp", reference.width, True, True)
            waypoint.gate_line = [list(reference.gate_line[0]), list(reference.gate_line[1])] if reference.gate_line else []
            waypoint.elevation = getattr(reference, "elevation", 0)
            effective_waypoints.append(waypoint)

        if effective_waypoints[-1].name != fp.name:
            effective_waypoints.append(fp)

        calculate_and_update_legs(effective_waypoints, self.contestant.navigation_task.route.use_procedure_turns)
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
            "inside_distance": waypoint.inside_distance,
            "outside_distance": waypoint.outside_distance,
            "is_procedure_turn": waypoint.is_procedure_turn,
            "is_steep_turn": waypoint.is_steep_turn,
            "end_curved": waypoint.end_curved,
            "elevation": waypoint.elevation,
        }

    def _build_gate_times_payload(self, declaration_payload: dict) -> dict[str, str]:
        gate_times = {
            key: value.isoformat() for key, value in self.contestant.calculate_missing_gate_times({}).items()
        }
        predictions = declaration_payload.get("known_time_gate_predictions", {})
        for key, value in predictions.items():
            if isinstance(value, str):
                gate_times[key] = parser.parse(value).isoformat()

        if self.contestant.navigation_task.task_subtype == PRECISION_NAVIGATION:
            expected_names = set(self._get_precision_navigation_prediction_names())
            gate_times = {
                key: value
                for key, value in gate_times.items()
                if key in expected_names
            }

        if self.contestant.navigation_task.task_subtype in (TURNPOINT_HUNT, LIMITED_FUEL_TURNPOINT_HUNT):
            compulsory_point_times = self._get_turnpoint_hunt_compulsory_point_times(declaration_payload)
            for key, value in compulsory_point_times.items():
                if isinstance(value, str):
                    gate_times[key] = parser.parse(value).isoformat()
            base_time = self.contestant.takeoff_time + datetime.timedelta(minutes=self.contestant.minutes_to_starting_point)
            free_targets = self._build_turnpoint_hunt_free_targets()
            offset_minutes = 0
            for target in free_targets:
                name = target.get("name")
                if not isinstance(name, str) or name in gate_times:
                    continue
                gate_times[name] = (base_time + datetime.timedelta(minutes=offset_minutes)).isoformat()
                offset_minutes += 5

        if self.contestant.navigation_task.task_subtype == CONTRACT_NAVIGATION_TIME_CONTROLS:
            declared_sequence = declaration_payload.get("declared_sequence", [])
            time_model = self._build_contract_navigation_time_model(declared_sequence)
            base_time = self.contestant.takeoff_time + datetime.timedelta(minutes=self.contestant.minutes_to_starting_point)
            gate_times["SP"] = base_time.isoformat()
            gate_times["MP"] = (base_time + datetime.timedelta(seconds=time_model["mp_offset_seconds"])).isoformat()
            gate_times["FP"] = (base_time + datetime.timedelta(seconds=time_model["fp_offset_seconds"])).isoformat()
            offset_minutes = 0
            for name in declared_sequence:
                if not isinstance(name, str) or name in ("SP", "MP", "FP"):
                    continue
                if name not in gate_times:
                    gate_times[name] = (base_time + datetime.timedelta(minutes=offset_minutes)).isoformat()
                    offset_minutes += 5
        return gate_times

    def _lock_if_needed(self, config: ContestantTaskConfiguration) -> None:
        if self.contestant.tracker_start_time <= self.contestant.takeoff_time:
            return
        self.contestant.schedule_locked = True
        self.contestant.save(update_fields=["schedule_locked"])

    def build_declaration_payload_from_input(self, declaration_input: dict | None = None) -> dict:
        declaration_input = declaration_input or {}
        subtype = self.contestant.navigation_task.task_subtype
        if subtype in (CURVE_NAVIGATION_TIME_ESTIMATION, PRECISION_NAVIGATION):
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

        if subtype == CONTRACT_NAVIGATION_TIME_CONTROLS:
            declared_sequence = declaration_input.get("declared_sequence")
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
            return {"declared_sequence": normalized_sequence} if normalized_sequence else {}

        if subtype in (TURNPOINT_HUNT, LIMITED_FUEL_TURNPOINT_HUNT):
            compulsory_point_times = declaration_input.get("compulsory_point_times")
            if compulsory_point_times is None:
                compulsory_point_times = declaration_input.get("predicted_gate_times") or {}
            fuel_metadata = declaration_input.get("fuel_metadata") or {}
            if not isinstance(compulsory_point_times, dict):
                raise serializers.ValidationError({"compulsory_point_times": "Expected a dictionary of compulsory point times."})
            if not isinstance(fuel_metadata, dict):
                raise serializers.ValidationError({"fuel_metadata": "Expected a dictionary of fuel metadata."})
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
            payload = {}
            if normalized_point_times:
                payload["compulsory_point_times"] = normalized_point_times
            if fuel_metadata:
                payload["fuel_metadata"] = fuel_metadata
            return payload

        return {}
