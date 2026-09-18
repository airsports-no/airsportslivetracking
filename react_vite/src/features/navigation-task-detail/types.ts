// The competition-map and mission-dashboard features each keep their own (incomplete, mutually
// inconsistent) Contestant/NavigationTask types - see the "Deferred lint & verification backlog"
// project memory. Rather than fight that pre-existing duplication, this feature declares the
// narrow slice of the real REST payloads (navigationtasks-detail) it actually reads.

export interface TrackerIdDisplay {
  tracker: string;
  is_active: boolean;
  has_user: boolean;
}

export interface PersonName {
  first_name: string;
  last_name: string;
}

export interface TeamDisplay {
  crew: { member1: PersonName; member2: PersonName | null };
  aeroplane: { registration: string };
}

export interface ContestantRow {
  pk: number;
  contestant_number: number;
  team: TeamDisplay;
  contestanttrack: { current_state: string; calculator_finished: boolean };
  tracker_id_display: TrackerIdDisplay[];
  tracker_start_time: string;
  takeoff_time: string;
  finished_by_time: string;
  adaptive_start: boolean;
  has_crossed_starting_line: boolean;
  air_speed: number;
  wind_speed: number;
  wind_direction: number;
  overlap_warnings: string[];
  overlapping_tasks: { task_id: number; task_name: string; contest_id: number; reason: string }[];
  declaration_status: { required: boolean; complete: boolean };
}

export interface GuestCapacityStatus {
  guest_created_contestants: number;
  guest_started_slots: number;
  guest_capacity_limit: number | null;
  guest_capacity_full: boolean;
  show_guest_capacity_warning: boolean;
}

export interface NavigationTaskDetail {
  pk: number;
  name: string;
  start_time: string;
  finish_time: string;
  tracking_link: string;
  time_zone: string;
  task_subtype?: string | null;
  is_public: boolean;
  is_featured: boolean;
  user_has_change_permission: boolean;
  contestant_set: ContestantRow[];
  editable_route: number | null;
  minutes_to_starting_point: number;
  planning_time: number;
  minutes_to_landing: number;
  wind_speed: number;
  wind_direction: number;
  allow_self_management: boolean;
  calculation_delay_minutes: number;
  guest_capacity_status: GuestCapacityStatus;
  is_poker_run: boolean;
}

// known_circuit's editor (KnownCircuitForm, ContestantDeclarationPage.tsx) already existed
// before curve/precision navigation's did, but was missing from this list too - the declaration
// is optional there (every turnpoint override defaults to the uniform declared speed), but the
// editor to set overrides still needs to be reachable.
const DECLARATION_EDITABLE_SUBTYPES = [
  'turnpoint_hunt',
  'limited_fuel_turnpoint_hunt',
  'contract_navigation_time_controls',
  'curve_navigation_time_estimation',
  'precision_navigation',
  'known_circuit',
];

export const supportsDeclarationEditing = (taskSubtype?: string | null): boolean =>
  !!taskSubtype && DECLARATION_EDITABLE_SUBTYPES.includes(taskSubtype);
