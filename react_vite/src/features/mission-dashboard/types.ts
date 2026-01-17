export interface Contest {
    id: number;
    time_zone: string;
    navigationtask_set: NavigationTask[];
    contest_team_count: number;
    share_string: string;
    country_flag_url: string;
    country: string;
    registered: boolean;
    latitude: number;
    longitude: number;
    is_editor: boolean;
    summary_score_sorting_direction: string;
    autosum_scores: boolean;
    name: string;
    location: string;
    start_time: string;
    finish_time: string;
    is_public: boolean;
    is_featured: boolean;
    contest_website: string;
    header_image: string;
    logo: string;
    contest_teams: number[];
}

export interface Route {
    id: number;
    name: string;
    number_of_wayoints: number;
    route_length_nm: number;
    number_of_prohibited_zones: number;
    number_of_penalty_zones: number;
    has_landing_gate: boolean;
    has_takeoff_gate: boolean;
    number_of_photos: number;
}

export interface NavigationTask {
    pk: number;
    name: string;
    start_time: string;
    finish_time: string;
    tracking_link: string;
    allow_self_management: boolean;
    future_contestants?: any[];
    contestant_set: ContestantResult[];
    score_sorting_direction: 'asc' | 'desc';
    user_has_change_permission: boolean;
    calculation_delay_minutes?: number;
    contest: Contest;
    route: Route;
    flown_contestants_count: number;
    is_public: boolean;
    is_featured: boolean;
}

export interface MyContestTeam {
    id: number;
    air_speed: number;
    tracking_service: string;
    tracking_device: string;
    tracker_device_id: string;
    contest: number;
    team: number;
    is_user_pilot: boolean; // Added property
}

export interface MyParticipatingContest {
    id: number;
    contest: Contest;
    team: Team;
    can_edit: boolean;
    air_speed: number;
    tracking_service: string;
    tracking_device: string;
    tracker_device_id: string | null;
}

export interface Team {
    id: number;
    country_flag_url: string | null;
    aeroplane: Aeroplane;
    country: string;
    crew: Crew;
    club: Club;
    logo: string | null;
}

export interface Aeroplane {
    id: number;
    registration: string;
    colour: string;
    type: string;
    picture: string;
}

export interface Crew {
    id: number;
    member1: Person;
    member2: Person | null;
}

export interface Person {
    id: number;
    phone: string;
    first_name: string;
    last_name: string;
    email: string;
    creation_time: string;
    validated: boolean;
    app_aircraft_registration: string;
    picture: string;
    biography: string;
    country: string;
    is_public: boolean;
    last_seen: string;
}

export interface Club {
    id: number;
    country_flag_url: string;
    country: string;
    name: string;
    logo: string;
}

export interface TrackerIdDisplay {
    tracker: string;
    has_user: boolean;
    is_active: boolean;
}

export interface PaginatedContests {
    count: number;
    next: string | null;
    previous: string | null;
    results: Contest[];
}

export interface Aircraft {
    id: number;
    registration: string;
    colour: string;
    type: string;
    picture: string | null;
}

export interface Copilot {
    id: number;
    first_name: string;
    last_name: string;
    email: string;
}

export interface ScheduleFlightPayload {
    starting_point_time: string;
    contest_team: number;
    adaptive_start: boolean;
    wind_speed: number;
    wind_direction: number;
}

export interface RegisterTeamPayload {
    club_name: string;
    aircraft_registration: string;
    airspeed: number;
    copilot_id: number | null;
    contestId: number;
}

export interface ContestantTrack {
    id: number;
    contest_summary: number | null;
    score: number;
    current_state: string;
    current_leg: string;
    last_gate: string;
    last_gate_time_offset: number;
    passed_starting_gate: boolean;
    passed_finish_gate: boolean;
    calculator_finished: boolean;
    calculator_started: boolean;
    contestant: number;
}

export interface ContestantResult {
    id: number;
    gate_times: { [key: string]: string };
    scorecard_rules: any[];
    tracker_id_display: TrackerIdDisplay[];
    default_map_url: string;
    has_crossed_starting_line: boolean;
    team: Team;
    contestanttrack: ContestantTrack;
    adaptive_start: boolean;
    takeoff_time: string;
    minutes_to_starting_point: number;
    finished_by_time: string;
    air_speed: number;
    track_version: number;
    contestant_number: number;
    tracking_service: string;
    tracking_device: string;
    tracker_device_id: string;
    tracker_start_time: string;
    competition_class_longform: string | null;
    competition_class_shortform: string | null;
    wind_speed: number;
    wind_direction: number;
    annotation_index: number;
    has_been_tracked_by_simulator: boolean;
}

export interface Contestant {
    id: number;
    contest_id: number;
    navigation_task: number;
    gate_times: { [key: string]: string };
    scorecard_rules: any[];
    tracker_id_display: TrackerIdDisplay[];
    default_map_url: string;
    has_crossed_starting_line: boolean;
    adaptive_start: boolean;
    takeoff_time: string;
    minutes_to_starting_point: number;
    finished_by_time: string;
    air_speed: number;
    track_version: number;
    contestant_number: number;
    tracking_service: string;
    tracking_device: string;
    tracker_device_id: string;
    tracker_start_time: string;
    competition_class_longform: string | null;
    competition_class_shortform: string | null;
    wind_speed: number;
    wind_direction: number;
    annotation_index: number;
    has_been_tracked_by_simulator: boolean;
    team: Team;

}

export interface OngoingNavigation {

    pk: number;

    name: string;

    start_time: string;

    finish_time: string;

    tracking_link: string;

    active_contestants: Contestant[];

    contest: Contest;

}



export interface ContestSummary {

    id: number;

    team: Team;

    points: number;

    contest: number;

}



export interface ContestResults {
    id: number;
    contestsummary_set: ContestSummary[];
    summary_score_sorting_direction: 'asc' | 'desc';
}
