import hashlib
import json

from display.models import CompiledNavigationTask
from display.utilities.cima_task_type_definitions import (
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    LIMITED_FUEL_TURNPOINT_HUNT,
    PRECISION_NAVIGATION,
    TURNPOINT_HUNT,
    get_task_subtype_definition,
)
from display.utilities.gate_definitions import FINISHPOINT, STARTINGPOINT, TURNPOINT


class TaskCompiler:
    def __init__(self, navigation_task):
        self.navigation_task = navigation_task

    def compile(self, force: bool = False) -> CompiledNavigationTask:
        effective_subtype = self._get_effective_task_subtype()
        current_signature = self._calculate_source_signature()
        compiled, created = CompiledNavigationTask.objects.get_or_create(
            navigation_task=self.navigation_task,
            defaults={
                "compiled_family_route": self.navigation_task.route,
                "task_subtype": effective_subtype,
                "compiled_payload": self._build_compiled_payload(),
                "source_signature": current_signature,
            },
        )
        if force or created or compiled.source_signature != current_signature:
            compiled.compiled_family_route = self.navigation_task.route
            compiled.task_subtype = effective_subtype
            compiled.compiled_payload = self._build_compiled_payload()
            compiled.source_signature = current_signature
            compiled.save()
        return compiled

    def _get_effective_task_subtype(self) -> str:
        return self.navigation_task.effective_task_subtype or ""

    def _build_compiled_payload(self) -> dict:
        primitives = self._build_compiled_primitives()
        validation_errors = self._validate_primitives(primitives)
        return {
            "coarse_task_family": self.navigation_task.coarse_task_family,
            "task_subtype": self._get_effective_task_subtype(),
            "task_config": self.navigation_task.task_config,
            "compiled_sequence": [],
            "compiled_primitives": primitives,
            "compiled_auxiliary_paths": self._build_compiled_auxiliary_paths(),
            "primitives": primitives,
            "validation_errors": validation_errors,
            "is_valid": len(validation_errors) == 0,
        }

    def _build_compiled_primitives(self) -> dict:
        editable_route = self.navigation_task.editable_route
        if editable_route is None:
            return {}
        return {
            "catalogue_turnpoint": [item["properties"].get("name") for item in editable_route.get_catalogue_turnpoints()],
            "circle_center_marker": [item["properties"].get("name") for item in editable_route.get_circle_center_markers()],
            "circle_start_marker": [item["properties"].get("name") for item in editable_route.get_circle_start_markers()],
            "circle_entry_marker": [item["properties"].get("name") for item in editable_route.get_circle_entry_markers()],
            "circle_exit_marker": [item["properties"].get("name") for item in editable_route.get_circle_exit_markers()],
            "route_to_sp_path": [
                item.get("properties", {}).get("name") or f"route_to_sp_{index}"
                for index, item in enumerate(editable_route.get_route_to_sp_paths(), start=1)
            ],
            "route_from_fp_path": [
                item.get("properties", {}).get("name") or f"route_from_fp_{index}"
                for index, item in enumerate(editable_route.get_route_from_fp_paths(), start=1)
            ],
            "known_time_gate": [item["properties"].get("name") for item in editable_route.get_known_time_gates()],
            "hidden_gate": [item["properties"].get("name") for item in editable_route.get_hidden_gates()],
            "unknown_leg": [item["properties"].get("name") for item in editable_route.get_unknown_leg_waypoints()],
            "observation_photo": [item["properties"].get("name") for item in editable_route.get_observation_photos()],
        }

    def _build_compiled_auxiliary_paths(self) -> dict:
        editable_route = self.navigation_task.editable_route
        if editable_route is None:
            return {}
        return {
            "route_to_sp_path": [
                item.get("geometry", {}).get("coordinates", []) for item in editable_route.get_route_to_sp_paths()
            ],
            "route_from_fp_path": [
                item.get("geometry", {}).get("coordinates", []) for item in editable_route.get_route_from_fp_paths()
            ],
        }

    def _validate_primitives(self, primitives: dict) -> list[str]:
        subtype = self._get_effective_task_subtype()
        if not subtype:
            return []
        definition = get_task_subtype_definition(str(subtype))
        errors = []
        for primitive in definition.required_primitives:
            values = primitives.get(primitive, [])
            if primitive == "route_path":
                if self.navigation_task.editable_route is None or self.navigation_task.editable_route.get_track() is None:
                    errors.append(f"Missing required primitive: {primitive}")
            elif not values:
                errors.append(f"Missing required primitive: {primitive}")
        if subtype == CONTRACT_NAVIGATION_TIME_CONTROLS:
            errors.extend(self._validate_contract_navigation_structure(primitives))
        if subtype == PRECISION_NAVIGATION:
            errors.extend(self._validate_precision_navigation_structure(primitives))
        if subtype in (TURNPOINT_HUNT, LIMITED_FUEL_TURNPOINT_HUNT):
            errors.extend(self._validate_turnpoint_hunt_structure(primitives))
        return errors

    def _validate_precision_navigation_structure(self, primitives: dict) -> list[str]:
        editable_route = self.navigation_task.editable_route
        if editable_route is None:
            return []

        errors = []
        authored_waypoints = editable_route.get_ordered_track_waypoints()
        if len(authored_waypoints) < 3:
            errors.append("Precision navigation requires a start, at least one intermediate turn point, and a finish.")
        else:
            first_type = authored_waypoints[0].get("properties", {}).get("pointType")
            last_type = authored_waypoints[-1].get("properties", {}).get("pointType")
            if first_type != STARTINGPOINT or last_type != FINISHPOINT:
                errors.append("Precision navigation route waypoints must start at SP and finish at FP.")

        hidden_gates = [name for name in primitives.get("hidden_gate", []) if name]
        if len(hidden_gates) < 1:
            errors.append("Precision navigation requires at least one hidden gate.")
        return errors

    def _validate_contract_navigation_structure(self, primitives: dict) -> list[str]:
        editable_route = self.navigation_task.editable_route
        if editable_route is None:
            return []

        errors = []
        authored_waypoints = editable_route.get_ordered_track_waypoints()
        if len(authored_waypoints) != 3:
            errors.append("Contract navigation requires exactly three route waypoints: SP, MP, and FP.")
        else:
            expected = [
                (STARTINGPOINT, "SP"),
                (TURNPOINT, "MP"),
                (FINISHPOINT, "FP"),
            ]
            for waypoint, (expected_type, expected_name) in zip(authored_waypoints, expected):
                point_type = waypoint.get("properties", {}).get("pointType")
                point_name = waypoint.get("properties", {}).get("name")
                if point_type != expected_type or point_name != expected_name:
                    errors.append("Contract navigation route waypoints must be authored in order as SP, MP, and FP.")
                    break

        free_waypoints = [name for name in primitives.get("catalogue_turnpoint", []) if name not in {"SP", "MP", "FP"}]
        if len(free_waypoints) < 1:
            errors.append("Contract navigation requires at least one free catalogue waypoint.")
        return errors

    def _validate_turnpoint_hunt_structure(self, primitives: dict) -> list[str]:
        editable_route = self.navigation_task.editable_route
        if editable_route is None:
            return []

        errors = []
        compulsory_names = [name for name in primitives.get("known_time_gate", []) if name]
        if len(compulsory_names) != 3:
            errors.append("Turnpoint hunt requires exactly three compulsory known time gates.")

        free_targets = [name for name in primitives.get("catalogue_turnpoint", []) if name]
        if len(free_targets) < 1:
            errors.append("Turnpoint hunt requires at least one free catalogue target.")

        evidence_by_target = {}
        for photo in editable_route.get_observation_photos():
            properties = photo.get("properties", {})
            target_name = properties.get("targetName") or properties.get("name")
            if target_name:
                evidence_by_target.setdefault(target_name, []).append(properties.get("name") or target_name)

        return errors

    def _calculate_source_signature(self) -> str:
        route_pk = getattr(self.navigation_task.route, "pk", "")
        editable_route_pk = getattr(self.navigation_task.editable_route, "pk", "")
        # The signature tracks every persisted configuration input that can
        # change compiled subtype semantics without forcing callers to pass
        # force=True. We intentionally include both task_config and relevant
        # scorecard runtime knobs in addition to route/editable-route identity.
        scorecard = getattr(self.navigation_task, "scorecard", None)
        scorecard_signature = (
            getattr(scorecard, "compulsory_timing_tolerance_seconds", None),
            getattr(scorecard, "maximum_task_duration_minutes", None),
            getattr(scorecard, "maximum_task_duration_penalty", None),
            getattr(scorecard, "fuel_deadline_penalty", None),
            getattr(scorecard, "duration_normalization_policy", None),
            getattr(scorecard, "duration_residual_fuel_required", None),
            getattr(scorecard, "circle_radius_min_m", None),
            getattr(scorecard, "circle_radius_max_m", None),
            getattr(scorecard, "anr_route_to_sp_penalty", None),
            getattr(scorecard, "anr_route_from_fp_penalty", None),
        )
        payload = {
            "task": self.navigation_task.pk,
            "route": route_pk,
            "editable_route": editable_route_pk,
            "subtype": self.navigation_task.task_subtype or "",
            "task_config": self.navigation_task.task_config,
            "scorecard": scorecard_signature,
        }
        canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
