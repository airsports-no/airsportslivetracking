import { GateFieldName, ScalarFieldName } from './types';

export type FieldKind = 'number' | 'integer' | 'boolean' | 'choice';

export interface FieldMeta {
    label: string;
    kind: FieldKind;
    unit?: string;
    min?: number;
    step?: number;
    choices?: { value: string; label: string }[];
}

// Labels follow the same convention as the legacy Django forms this replaces
// (capfirst(field_name.replace("_", " ")) - forms.py:1029), grouped so the editor can present
// them as sections instead of one long flat list.
export const SCALAR_FIELD_GROUPS: { title: string; fields: ScalarFieldName[] }[] = [
    {
        title: 'General',
        fields: ['score_sorting_direction', 'initial_score'],
    },
    {
        title: 'Backtracking',
        fields: [
            'backtracking_penalty',
            'backtracking_bearing_difference',
            'backtracking_grace_time_seconds',
            'backtracking_maximum_penalty',
        ],
    },
    {
        title: 'Zones',
        fields: [
            'prohibited_zone_penalty',
            'prohibited_zone_grace_time',
            'prohibited_zone_maximum',
            'penalty_zone_grace_time',
            'penalty_zone_penalty_per_second',
            'penalty_zone_maximum',
        ],
    },
    {
        title: 'Corridor',
        fields: [
            'corridor_grace_time',
            'corridor_outside_penalty',
            'corridor_maximum_penalty',
            'corridor_maximum_penalty_is_per_leg',
        ],
    },
    {
        title: 'ANR route',
        fields: ['anr_route_to_sp_penalty', 'anr_route_from_fp_penalty'],
    },
    {
        title: 'Duration',
        fields: [
            'compulsory_timing_tolerance_seconds',
            'maximum_task_duration_minutes',
            'maximum_task_duration_penalty',
            'fuel_deadline_penalty',
            'duration_normalization_policy',
            'duration_residual_fuel_required',
            'turnpoint_hunt_sequence_bonus',
        ],
    },
    {
        title: 'Circle',
        fields: ['circle_radius_min_m', 'circle_radius_max_m'],
    },
    {
        title: 'Speed keeping',
        fields: ['speed_keeping_tolerance_kt', 'speed_keeping_penalty_per_kt'],
    },
];

export const SCALAR_FIELD_META: Record<ScalarFieldName, FieldMeta> = {
    score_sorting_direction: {
        label: 'Score sorting direction',
        kind: 'choice',
        choices: [
            { value: 'asc', label: 'Ascending (lowest wins)' },
            { value: 'desc', label: 'Descending (highest wins)' },
        ],
    },
    initial_score: {
        label: 'Initial score',
        kind: 'number',
    },
    backtracking_penalty: { label: 'Backtracking penalty', kind: 'number', min: 0 },
    backtracking_bearing_difference: { label: 'Backtracking bearing difference', kind: 'number', unit: '°', min: 0 },
    backtracking_grace_time_seconds: { label: 'Backtracking grace time', kind: 'number', unit: 's', min: 0 },
    backtracking_maximum_penalty: { label: 'Backtracking maximum penalty', kind: 'number', min: 0 },
    prohibited_zone_penalty: { label: 'Prohibited zone penalty', kind: 'number', min: 0 },
    prohibited_zone_grace_time: { label: 'Prohibited zone grace time', kind: 'number', unit: 's', min: 0 },
    prohibited_zone_maximum: { label: 'Prohibited zone maximum', kind: 'number' },
    penalty_zone_grace_time: { label: 'Penalty zone grace time', kind: 'number', unit: 's', min: 0 },
    penalty_zone_penalty_per_second: { label: 'Penalty zone penalty per second', kind: 'number', min: 0 },
    penalty_zone_maximum: { label: 'Penalty zone maximum', kind: 'number' },
    corridor_grace_time: { label: 'Corridor grace time', kind: 'integer', unit: 's', min: 0 },
    corridor_outside_penalty: { label: 'Corridor outside penalty', kind: 'number', min: 0 },
    corridor_maximum_penalty: { label: 'Corridor maximum penalty', kind: 'number', min: 0 },
    corridor_maximum_penalty_is_per_leg: { label: 'Corridor maximum penalty is per leg', kind: 'boolean' },
    anr_route_to_sp_penalty: { label: 'ANR route to SP penalty', kind: 'number', min: 0 },
    anr_route_from_fp_penalty: { label: 'ANR route from FP penalty', kind: 'number', min: 0 },
    compulsory_timing_tolerance_seconds: { label: 'Compulsory timing tolerance', kind: 'integer', unit: 's', min: 0 },
    maximum_task_duration_minutes: { label: 'Maximum task duration', kind: 'integer', unit: 'min', min: 0 },
    maximum_task_duration_penalty: { label: 'Maximum task duration penalty', kind: 'number', min: 0 },
    fuel_deadline_penalty: { label: 'Fuel deadline penalty', kind: 'number', min: 0 },
    duration_normalization_policy: {
        label: 'Duration normalization policy',
        kind: 'choice',
        choices: [
            { value: '', label: '---------' },
            { value: 'raw_minutes', label: 'Raw minutes' },
        ],
    },
    duration_residual_fuel_required: { label: 'Duration residual fuel required', kind: 'boolean' },
    circle_radius_min_m: { label: 'Circle radius min', kind: 'number', unit: 'm', min: 0 },
    circle_radius_max_m: { label: 'Circle radius max', kind: 'number', unit: 'm', min: 0 },
    speed_keeping_tolerance_kt: { label: 'Speed keeping tolerance', kind: 'number', unit: 'kt', min: 0 },
    speed_keeping_penalty_per_kt: { label: 'Speed keeping penalty per kt', kind: 'number', min: 0 },
    turnpoint_hunt_sequence_bonus: { label: 'Turnpoint hunt sequence bonus', kind: 'number', min: 0 },
};

export const GATE_FIELD_ORDER: GateFieldName[] = [
    'graceperiod_before',
    'graceperiod_after',
    'penalty_per_second',
    'maximum_penalty',
    'missed_penalty',
    'missed_procedure_turn_penalty',
    'extended_gate_width',
    'bad_crossing_extended_gate_penalty',
    'backtracking_before_gate_grace_period_nm',
    'backtracking_after_gate_grace_period_nm',
    'backtracking_after_steep_gate_grace_period_seconds',
];

export const GATE_FIELD_META: Record<GateFieldName, FieldMeta> = {
    extended_gate_width: { label: 'Extended gate width', kind: 'number', unit: 'nm', min: 0 },
    bad_crossing_extended_gate_penalty: { label: 'Bad crossing extended gate penalty', kind: 'number', min: 0 },
    graceperiod_before: { label: 'Grace period before', kind: 'number', unit: 's', min: 0 },
    graceperiod_after: { label: 'Grace period after', kind: 'number', unit: 's', min: 0 },
    maximum_penalty: { label: 'Maximum penalty', kind: 'number', min: 0 },
    penalty_per_second: { label: 'Penalty per second', kind: 'number', min: 0 },
    missed_penalty: { label: 'Missed penalty', kind: 'number', min: 0 },
    missed_procedure_turn_penalty: { label: 'Missed procedure turn penalty', kind: 'number', min: 0 },
    backtracking_after_steep_gate_grace_period_seconds: {
        label: 'Backtracking after steep gate grace period',
        kind: 'number',
        unit: 's',
        min: 0,
    },
    backtracking_before_gate_grace_period_nm: {
        label: 'Backtracking before gate grace period',
        kind: 'number',
        unit: 'nm',
        min: 0,
    },
    backtracking_after_gate_grace_period_nm: {
        label: 'Backtracking after gate grace period',
        kind: 'number',
        unit: 'nm',
        min: 0,
    },
};

const GATE_TYPE_DISPLAY_NAMES: Record<string, string> = {
    tp: 'Turning Point',
    sp: 'Starting Point',
    fp: 'Finish Point',
    secret: 'Secret Point',
    anrtp: 'ANR Turning Point',
    to: 'Takeoff Gate',
    ldg: 'Landing Gate',
    isp: 'Intermediary Starting Point',
    ifp: 'Intermediary Finish Point',
    dummy: 'Dummy',
    ul: 'Unknown leg',
    catalogue_turnpoint: 'Catalogue turnpoint',
    circle_center: 'Circle center',
    circle_start: 'Circle start',
    circle_entry: 'Circle entry',
    circle_exit: 'Circle exit',
};

export function getGateTypeDisplayName(gateType: string): string {
    return GATE_TYPE_DISPLAY_NAMES[gateType] ?? gateType;
}
