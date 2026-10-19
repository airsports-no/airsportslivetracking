import { getCookie } from '../../utils/csrf';
import { reverse } from '../../urls';

export type ScoringMethod = 'placements' | 'points_table';
export type EntrantIdentity = 'pilot' | 'crew';

export interface Series {
    id: number;
    name: string;
    description: string;
    is_public: boolean;
    scoring_method: ScoringMethod;
    entrant_identity: EntrantIdentity;
    best_results_counted: number | null;
    points_table: number[];
    created_at: string;
    can_manage: boolean;
    leg_count: number;
}

export interface SeriesLeg {
    contest_id: number;
    name: string;
    start_time: string;
    is_public: boolean;
    leg_number: number;
    weight: number;
}

export interface SeriesDetail extends Series {
    legs: SeriesLeg[];
}

export type LegStatus = 'ranked' | 'no_result' | 'absent';

export interface StandingsCell {
    contest_id: number;
    status: LegStatus;
    placement: number | null;
    score: number | null;
    points: number;
    counted: boolean;
}

export interface StandingsRow {
    rank: number;
    total: number;
    entrant: { key: string; name: string; country: string; club: string };
    legs: StandingsCell[];
}

export interface Standings {
    id: number;
    name: string;
    scoring_method: ScoringMethod;
    entrant_identity: EntrantIdentity;
    best_results_counted: number | null;
    legs: { contest_id: number; name: string; weight: number }[];
    rows: StandingsRow[];
}

export interface AddableContest {
    id: number;
    name: string;
    start_time: string;
    is_public: boolean;
}

export type SeriesSettings = Partial<
    Pick<Series, 'name' | 'description' | 'is_public' | 'scoring_method' | 'entrant_identity' | 'best_results_counted' | 'points_table'>
>;

const headers = () => ({
    'Content-Type': 'application/json',
    'X-CSRFToken': getCookie('csrftoken')!,
});

async function errorMessage(response: Response): Promise<string> {
    try {
        const data = await response.json();
        if (Array.isArray(data)) return data.join(' ');
        if (data && typeof data === 'object') {
            if ('detail' in data) return String(data.detail);
            return Object.entries(data)
                .map(([field, messages]) => `${field}: ${[messages].flat().join(' ')}`)
                .join(' ');
        }
    } catch {
        // fall through to the status text
    }
    return response.statusText;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
    const response = await fetch(url, { headers: headers(), ...init });
    if (!response.ok) {
        throw new Error(await errorMessage(response));
    }
    return response.status === 204 ? (undefined as T) : response.json();
}

const send = (method: string, body?: unknown): RequestInit => ({
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
});

export const fetchSeriesList = () => request<Series[]>(reverse('series-list'));

export const createSeries = (settings: SeriesSettings) => request<Series>(reverse('series-list'), send('POST', settings));

export const fetchSeries = (seriesId: number) => request<SeriesDetail>(reverse('series-detail', seriesId));

export const updateSeries = (seriesId: number, settings: SeriesSettings) =>
    request<Series>(reverse('series-detail', seriesId), send('PATCH', settings));

export const deleteSeries = (seriesId: number) => request<void>(reverse('series-detail', seriesId), send('DELETE'));

export const fetchStandings = (seriesId: number) => request<Standings>(reverse('series-standings', seriesId));

export const fetchAddableContests = (seriesId: number) =>
    request<AddableContest[]>(reverse('series-addable-contests', seriesId));

export const addContestToSeries = (seriesId: number, contestId: number) =>
    request<SeriesLeg>(reverse('series-contests', seriesId), send('POST', { contest: contestId }));

export const updateLeg = (seriesId: number, contestId: number, change: { leg_number?: number; weight?: number }) =>
    request<SeriesLeg>(reverse('series-contest', seriesId, contestId), send('PATCH', change));

export const removeContestFromSeries = (seriesId: number, contestId: number) =>
    request<void>(reverse('series-contest', seriesId, contestId), send('DELETE'));
