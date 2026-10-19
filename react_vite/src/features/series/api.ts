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

export interface SeriesRequest {
    id: number;
    series_id: number;
    series_name: string;
    contest_id: number;
    contest_name: string;
    from_side: 'series' | 'contest';
    status: string;
    requested_by_name: string;
    created_at: string;
    can_answer: boolean;
    can_cancel: boolean;
}

/** What asking for a contest to join a series led to: it was added at once, or the other side has to answer */
export type EnrolmentOutcome = { added: true; leg: SeriesLeg } | { added: false; request: SeriesRequest };

export interface ContestSearchResult {
    id: number;
    name: string;
    start_time: string;
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

/**
 * Get a contest into a series: added at once by somebody who manages both, otherwise the managers of the other side get
 * a request to answer.
 */
export const enrolContest = async (seriesId: number, contestId: number): Promise<EnrolmentOutcome> => {
    const response = await fetch(reverse('series-requests-list'), { headers: headers(), ...send('POST', { series: seriesId, contest: contestId }) });
    if (!response.ok) {
        throw new Error(await errorMessage(response));
    }
    const data = await response.json();
    return response.status === 201 ? { added: true, leg: data } : { added: false, request: data };
};

export const fetchSeriesRequests = (filter: { series?: number; contest?: number } = {}) => {
    const params = new URLSearchParams();
    if (filter.series) params.set('series', String(filter.series));
    if (filter.contest) params.set('contest', String(filter.contest));
    const query = params.toString();
    return request<SeriesRequest[]>(`${reverse('series-requests-list')}${query ? `?${query}` : ''}`);
};

export const acceptSeriesRequest = (requestId: number) =>
    request<SeriesLeg>(reverse('series-requests-accept', requestId), send('POST'));

export const declineSeriesRequest = (requestId: number) =>
    request<void>(reverse('series-requests-decline', requestId), send('POST'));

export const cancelSeriesRequest = (requestId: number) =>
    request<void>(reverse('series-requests-cancel', requestId), send('POST'));

export const fetchSeriesOfContest = (contestId: number) => request<Series[]>(`${reverse('series-list')}?contest=${contestId}`);

/** Contests anybody may see, found by part of the name */
export const searchContests = async (name: string): Promise<ContestSearchResult[]> => {
    const params = new URLSearchParams({ search: name, public_only: 'true', exclude_tasks: 'true', exclude_teams: 'true' });
    const data = await request<{ results: ContestSearchResult[] }>(`${reverse('contests-list')}?${params.toString()}`);
    return data.results;
};

export const updateLeg = (seriesId: number, contestId: number, change: { leg_number?: number; weight?: number }) =>
    request<SeriesLeg>(reverse('series-contest', seriesId, contestId), send('PATCH', change));

export const removeContestFromSeries = (seriesId: number, contestId: number) =>
    request<void>(reverse('series-contest', seriesId, contestId), send('DELETE'));
