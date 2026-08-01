// Types for Navigation Task live competition map

export interface Aeroplane {
  id: number;
  registration: string;
  colour: string | null;
  type: string | null;
  picture?: string | null;
}

export interface Member {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  country?: string | null;
  picture?: string | null;
}

export interface Crew {
  id: number;
  member1: Member;
  member2?: Member | null;
}

export interface Club {
  id: number;
  country_flag_url?: string | null;
  country?: string | null;
  name: string;
  logo?: string | null;
}

export interface Team {
  id: number;
  aeroplane: Aeroplane;
  country: string | null;
  crew: Crew;
  club: Club;
  logo?: string | null;
}

export interface ContestantTrackSummary {
  id: number;
  contest_summary: number;
  score: number;
  current_state: string;
  current_leg: string | null;
  last_gate: string | null;
  last_gate_time_offset: number | null;
  passed_starting_gate: boolean;
  passed_finish_gate: boolean;
  calculator_finished: boolean;
  calculator_started: boolean;
  contestant: number;
  progress?: number;
  last_position_received_at?: number;
}

export interface TrackerDisplay {
  tracker: string;
  has_user: boolean;
  is_active: boolean;
}

export interface Contest {
    id: number;
    name: string;
    logo: string;
    country_flag_url?: string | null;
    country: string;
    start_time: string;
    finish_time: string;
    location: string;
    contest_website?: string;
}

export interface Waypoint {
  name: string;
  latitude: number;
  longitude: number;
  elevation: number;
  width: number;
  gate_line: [number, number][];
  gate_line_extended?: [number, number][];
  time_check: boolean;
  gate_check: boolean;
  end_curved: boolean;
  type: string;
  distance_next: number;
  distance_previous: number;
  bearing_next: number;
  bearing_from_previous: number;
  procedure_turn_points?: [number, number][];
  is_procedure_turn: boolean;
  is_steep_turn?: boolean;
  outer_corner_position?: any[];
}

export interface ProhibitedZone {
  id: number;
  name: string;
  type: 'prohibited' | 'penalty' | 'info' | 'gate';
  path: [number, number][];
  tooltip_position?: [number, number];
}

export interface Photo {
  id: number;
  name: string;
  route: number;
  latitude: number;
  longitude: number;
  file: string | null;
}

export interface RouteData {
  id: number;
  name: string;
  use_procedure_turns: boolean;
  rounded_corners: boolean;
  corridor_width: number;
  waypoints: Waypoint[];
  takeoff_gates: Waypoint[];
  landing_gates: Waypoint[];
  corridor_polygon?: { lat: number; lng: number }[];
  prohibited_set: ProhibitedZone[];
  photo_set: Photo[];
}

export interface GateScoreRule {
  gate_type: string;
  graceperiod_before: number;
  graceperiod_after: number;
  penalty_per_second: number;
  maximum_penalty: number;
  maximum_timing_penalty?: number;
  missed_penalty: number;
  missed_procedure_turn_penalty?: number;
  extended_gate_width?: number;
  bad_crossing_extended_gate_penalty?: number;
}

export interface Scorecard {
  gatescore_set: GateScoreRule[];
  task_type: string[];
  initial_score?: number;
  corridor_width?: number;
  corridor_outside_penalty?: number;
  corridor_grace_time?: number;
  corridor_maximum_penalty?: number;
  prohibited_zone_penalty?: number;
  penalty_zone_penalty_per_second?: number;
  penalty_zone_grace_time?: number;
  penalty_zone_maximum?: number;
  backtracking_bearing_difference?: number;
  backtracking_grace_time_seconds?: number;
  backtracking_penalty?: number;
  backtracking_maximum_penalty?: number;
}

export interface Contestant {
  id: number;
  contest_id: number;
  declaration_payload?: Record<string, any>;
  compiled_effective_route_payload?: Record<string, any>;
  team: Team;
  contestanttrack: ContestantTrackSummary;
  contestant_number: number;
  track_version: number;
  score_version: number;
  air_speed: number;
  wind_speed: number;
  wind_direction: number;
  gate_times?: Record<string, string>;
  default_map_url?: string;
  tracker_id_display?: TrackerDisplay[];
  playing_cards?: { card?: string; rank?: string; suit?: string; id?: number; waypoint?: string; card_string?: string; card_value?: string; card_suit?: string }[];
  navigation_task: NavigationTask;
  takeoff_time: string;
  tracker_start_time: string;
  first_position_time?: string | null;
  last_position_time?: string | null;
  finished_by_time: string;
  adaptive_start?: boolean;
  has_crossed_starting_line: boolean;
  progress?: number;
  last_position_received_at?: number;
  latest_emaillink?: { url: string; created_at: string };
  overlap_warnings?: string[];
  overlapping_tasks?: {
    task_id: number;
    task_name: string;
    contest_id: number;
    reason: string;
  }[];
}

export interface NavigationTaskCatalogueTarget {
  name: string;
  coordinates: [number, number];
  kind?: "catalogue_turnpoint" | "circle_center_marker" | "circle_start_marker" | "circle_entry_marker" | "circle_exit_marker";
}

export interface NavigationTask {
  id: number;
  route: RouteData;
  task_catalogue_targets?: NavigationTaskCatalogueTarget[];
  scorecard: Scorecard;
  contestant_set: Contestant[];
  task_subtype?: string | null;
  task_config?: Record<string, any>;
  task_information?: {
    family_display_name: string;
    subtype_key?: string | null;
    subtype_display_name: string;
    objective: string;
    summary: string[];
    scoring: string[];
    penalties: string[];
    overrides: string[];
  };
  task_subtype_definition?: {
    key: string;
    display_name: string;
    coarse_family: string;
    requires_contestant_configuration: boolean;
  } | null;
  name: string;
  display_background_map: boolean;
  display_secrets: boolean;
  display_contestant_rank_summary: boolean;
  time_zone: string;
  contest: Contest;
  score_sorting_direction: "asc" | "desc";
  calculation_delay_minutes: number;
  user_has_change_permission: boolean;
  allow_self_management: boolean;
  start_time: string;
  finish_time: string;
  tracking_link: string;
  pk: number;
  future_contestants: any[];
}

export interface TrackPosition {
  time: string; // ISO string
  latitude: number;
  longitude: number;
  speed?: number;
  course?: number;
  altitude?: number;
  progress?: number;
  interpolated?: boolean;
}

export interface PaginatedTrackResponse {
  next: string | null;
  previous: string | null;
  results: TrackPosition[];
}

export interface ScoreAnnotation {
  id: number;
  time: string;
  latitude: number;
  longitude: number;
  message: string;
  gate: string;
  gate_type: string;
  type: "anomaly" | "information" | string;
  contestant: number;
  score_log_entry: number | null;
}

export interface ScoreLogEntry {
  id: number;
  time: string;
  gate: string;
  message: string;
  string: string;
  points: number;
  planned?: string | null;
  actual?: string | null;
  offset_string?: string | null;
  type: "anomaly" | "information" | string;
  contestant: number;
}

export interface ContestantScoreData {
  contestant_id: number;
  positions: TrackPosition[];
  annotations: ScoreAnnotation[];
  score_log_entries: ScoreLogEntry[];
  gate_scores: { id: number; gate: string; points: number; contestant: number }[];
  contestant_track: ContestantTrackSummary;
  playing_cards?: { card?: string; rank?: string; suit?: string; id?: number; waypoint?: string; card_string?: string; card_value?: string; card_suit?: string }[];
}

export interface GateArrowData {
  waypoint_name: string;
  seconds_to_planned_crossing: number;
  estimated_crossing_offset: number; // seconds (+/-)
  estimated_score: number;
  final: boolean;
  missed: boolean;
}

export interface DangerData {
  accumulated_score: number;
  danger_level: number; // 0-100
}

export type LiveTrackMessage =
  | { type: "current_time"; data: string }
  | { type: "contestant"; data: string } // JSON string of contestant
  | { type: "contestant_delete"; data: string }
  | { type: "position"; data: string } // JSON string of position payload incl. contestant_id
  | { type: "gate_distance_and_estimate"; data: string } // JSON string of GateArrowData & contestant_id
  | { type: "danger_level"; data: string } // JSON string of DangerData & contestant_id
  | { type: string; data: string }; // fallback

