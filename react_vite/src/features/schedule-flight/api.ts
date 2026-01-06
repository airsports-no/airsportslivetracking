import { PaginatedContests, MyParticipatingContest, Club, Aircraft, Copilot, ScheduleFlightPayload, RegisterTeamPayload, Contest, NavigationTask } from './types';
import { getCookie } from '../../utils/csrf';
import { reverse } from '../../urls';

const getAuthHeaders = () => {
    // In a real app, you would get the token from a secure place.
    // For now, let's assume the browser handles cookies or auth headers automatically.
    return {
        'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')!
        // 'Authorization': `Bearer ${your_token_here}`
    };
};

export const fetchContests = async (cursor?: string | null): Promise<PaginatedContests> => {
    const baseUrl = reverse('contests-list');
    const url = new URL(baseUrl, window.location.origin);
    if (cursor) {
        url.searchParams.set('cursor', cursor);
    }

    const response = await fetch(url.toString(), { headers: getAuthHeaders() });
    if (!response.ok) {
        throw new Error('Failed to fetch contests');
    }
    return response.json();
};

export const fetchMyParticipatingContests = async (): Promise<MyParticipatingContest[]> => {
    const url = reverse('userprofile-my-participating-contests');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const error = new Error('Failed to fetch participating contests') as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};

export const fetchMyParticipatedContests = async (): Promise<NavigationTask[]> => {
    const url = reverse('userprofile-my-participated-contests');
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const error = new Error('Failed to fetch participated contests') as any;
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
