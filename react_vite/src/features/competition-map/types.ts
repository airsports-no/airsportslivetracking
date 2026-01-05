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
}

export interface TrackerDisplay {
  tracker: string;
  has_user: boolean;
  is_active: boolean;
}

export interface Contestant {
  id: number;
  team: Team;
  contestanttrack: ContestantTrackSummary;
  contestant_number: number;
  air_speed: number;
  wind_speed: number;
  wind_direction: number;
  gate_times?: Record<string, string>;
  default_map_url?: string;
  tracker_id_display?: TrackerDisplay[];
  playing_cards?: { card: string }[];
}

export interface GateLine {
  // gate_line and gate_line_extended are [ [lat, lng], [lat, lng] ]
  0: [number, number];
  1: [number, number];
}

export interface Waypoint {
  name: string;
  latitude: number;
  longitude: number;
  elevation: number;
  width: number;
  gate_line: GateLine;
  gate_line_extended: GateLine;
  time_check: boolean;
  gate_check: boolean;
  end_curved: boolean;
  type: "sp" | "tp" | "secret" | "fp";
  distance_next: number;
  distance_previous: number;
  bearing_next: number;
  bearing_from_previous: number;
  is_procedure_turn: boolean;
}

export interface ProhibitedZone {
  id: number;
  path: [number, number][]; // [lng, lat] coordinate pairs from API; will convert to [lat, lng]
  name: string;
  type: "prohibited" | "penalty";
  tooltip_position: [number, number] | null;
  route: number;
}

export interface CorridorPoint {
  lat: number;
  lng: number;
  source_index: number;
}

export interface RouteData {
  id: number;
  name: string;
  waypoints: Waypoint[];
  landing_gates: any[];
  takeoff_gates: any[];
  prohibited_set: ProhibitedZone[];
  corridor_polygon: CorridorPoint[];
  corridor_width: number;
}

export interface GateScoreRule {
  gate_type: "dummy" | "fp" | "ldg" | "secret" | "sp" | "to" | "tp" | "ul";
  graceperiod_before: number;
  graceperiod_after: number;
  maximum_penalty: number;
  penalty_per_second: number;
  missed_penalty: number;
  maximum_timing_penalty?: number;
  missed_procedure_turn_penalty?: number;
  extended_gate_width?: number;
  bad_crossing_extended_gate_penalty?: number;
}

export interface Scorecard {
  gatescore_set: GateScoreRule[];
  corridor_width: number;
  task_type: string[];
  shortcut_name: string;
  valid_from: string;
  free_text: string;
  initial_score: number;
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

export interface NavigationTask {
  id: number;
  route: RouteData;
  scorecard: Scorecard;
  contestant_set: Contestant[];
  name: string;
  display_background_map: boolean;
  display_secrets: boolean;
  display_contestant_rank_summary: boolean;
  time_zone: string;
  contest: number;
  score_sorting_direction: "asc" | "desc";
  calculation_delay_minutes: number;
  user_has_change_permission: boolean;
  allow_self_management: boolean;
  
}

export interface TrackPosition {
  time: string; // ISO string
  latitude: number;
  longitude: number;
  speed?: number;
  course?: number;
  altitude?: number;
  progress?: number;
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