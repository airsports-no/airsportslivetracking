import { reverse } from '../../urls';

export type FlightStatsBin = 'hour' | 'day' | 'week' | 'month' | 'year';

export interface FlightStatsBucket {
    bucket_start: string;
    awaiting_start: number;
    flying: number;
    finished: number;
}

export interface UniquePersonsBucket {
    bucket_start: string;
    count: number;
}

export interface FlightStatsResponse {
    bin: FlightStatsBin;
    start: string;
    end: string;
    series: FlightStatsBucket[];
    unique_persons_series: UniquePersonsBucket[];
}

export const fetchAdminFlightStats = async (days: number, bin: FlightStatsBin): Promise<FlightStatsResponse> => {
    const url = `${reverse('admin-flight-stats-list')}?days=${days}&bin=${bin}`;
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) {
        throw new Error('Failed to fetch flight stats');
    }
    return response.json();
};

export interface UpcomingContestant {
    id: number;
    contest_id: number;
    contest_name: string;
    navigation_task_id: number;
    navigation_task_name: string;
    team: string;
    aeroplane: string;
    takeoff_time: string;
    contest_time_zone: string;
}

export const fetchUpcomingContestants = async (days: number): Promise<UpcomingContestant[]> => {
    const url = `${reverse('admin-upcoming-contestants-list')}?days=${days}`;
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) {
        throw new Error('Failed to fetch upcoming contestants');
    }
    return response.json();
};

export interface CountryStatsRow {
    country_code: string;
    country_name: string;
    contests: number;
    tasks: number;
    contestants: number;
    latitude: number | null;
    longitude: number | null;
}

export interface RepeatParticipationStats {
    total: number;
    returning: number;
    returning_pct: number;
    distribution: { contests: number | string; count: number }[];
}

export interface OverviewStats {
    number_of_persons: number;
    number_of_contests: number;
    number_of_tasks: number;
    number_of_contestants: number;
    number_of_countries_reached: number;
    total_gps_positions: number;
    total_anomalies: number;
    average_air_speed: number;
    number_of_started_contestants: number;
    number_of_contestants_crossed_starting: number;
    number_of_persons_crossed_starting: number;
    top_clubs: { name: string; count: number }[];
    top_aircraft_types: { type: string; count: number }[];
}

export interface SystemStatsResponse {
    overview: OverviewStats;
    country: CountryStatsRow[];
    task_type_popularity: { task_subtype: string; count: number }[];
    retention: {
        teams: RepeatParticipationStats;
        persons: RepeatParticipationStats;
        total_persons_ever_tracked: number;
    };
}

export const fetchAdminSystemStats = async (): Promise<SystemStatsResponse> => {
    const url = reverse('admin-system-stats-list');
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) {
        throw new Error('Failed to fetch system stats');
    }
    return response.json();
};

export interface ActivityTrendBucket {
    bucket_start: string;
    contests: number;
    tasks: number;
}

export interface ActivityTrendsResponse {
    bin: FlightStatsBin;
    start: string;
    end: string;
    series: ActivityTrendBucket[];
}

export const fetchAdminActivityTrends = async (days: number, bin: FlightStatsBin): Promise<ActivityTrendsResponse> => {
    const url = `${reverse('admin-activity-trends-list')}?days=${days}&bin=${bin}`;
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) {
        throw new Error('Failed to fetch activity trends');
    }
    return response.json();
};

export interface MobileAppVersionRow {
    platform: 'android' | 'ios' | 'msfs';
    app_version: string;
    app_build: string;
    users: number;
}

export interface MobileAppUserRow {
    name: string;
    email: string;
    platform: 'android' | 'ios' | 'msfs';
    app_version: string;
    app_build: string;
    last_seen: string;
    /** Where the phone last reported from, when the tracking stream has delivered a position (nothing is sent by the app for it). */
    position: { latitude: number; longitude: number; time: string } | null;
}

export interface MobileAppsResponse {
    window_minutes: number;
    total: number;
    by_version: MobileAppVersionRow[];
    users: MobileAppUserRow[];
}

/** The mobile apps that have talked to the server in the last [minutes] minutes, with their versions. */
export const fetchAdminMobileApps = async (minutes: number): Promise<MobileAppsResponse> => {
    const url = `${reverse('admin-mobile-apps-list')}?minutes=${minutes}`;
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) {
        throw new Error('Failed to fetch the mobile apps');
    }
    return response.json();
};

/** One flight of a person, as display/services/admin_user_flights.py describes it. */
export interface AdminUserFlight {
    id: number;
    contestant_number: number;
    contest_id: number;
    contest_name: string;
    navigation_task_id: number;
    navigation_task_name: string;
    task_type: string | null;
    role: 'pilot' | 'co-pilot';
    partner: string | null;
    aeroplane: string;
    flight_mode: string;
    takeoff_time: string;
    finished_by_time: string;
    calculator_started: boolean;
    calculator_finished: boolean;
    score: number | null;
    /** The styles of the AI summaries written of the flight's current scores. */
    summary_styles: string[];
}

export interface AdminUserFlightsResponse {
    person: { id: number; name: string; email: string; has_account: boolean };
    flights: AdminUserFlight[];
}

export const fetchAdminUserFlights = async (personId: number): Promise<AdminUserFlightsResponse> => {
    const response = await fetch(`${reverse('admin-user-flights-list')}?person=${personId}`, { cache: 'no-store' });
    if (!response.ok) {
        throw new Error(response.status === 404 ? 'No such person' : 'Failed to fetch the flights');
    }
    return response.json();
};
