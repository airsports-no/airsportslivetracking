import { reverse } from '../../urls';

export type FlightStatsBin = 'hour' | 'day' | 'week' | 'month' | 'year';

export interface FlightStatsBucket {
    bucket_start: string;
    awaiting_start: number;
    flying: number;
    finished: number;
}

export interface UniquePersonsDay {
    date: string;
    count: number;
}

export interface FlightStatsResponse {
    bin: FlightStatsBin;
    start: string;
    end: string;
    series: FlightStatsBucket[];
    unique_persons_per_day: UniquePersonsDay[];
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
