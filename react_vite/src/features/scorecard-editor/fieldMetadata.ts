import { GateFieldName, ScalarFieldName } from './types';

export type FieldKind = 'number' | 'integer' | 'boolean' | 'choice';

export interface FieldMeta {
    label: string;
    kind: FieldKind;
    unit?: string;
    min?: number;
    step?: number;
    max?: number;
    /** Plain-words explanation shown under the field. */
    help?: string;
    choices?: { value: string; label: string }[];
}

// Labels follow the same convention as the legacy Django forms this replaces
// (capfirst(field_name.replace("_", " ")) - forms.py:1029), grouped so the editor can present
// them as sections instead of one long flat list.
export const SCALAR_FIELD_GROUPS: { title: string; fields: ScalarFieldName[] }[] = [
    {
        title: 'General',
        fields: ['score_sorting_direction', 'initial_score', 'scoring_model', 'qmax_policy', 'task_value'],
    },
    {
        title: 'Backtracking',
        fields: [
            'backtracking_penalty',
            'backtracking_bearing_difference',
            'backtracking_grace_time_seconds',
            'backtracking_maximum_penalty',
            'backtracking_penalty_percentage',
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
            'compulsory_timing_penalty_per_second',
            'turnpoint_hunt_time_gate_value',
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
        fields: ['circle_radius_min_m', 'circle_radius_max_m', 'circle_altitude_band_ft', 'circle_altitude_penalty_percent'],
    },
    {
        title: 'Speed keeping',
        fields: ['speed_term_value', 'speed_keeping_enabled', 'speed_keeping_tolerance_kt', 'speed_keeping_penalty_per_kt'],
    },
    {
        title: 'Observation photos',
        fields: [
            'observation_photo_penalty',
            'observation_photo_value',
            'observation_photo_full_tolerance_mm',
            'observation_photo_half_tolerance_mm',
        ],
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
    scoring_model: {
        label: 'Scoring model',
        kind: 'choice',
        choices: [
            { value: '', label: 'Task type default' },
            { value: 'quality', label: 'Quality score (CIMA): scaled to the best flight' },
            { value: 'penalties', label: 'Penalty points: penalties add up' },
        ],
        help:
            'Quality score: every pilot earns a raw quality score, and the task score is scaled so that the best flight in the ' +
            'task gets the full task value. The highest task score wins, and it can change until all flights are finished. ' +
            'Penalty points: penalties are added up, as in the older scorecards.',
    },
    qmax_policy: {
        label: 'Scaled to',
        kind: 'choice',
        choices: [
            { value: '', label: 'Task type default' },
            { value: 'best_in_task', label: 'The best flight in the task' },
            { value: 'theoretical', label: "Each pilot's theoretical maximum" },
            { value: 'absolute', label: 'An absolute scale (no comparison with the others)' },
        ],
        help:
            'What a pilot\'s raw quality score is divided by. The best flight in the task (the CIMA rule) gives the best pilot ' +
            'the full task value. The theoretical maximum compares each pilot with the most they could have scored. An absolute ' +
            'scale does not depend on the other pilots (the circle and the ANR task use it). Only used with the quality score.',
    },
    task_value: {
        label: 'Task value',
        kind: 'number',
        unit: 'points',
        min: 500,
        max: 1500,
        help:
            'The task score of the best flight, announced before the task. It must be between 500 and 1500 points ' +
            '(1000 if you leave it as it is). Only used with the quality score.',
    },
    backtracking_penalty: { label: 'Backtracking penalty', kind: 'number', min: 0 },
    backtracking_bearing_difference: { label: 'Backtracking bearing difference', kind: 'number', unit: '°', min: 0 },
    backtracking_grace_time_seconds: { label: 'Backtracking grace time', kind: 'number', unit: 's', min: 0 },
    backtracking_maximum_penalty: { label: 'Backtracking maximum penalty', kind: 'number', min: 0 },
    backtracking_penalty_percentage: {
        label: 'Backtracking penalty (% of the task score)',
        kind: 'number',
        unit: '%',
        min: 0,
        max: 100,
        help:
            'CIMA tasks 2.A1-2.A5 take this share of the final task score for backtracking (50% in the catalogue). ' +
            'Leave it blank for the task type\'s own value; 0 uses the flat backtracking penalty above instead.',
    },
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
    compulsory_timing_penalty_per_second: {
        label: 'Compulsory timing penalty per second beyond the tolerance',
        kind: 'number',
        min: 0,
    },
    turnpoint_hunt_time_gate_value: { label: 'Time gate value', kind: 'number', min: 0 },
    maximum_task_duration_minutes: { label: 'Maximum task duration', kind: 'integer', unit: 'min', min: 0 },
    maximum_task_duration_penalty: { label: 'Maximum task duration penalty per second over', kind: 'number', min: 0 },
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
    circle_altitude_band_ft: {
        label: 'Circle altitude band',
        kind: 'number',
        unit: 'ft',
        min: 0,
        help: 'Circle (2.A7): the most the aircraft may climb or descend between the lowest and the highest point of the scored circle (200 ft / 61 m).',
    },
    circle_altitude_penalty_percent: {
        label: 'Circle altitude penalty',
        kind: 'number',
        unit: '%',
        min: 0,
        max: 100,
        help: 'Circle (2.A7): the percentage of the task score lost when the altitude band is exceeded (20%).',
    },
    speed_term_value: {
        label: 'Speed term value (Vs)',
        kind: 'number',
        unit: 'points',
        min: 0,
        help:
            'Navigation over a known circuit (2.A4): the points the fastest pilot of the task earns for the speed term ' +
            '(Qv = Vs x S / Smax, S being the ground speed between the first and the last time gate). 0 leaves the speed term out.',
    },
    speed_keeping_enabled: {
        label: 'Penalise deviation from the declared speed',
        kind: 'boolean',
        help: 'Not part of the catalogue: penalises every leg flown faster or slower than the declared speed. Off by default.',
    },
    speed_keeping_tolerance_kt: { label: 'Speed keeping tolerance', kind: 'number', unit: 'kt', min: 0 },
    speed_keeping_penalty_per_kt: { label: 'Speed keeping penalty per kt', kind: 'number', min: 0 },
    turnpoint_hunt_sequence_bonus: { label: 'Turnpoint hunt sequence bonus', kind: 'number', min: 0 },
    observation_photo_penalty: { label: 'Penalty per missed observation (legacy)', kind: 'number', min: 0 },
    observation_photo_value: { label: 'Points per observation (CIMA)', kind: 'number', min: 0 },
    observation_photo_full_tolerance_mm: { label: 'Full score within (blank: 1 mm legacy, 2 mm CIMA)', kind: 'number', unit: 'mm', min: 0 },
    observation_photo_half_tolerance_mm: { label: 'Half score within (blank: none legacy, 5 mm CIMA)', kind: 'number', unit: 'mm', min: 0 },
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
