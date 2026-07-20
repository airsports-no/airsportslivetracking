import { OngoingNavigation, PaginatedContests, MyParticipatingContest, Club, ClubManagerMembership, Aircraft, Copilot, ScheduleFlightPayload, RegisterTeamPayload, Contest, NavigationTask, ContestResults, MyContestTeam, Team } from './types';
import { Contestant } from '../competition-map/types';
import { getCookie } from '../../utils/csrf';
import { reverse } from '../../urls';

type ErrorMessage = string | string[];

async function getErrorMessages(response: Response): Promise<ErrorMessage> {
  try {
    const errorData = await response.json();
    if (Array.isArray(errorData) && errorData.every(item => typeof item === 'string')) {
      return errorData;
    } else if (typeof errorData === 'object' && errorData !== null && 'detail' in errorData) {
      return errorData.detail;
    }
    return JSON.stringify(errorData);
  } catch {
    return response.statusText;
  }
}

export const fetchMyContestTeams = async (): Promise<MyContestTeam[]> => {
    const url = reverse('userprofile-my-contest-teams');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        const error = new Error(`Failed to fetch my contest teams: ${errorMessages}`) as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};

export const fetchOngoingNavigation = async (): Promise<OngoingNavigation[]> => {
    const url = reverse('contests-ongoing-navigation');
    const response = await fetch(url);
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to fetch ongoing navigation tasks: ${errorMessages}`);
    }
    return response.json();
};

const getAuthHeaders = () => {
    return {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')!
    };
};

export interface ContestFilters {
    pks?: number[];
    startTimeGte?: string;
    finishTimeLte?: string;
    startTimeLte?: string;
    finishTimeGte?: string;
    isEditor?: boolean;
    excludeTasks?: boolean;
    excludeTeams?: boolean;
    publicOnly?: boolean;
    sharedOnly?: boolean;
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
    if (filters?.startTimeLte) {
        url.searchParams.set('start_time__lte', filters.startTimeLte);
    }
    if (filters?.finishTimeGte) {
        url.searchParams.set('finish_time__gte', filters.finishTimeGte);
    }
    if (filters?.isEditor !== undefined) {
        url.searchParams.set('is_editor', filters.isEditor.toString());
    }
    if (filters?.excludeTasks !== undefined) {
        url.searchParams.set('exclude_tasks', filters.excludeTasks.toString());
    }
    if (filters?.excludeTeams !== undefined) {
        url.searchParams.set('exclude_teams', filters.excludeTeams.toString());
    }
    if (filters?.publicOnly !== undefined) {
        url.searchParams.set('public_only', filters.publicOnly.toString());
    }
    if (filters?.sharedOnly !== undefined) {
        url.searchParams.set('shared_only', filters.sharedOnly.toString());
    }

    const response = await fetch(url.toString(), { headers: getAuthHeaders() });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to fetch contests: ${errorMessages}`);
    }
    return response.json();
};

export type OnContestPageFetched = (contests: Contest[], nextCursor: string | null) => void;

export const fetchContests = async (filters?: ContestFilters, onPageFetched?: OnContestPageFetched): Promise<Contest[]> => {
    let allContests: Contest[] = [];
    let nextCursor: string | null = null;
    let hasMore = true;

    while (hasMore) {
        const response = await _fetchContestsPage(nextCursor, filters);
        allContests = allContests.concat(response.results);
        nextCursor = response.next;
        hasMore = !!response.next;

        if (onPageFetched) {
            onPageFetched(response.results, response.next);
        }
    }

    return allContests;
};

export const fetchContestResults = async (contestId: number): Promise<ContestResults> => {
    const url = reverse('contests-results-details', contestId);
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        const error = new Error(`Failed to fetch contest results for ${contestId}: ${errorMessages}`) as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};

export const fetchMyFutureFlights = async (): Promise<Contestant[]> => {
    const url = reverse('userprofile-my-future-flights');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        const error = new Error(`Failed to fetch future flights: ${errorMessages}`) as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};

export const fetchMyPreviousFlights = async (): Promise<Contestant[]> => {
    const url = reverse('userprofile-my-previous-flights');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        const error = new Error(`Failed to fetch previous flights: ${errorMessages}`) as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};

export const fetchClubs = async (): Promise<Club[]> => {
    const url = reverse('clubs-list');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to fetch clubs: ${errorMessages}`);
    }
    return response.json();
};

export const fetchManagedClubs = async (): Promise<Club[]> => {
    const url = reverse('clubs-managed');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to fetch managed clubs: ${errorMessages}`);
    }
    return response.json();
};

export const addClubManager = async (clubId: number, identifier: string, role: string): Promise<ClubManagerMembership> => {
    const url = reverse('clubs-managers', clubId);
    const payload = /^\d+$/.test(identifier) ? { user_id: Number(identifier), role } : { user_id: identifier, role };
    const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to add club manager: ${errorMessages}`);
    }
    return response.json();
};

export const deactivateClubManager = async (clubId: number, membershipId: number): Promise<void> => {
    const url = reverse('clubs-manager-detail', clubId, membershipId);
    const response = await fetch(url, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to remove club manager: ${errorMessages}`);
    }
};

export const fetchAircrafts = async (): Promise<Aircraft[]> => {
    const url = reverse('aircraft-list');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to fetch aircrafts: ${errorMessages}`);
    }
    return response.json();
};

export const fetchPilots = async (): Promise<Copilot[]> => {
    const url = reverse('get_persons_for_signup');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to fetch pilots: ${errorMessages}`);
    }
    return response.json();
};

export const fetchTeam = async (teamId: number): Promise<Team> => {
    const url = reverse('teams-detail', teamId);
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        const error = new Error(`Failed to fetch team ${teamId}: ${errorMessages}`) as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};

export const registerForContest = async (payload: RegisterTeamPayload): Promise<any> => {
    const { contestId, ...apiPayload } = payload;
    const url = reverse('contests-signup', contestId);
    const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(apiPayload),
    });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to register for contest: ${errorMessages}`);
    }
    return response.json();
};

export const fetchContest = async (contestId: number): Promise<Contest> => {
    const url = reverse('contests-detail', contestId);
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        const error = new Error(`Failed to fetch contest ${contestId}: ${errorMessages}`) as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};

export const assignContestToken = async (contestId: number, tokenGrantId: number): Promise<any> => {
    const url = reverse('contests-assign-token', contestId);
    const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ token_grant_id: tokenGrantId }),
    });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to assign token to contest: ${errorMessages}`);
    }
    return response.json();
};

export const replaceContestToken = async (contestId: number, tokenGrantId: number): Promise<any> => {
    const url = reverse('contests-replace-token', contestId);
    const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ token_grant_id: tokenGrantId }),
    });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to replace token on contest: ${errorMessages}`);
    }
    return response.json();
};

export const scheduleFlight = async (contestId: number, navigationTaskId: number, payload: ScheduleFlightPayload): Promise<Contestant> => {
    const url = reverse('navigationtasks-contestant-self-registration', contestId, navigationTaskId);
    const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to schedule flight: ${errorMessages}`);
    }
    if (response.status === 204) {
        return undefined as any;
    }
    return response.json();
};

export const cancelFlight = async (contestId: number, navigationTaskId: number, futureContestantId: number): Promise<void> => {
    const url = reverse('navigationtasks-delete-self-managed-contestant', contestId, navigationTaskId, futureContestantId);
    const response = await fetch(url, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to cancel flight: ${errorMessages}`);
    }
};

export const withdraw = async (contestId: number): Promise<void> => {
    const url = reverse('contests-withdraw', contestId);
    const response = await fetch(url, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to withdraw from contest: ${errorMessages}`);
    }
};
