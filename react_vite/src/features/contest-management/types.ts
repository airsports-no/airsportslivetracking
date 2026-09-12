export interface TaskTemplateChoice {
    value: string;
    label: string;
    // Coarse family (e.g. "anr_corridor") and, if a CIMA subtype was picked, its specific key -
    // together these are what the create payload's task_subtype field and the per-family
    // parameter requirements (see navigationTaskFlow.requiredParameters) are keyed on.
    task_type: string;
    task_subtype: string;
    // The effective compatibility-ruleset key (task_subtype, or the family's legacy shim when
    // task_subtype is empty) - use this only for filtering the route picker, never for the
    // create payload.
    subtype_key: string;
}

export interface TaskTemplateGroup {
    group: string;
    templates: TaskTemplateChoice[];
}

export interface TaskTemplatesResponse {
    groups: TaskTemplateGroup[];
    no_compatible_task_types_message: string | null;
}

export interface ScorecardChoice {
    shortcut_name: string;
    name: string;
    task_type: string[];
}

// Mirrors the write side of NavigationTaskEditableRoutReferenceSerialiser.
export interface NavigationTaskCreatePayload {
    name: string;
    start_time: string;
    finish_time: string;
    original_scorecard: string;
    editable_route: number;
    task_subtype?: string;
    task_config?: Record<string, unknown>;
    corridor_width?: number;
    rounded_corners?: boolean;
    display_background_map: boolean;
    display_secrets: boolean;
    minutes_to_starting_point: number;
    planning_time: number;
    minutes_to_landing: number;
    wind_speed: number;
    wind_direction: number;
    allow_self_management: boolean;
    calculation_delay_minutes: number;
}

export interface NavigationTaskCreateResponse {
    id: number;
    warnings: string[];
}
