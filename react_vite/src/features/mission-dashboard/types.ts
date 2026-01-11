import { Contest } from "../schedule-flight/types";

export interface ActiveContestant {
    id: number;
    gate_times: { [key: string]: string };
    scorecard_rules: any[];
    tracker_id_display: {
        tracker: string;
        has_user: boolean;
        is_active: boolean;
    }[];
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
    team: number;
}

export interface OngoingNavigation {
    pk: number;
    name: string;
    start_time: string;
    finish_time: string;
    tracking_link: string;
    active_contestants: ActiveContestant[];
    contest: Contest;
}
