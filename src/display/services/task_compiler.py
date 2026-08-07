import hashlib
import json

TASK_COMPILER_SIGNATURE_VERSION = 2

from display.models import CompiledNavigationTask
from display.utilities.cima_task_type_definitions import (
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    LIMITED_FUEL_TURNPOINT_HUNT,
    PRECISION_NAVIGATION,
    TURNPOINT_HUNT,
    UNKNOWN_LEGS,
    get_task_subtype_definition,
)
from display.utilities.gate_definitions import FINISHPOINT, STARTINGPOINT, TURNPOINT, UNKNOWN_LEG, DUMMY, HIDDEN_GATE, SECRETPOINT


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
            # compiled_primitives is the canonical compiled-task contract.
            # Keep new consumers on this key so older compatibility aliases can
            # be removed once the remaining tests/callers migrate.
            "compiled_primitives": primitives,
            "compiled_auxiliary_paths": self._build_compiled_auxiliary_paths(),
            **self._build_subtype_payload(primitives),
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
            "dummy_branch_waypoint": [
                item.get("properties", {}).get("name")
                for item in editable_route.get_features_type("dummy_branch_waypoint")
                if item.get("properties", {}).get("name")
            ],
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
        # required_primitives only checks authored primitive presence. Subtype-
        # specific structure rules (for example SP/MP/FP ordering) are layered
        # below so the registry stays declarative and the stricter shape checks
        # remain close to the subtype-specific semantics.
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
        if subtype == UNKNOWN_LEGS:
            errors.extend(self._validate_unknown_legs_structure(primitives))
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
        authored_waypoints = editable_route.get_ordered_track_waypoints()
        compiled_known_time_gates = [name for name in primitives.get("known_time_gate", []) if name]
        compulsory_backbone_count = len(compiled_known_time_gates) if compiled_known_time_gates else (len(authored_waypoints) if authored_waypoints else len(self.navigation_task.route.waypoints))
        if compulsory_backbone_count != 3:
            errors.append("Turnpoint hunt requires exactly three compulsory points.")
        free_targets = [name for name in primitives.get("catalogue_turnpoint", []) if name]
        if len(free_targets) < 1:
            errors.append("Turnpoint hunt requires at least one free catalogue target.")

        return errors

    def _validate_unknown_legs_structure(self, primitives: dict) -> list[str]:
        editable_route = self.navigation_task.editable_route
        if editable_route is None:
            return []

        errors = []
        authored_waypoints = editable_route.get_ordered_track_waypoints()
        if len(authored_waypoints) < 3:
            errors.append("Unknown legs requires at least a start point, one trigger segment, and a finish point.")
            return errors

        first_type = authored_waypoints[0].get("properties", {}).get("pointType")
        last_type = authored_waypoints[-1].get("properties", {}).get("pointType")
        if first_type != STARTINGPOINT or last_type != FINISHPOINT:
            errors.append("Unknown legs route waypoints must start at SP and finish at FP.")

        unknown_leg_names = [name for name in primitives.get("unknown_leg", []) if name]
        if not unknown_leg_names:
            errors.append("Unknown legs requires at least one unknown-leg trigger waypoint.")

        point_types = [item.get("properties", {}).get("pointType") for item in authored_waypoints]
        dummy_branch_features = editable_route.get_features_type("dummy_branch_waypoint")
        dummy_branch_by_trigger = {}
        for feature in dummy_branch_features:
            props = feature.get("properties", {})
            trigger_id = props.get("triggerPointId")
            if not trigger_id:
                continue
            dummy_branch_by_trigger.setdefault(trigger_id, []).append(feature)
        for branch_items in dummy_branch_by_trigger.values():
            branch_items.sort(key=lambda item: item.get("properties", {}).get("branchSequence", 0))
        for trigger_index, point_type in enumerate(point_types):
            if point_type != UNKNOWN_LEG:
                continue
            trigger_id = authored_waypoints[trigger_index].get("properties", {}).get("id")
            if not trigger_id or not dummy_branch_by_trigger.get(trigger_id):
                errors.append("Unknown legs requires at least one dummy waypoint after each unknown-leg trigger.")
                break

        if not primitives.get("route_to_sp_path", []) or not primitives.get("route_from_fp_path", []):
            errors.append("Unknown legs requires route_to_sp_path and route_from_fp_path for the full competition workflow.")
        if not unknown_leg_names:
            return errors

        return errors

    def _build_unknown_legs_compiled_payload(self) -> dict:
        editable_route = self.navigation_task.editable_route
        if editable_route is None:
            return {
                "unknown_legs_segments": [],
                "unknown_legs_actual_route": {
                    "waypoint_names": [],
                    "waypoints": [],
                    "unknown_leg_connectors": [],
                },
                "unknown_legs_hidden_gates": [],
            }

        ordered_waypoints = editable_route.get_ordered_track_waypoints()
        if not ordered_waypoints:
            return {
                "unknown_legs_segments": [],
                "unknown_legs_actual_route": {
                    "waypoint_names": [],
                    "waypoints": [],
                    "unknown_leg_connectors": [],
                },
                "unknown_legs_hidden_gates": [],
            }

        segments = []
        current_segment = {
            "name": "segment_1",
            "display_waypoint_names": [],
            "display_coordinates_by_name": {},
            "actual_waypoint_names": [],
            "actual_coordinates_by_name": {},
        }
        post_trigger_hidden_gate_names = set()
        actual_route_names = []
        actual_route_waypoints = []
        connectors = []
        segment_index = 1
        editable_route_features = editable_route.get_features_type("dummy_branch_waypoint")
        dummy_branch_by_trigger = {}
        for feature in editable_route_features:
            props = feature.get("properties", {})
            trigger_id = props.get("triggerPointId")
            if not trigger_id:
                continue
            dummy_branch_by_trigger.setdefault(trigger_id, []).append(feature)
        for branch_items in dummy_branch_by_trigger.values():
            branch_items.sort(key=lambda item: item.get("properties", {}).get("branchSequence", 0))

        def append_actual_name(name: str):
            if not actual_route_names or actual_route_names[-1] != name:
                actual_route_names.append(name)

        def append_actual_waypoint(name: str, point_type: str, coordinates: list):
            if actual_route_waypoints and actual_route_waypoints[-1].get("name") == name:
                return
            actual_route_waypoints.append(
                {
                    "name": name,
                    "type": point_type,
                    "coordinates": coordinates,
                }
            )

        def feature_coordinates(item: dict) -> list:
            return item.get("geometry", {}).get("coordinates", [])

        for index, item in enumerate(ordered_waypoints):
            properties = item.get("properties", {})
            name = properties.get("name")
            point_type = properties.get("pointType")
            coordinates = feature_coordinates(item)
            if not name:
                continue

            include_in_display_segment = True
            if point_type in (HIDDEN_GATE, SECRETPOINT) and name in post_trigger_hidden_gate_names:
                include_in_display_segment = False

            if include_in_display_segment:
                current_segment["display_waypoint_names"].append(name)
                current_segment["display_coordinates_by_name"][name] = coordinates

            if point_type != DUMMY:
                current_segment["actual_waypoint_names"].append(name)
                current_segment["actual_coordinates_by_name"][name] = coordinates
                append_actual_name(name)
                append_actual_waypoint(name, point_type, coordinates)

            if point_type == UNKNOWN_LEG:
                trigger_id = properties.get("id")
                branch_features = dummy_branch_by_trigger.get(trigger_id, []) if trigger_id else []
                branch_waypoints = []
                post_trigger_hidden_gate_names = set()
                for next_item in ordered_waypoints[index + 1 :]:
                    next_type = next_item.get("properties", {}).get("pointType")
                    next_name = next_item.get("properties", {}).get("name")
                    if next_type in (HIDDEN_GATE, SECRETPOINT) and next_name:
                        post_trigger_hidden_gate_names.add(next_name)
                        continue
                    break
                for branch_feature in branch_features:
                    branch_properties = branch_feature.get("properties", {})
                    branch_name = branch_properties.get("name")
                    branch_coordinates = feature_coordinates(branch_feature)
                    if not branch_name or len(branch_coordinates) != 2:
                        continue
                    current_segment["display_waypoint_names"].append(branch_name)
                    current_segment["display_coordinates_by_name"][branch_name] = branch_coordinates
                    branch_waypoints.append(
                        {
                            "name": branch_name,
                            "coordinates": branch_coordinates,
                            "trigger_point_id": trigger_id,
                            "branch_sequence": branch_properties.get("branchSequence", 0),
                        }
                    )
                next_real_waypoint = None
                for next_item in ordered_waypoints[index + 1 :]:
                    next_type = next_item.get("properties", {}).get("pointType")
                    if next_type == HIDDEN_GATE:
                        continue
                    next_real_waypoint = next_item
                    break
                if next_real_waypoint is not None:
                    next_name = next_real_waypoint.get("properties", {}).get("name")
                    next_coordinates = feature_coordinates(next_real_waypoint)
                    connectors.append(
                        {
                            "from": name,
                            "to": next_name,
                            "heading": properties.get("unknownLegHeading"),
                            "from_coordinates": coordinates,
                            "to_coordinates": next_coordinates,
                            "dummy_branch_waypoint_names": [
                                feature.get("properties", {}).get("name")
                                for feature in branch_features
                                if feature.get("properties", {}).get("name")
                            ],
                            "dummy_branch_waypoints": branch_waypoints,
                        }
                    )
                segments.append(current_segment)
                segment_index += 1
                current_segment = {
                    "name": f"segment_{segment_index}",
                    "display_waypoint_names": [],
                    "display_coordinates_by_name": {},
                    "actual_waypoint_names": [],
                    "actual_coordinates_by_name": {},
                }
                continue

            if point_type in (TURNPOINT, FINISHPOINT):
                post_trigger_hidden_gate_names = set()

        if current_segment["display_waypoint_names"] or current_segment["actual_waypoint_names"]:
            segments.append(current_segment)

        return {
            "unknown_legs_segments": segments,
            "unknown_legs_actual_route": {
                "waypoint_names": actual_route_names,
                "waypoints": actual_route_waypoints,
                "unknown_leg_connectors": connectors,
            },
            "unknown_legs_hidden_gates": [
                {
                    "name": item.get("properties", {}).get("name") or "",
                    "coordinates": item.get("geometry", {}).get("coordinates", []),
                }
                for item in ordered_waypoints
                if (
                    item.get("properties", {}).get("pointType") in (HIDDEN_GATE, SECRETPOINT)
                    or item.get("properties", {}).get("featureType") == "hidden_gate"
                )
                and len(item.get("geometry", {}).get("coordinates", [])) == 2
            ],
        }

    def _build_subtype_payload(self, primitives: dict) -> dict:
        if self._get_effective_task_subtype() == UNKNOWN_LEGS:
            return self._build_unknown_legs_compiled_payload()
        return {}

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
            "signature_version": TASK_COMPILER_SIGNATURE_VERSION,
            "task": self.navigation_task.pk,
            "route": route_pk,
            "editable_route": editable_route_pk,
            "subtype": self.navigation_task.task_subtype or "",
            "task_config": self.navigation_task.task_config,
            "scorecard": scorecard_signature,
        }
        canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
