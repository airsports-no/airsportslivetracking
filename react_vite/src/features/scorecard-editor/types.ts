// Mirrors ScorecardNestedSerialiser / GateScoreSerialiser (src/display/serialisers.py) and the
// NavigationTaskViewSet.scorecard action's merged response (src/display/viewsets.py) - Scorecard
// Phase 3.

export interface GateScoreData {
    gate_type: string;
    extended_gate_width?: number;
    bad_crossing_extended_gate_penalty?: number;
    graceperiod_before?: number;
    graceperiod_after?: number;
    maximum_penalty?: number;
    penalty_per_second?: number;
    missed_penalty?: number;
    missed_procedure_turn_penalty?: number;
    backtracking_after_steep_gate_grace_period_seconds?: number;
    backtracking_before_gate_grace_period_nm?: number;
    backtracking_after_gate_grace_period_nm?: number;
    visible_fields: string[];
}

export type GateFieldName = Exclude<keyof GateScoreData, 'gate_type' | 'visible_fields'>;

export interface ScorecardData {
    shortcut_name: string;
    valid_from: string;
    free_text: string;
    score_sorting_direction: string;
    initial_score: number;
    task_type: string[];
    corridor_width: number;
    gatescore_set: GateScoreData[];
    visible_fields: string[];

    backtracking_penalty?: number;
    backtracking_bearing_difference?: number;
    backtracking_grace_time_seconds?: number;
    backtracking_maximum_penalty?: number;
    prohibited_zone_penalty?: number;
    prohibited_zone_grace_time?: number;
    prohibited_zone_maximum?: number;
    penalty_zone_grace_time?: number;
    penalty_zone_penalty_per_second?: number;
    penalty_zone_maximum?: number;
    corridor_grace_time?: number;
    corridor_outside_penalty?: number;
    corridor_maximum_penalty?: number;
    corridor_maximum_penalty_is_per_leg?: boolean;
    anr_route_to_sp_penalty?: number;
    anr_route_from_fp_penalty?: number;
    compulsory_timing_tolerance_seconds?: number;
    maximum_task_duration_minutes?: number | null;
    maximum_task_duration_penalty?: number;
    fuel_deadline_penalty?: number;
    duration_normalization_policy?: string;
    duration_residual_fuel_required?: boolean;
    circle_radius_min_m?: number;
    circle_radius_max_m?: number;
    speed_keeping_tolerance_kt?: number;
    speed_keeping_penalty_per_kt?: number;

    // Merged in by the scorecard action (viewsets.py), not part of the plain serializer shape.
    applicable_gate_types: string[];
    applicable_scalar_groups: string[];
    original_scorecard: ScorecardData | null;
}

export type ScalarFieldName = Exclude<
    keyof ScorecardData,
    | 'shortcut_name'
    | 'valid_from'
    | 'free_text'
    | 'score_sorting_direction'
    | 'initial_score'
    | 'task_type'
    | 'corridor_width'
    | 'gatescore_set'
    | 'visible_fields'
    | 'applicable_gate_types'
    | 'applicable_scalar_groups'
    | 'original_scorecard'
>;

// Client-side editing state: only fields the user has actually touched are ever sent back to
// the API (see scorecardEditorLogic.ts's buildSavePayload) - a field the user never touched
// stays entirely absent from both editedScalars and editedGates, so it can never accidentally
// reach the server as a blank/null value.
export interface ScorecardEditorState {
    editedScalars: Partial<Record<ScalarFieldName, number | boolean | string | null>>;
    editedGates: Record<string, Partial<Record<GateFieldName, number>>>;
}
