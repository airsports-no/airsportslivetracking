// What the pilot endpoint /api/v1/declarations/<contestant id>/ returns (src/display/viewsets_declarations.py) and what the
// own-flight lists carry beside it (declaration_status, flight_order_status).

export type DeclarationNeed = 'not_needed' | 'optional' | 'required';
export type DeclarationState = 'missing' | 'incomplete' | 'complete';

export interface DeclarationStatus {
    need: DeclarationNeed;
    state: DeclarationState;
    errors: string[];
    can_edit: boolean;
    /** The cut-off as an ISO timestamp; only for the flight's crew */
    edit_until: string | null;
    edit_url: string | null;
}

export type FlightOrderState = 'waiting_for_declaration' | 'being_made' | 'ready' | 'failed' | 'not_available';

export interface FlightOrderStatus {
    state: FlightOrderState;
    /** The download page; only when ready */
    path: string | null;
    created_at: string | null;
    /** Only when failed: in words for the pilot */
    reason: string | null;
}

/** What to ask for; names only. Which keys are present says what is asked (see ContestantTaskCompilerStrategy.declaration_form). */
export interface DeclarationForm {
    /** 2.A2 and 2.A4: the points to give a time for */
    time_points?: string[];
    /** 2.A6 and 2.B2: the compulsory points, each with a time */
    compulsory_points?: string[];
    /** 2.A6 and 2.B2: the targets to put in order between them */
    targets?: string[];
    asks_for_fuel_endurance?: boolean;
    /** 2.A3: the points that are always flown, in order (SP, MP, FP) */
    mandatory_points?: string[];
    /** 2.A3: the turn points to choose from */
    turnpoints?: string[];
    asks_for_period?: boolean;
    declares_times?: boolean;
    /** The key of the declaration payload that holds the times */
    time_key?: string | null;
    adaptive_start?: boolean;
    /** When the start point is crossed (ISO); null with an adaptive start */
    start_point_time?: string | null;
}

export interface PilotDeclaration {
    contestant_id: number;
    contest_id: number;
    navigation_task_id: number;
    contest_name: string;
    navigation_task_name: string;
    time_zone: string;
    task_type: string;
    status: DeclarationStatus;
    read_only_reason: string | null;
    flight_order_status: FlightOrderStatus | null;
    declaration_payload: Record<string, any>;
    form: DeclarationForm;
}
