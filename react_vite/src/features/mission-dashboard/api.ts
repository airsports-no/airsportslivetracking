import { OngoingNavigation, PaginatedContests, MyParticipatingContest, Club, Aircraft, Copilot, ScheduleFlightPayload, RegisterTeamPayload, Contest, NavigationTask, ContestResults, MyContestTeam, Team } from './types';
import { Contestant } from '../competition-map/types';
import { getCookie } from '../../utils/csrf';
import { reverse } from '../../urls';


export const fetchMyContestTeams = async (): Promise<MyContestTeam[]> => {
    const url = reverse('userprofile-my-contest-teams');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const error = new Error('Failed to fetch my contest teams') as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};


export const fetchOngoingNavigation = async (): Promise<OngoingNavigation[]> => {
    // const url = reverse('ongoing_navigation');
    const url = '/api/v1/contests/ongoing_navigation/';
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error('Failed to fetch ongoing navigation tasks');
    }
    return response.json();
};

const getAuthHeaders = () => {
    // In a real app, you would get the token from a secure place.
    // For now, let's assume the browser handles cookies or auth headers automatically.
    return {
        'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')!
        // 'Authorization': `Bearer ${your_token_here}`
    };
};

let cachedContests: Contest[] | null = null;

export interface ContestFilters {
    pks?: number[];
    startTimeGte?: string;
    finishTimeLte?: string;
}

const _fetchContestsPage = async (cursor?: string | null, filters?: ContestFilters): Promise<PaginatedContests> => {
    const baseUrl = reverse('contests-list');
    const url = new URL(baseUrl, window.location.origin);
    if (cursor) {
        url.searchParams.set('cursor', cursor);
    }
    if (filters?.pks?.length) {
        url.searchParams.set('pks', filters.pks.join(','));
    }
    if (filters?.startTimeGte) {
        url.searchParams.set('start_time__gte', filters.startTimeGte);
    }
    if (filters?.finishTimeLte) {
        url.searchParams.set('finish_time__lte', filters.finishTimeLte);
    }

    const response = await fetch(url.toString(), { headers: getAuthHeaders() });
    if (!response.ok) {
        throw new Error('Failed to fetch contests');
    }
    return response.json();
};

export const fetchContests = async (filters?: ContestFilters): Promise<Contest[]> => {
    const hasFilters = filters && (filters.pks?.length || filters.startTimeGte || filters.finishTimeLte);

    if (!hasFilters && cachedContests) {
        return Promise.resolve(cachedContests);
    }

    let allContests: Contest[] = [];
    let nextCursor: string | null = null;
    let hasMore = true;

    while(hasMore) {
        const response = await _fetchContestsPage(nextCursor, filters);
        allContests = allContests.concat(response.results);
        nextCursor = response.next;
        hasMore = !!response.next;
    }

    if (!hasFilters) {
        cachedContests = allContests;
    }
    return allContests;
};

export const fetchContestResults = async (contestId: number): Promise<ContestResults> => {
    const url = reverse('contests-results-details', contestId);
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const error = new Error(`Failed to fetch contest results for ${contestId}`) as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};


export const fetchMyFutureFlights = async (): Promise<Contestant[]> => {
    const url = reverse('userprofile-my-future-flights');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const error = new Error('Failed to fetch future flights') as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};

export const fetchMyPreviousFlights = async (): Promise<Contestant[]> => {
    const url = reverse('userprofile-my-previous-flights');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const error = new Error('Failed to fetch previous flights') as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};

export const fetchClubs = async (): Promise<Club[]> => {
    const url = reverse('clubs-list');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        throw new Error('Failed to fetch clubs');
    }
    return response.json();
};

export const fetchAircrafts = async (): Promise<Aircraft[]> => {
    const url = reverse('aircraft-list');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        throw new Error('Failed to fetch aircrafts');
    }
    return response.json();
};

export const fetchPilots = async (): Promise<Copilot[]> => {
    const url = reverse('get_persons_for_signup');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        throw new Error('Failed to fetch pilots');
    }
    return response.json();
};

export const fetchTeam = async (teamId: number): Promise<Team> => {
    const url = reverse('teams-detail', teamId);
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const error = new Error(`Failed to fetch team ${teamId}`) as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};

export const registerForContest = async (payload: RegisterTeamPayload): Promise<any> => {
    const { contestId, ...apiPayload } = payload;
    const url = reverse("contests-signup", contestId);
    const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(apiPayload),
    });
    if (!response.ok) {
        throw new Error('Failed to register for contest');
    }
    return response.json();
};


export const fetchContest = async (contestId: number): Promise<Contest> => {
    const url = reverse('contests-detail', contestId);
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const error = new Error(`Failed to fetch contest ${contestId}`) as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};

export const scheduleFlight = async (contestId: number, navigationTaskId: number, payload: ScheduleFlightPayload): Promise<any> => {
    const url = reverse('navigationtasks-contestant-self-registration', contestId, navigationTaskId);
    const response = await fetch(url,
        {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(payload),
        }
    );
    if (!response.ok) {
        throw new Error('Failed to schedule flight');
    }
    if (response.status === 201 || response.status === 204) {
        return; // Resolve with undefined, as there's no JSON body
    }
    return response.json();
};

export const cancelFlight = async (contestId: number, navigationTaskId: number, futureContestantId: number): Promise<void> => {
    const url = reverse('navigationtasks-delete-self-managed-contestant', contestId, navigationTaskId, futureContestantId);
    const response = await fetch(url,
        {
            method: 'DELETE',
            headers: getAuthHeaders(),
        }
    );
    if (!response.ok) {
        throw new Error('Failed to cancel flight');
    }
};

export const withdraw = async (contestId: number): Promise<void> => {
    const url = reverse('contests-withdraw', contestId);
    const response = await fetch(url, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    });
    if (!response.ok) {
        throw new Error('Failed to withdraw from contest');
    }
    if (response.status === 204) {
        return; // No content expected for a successful DELETE
    }
    // Optionally, if the backend might return JSON even for DELETE, handle it here.
    // For now, assuming no content for 204.
};