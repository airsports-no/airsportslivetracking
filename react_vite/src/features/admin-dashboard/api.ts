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
}

export interface RepeatParticipationStats {
    total: number;
    returning: number;
    returning_pct: number;
    distribution: { contests: number | string; count: number }[];
}

export interface SystemStatsResponse {
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
