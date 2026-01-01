import { PaginatedContests, MyParticipatingContest, Club, Aircraft, Copilot, ScheduleFlightPayload, RegisterTeamPayload, Contest, NavigationTask } from './types';
import { getCookie } from '../../utils/csrf';


const API_BASE_URL = '/api/v1/';

const getAuthHeaders = () => {
    // In a real app, you would get the token from a secure place.
    // For now, let's assume the browser handles cookies or auth headers automatically.
    return {
        'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')!
        // 'Authorization': `Bearer ${your_token_here}`
    };
};

export const fetchContests = async (url: string): Promise<PaginatedContests> => {
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        throw new Error('Failed to fetch contests');
    }
    return response.json();
};

export const fetchMyParticipatingContests = async (url: string): Promise<MyParticipatingContest[]> => {
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const error = new Error('Failed to fetch participating contests') as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};

export const fetchMyParticipatedContests = async (url: string): Promise<NavigationTask[]> => {
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (!response.ok) {
        const error = new Error('Failed to fetch participated contests') as any;
        error.status = response.status;
        throw error;
    }
    return response.json();
};

export const fetchClubs = async (): Promise<Club[]> => {
    const response = await fetch(`${API_BASE_URL}clubs/`, { headers: getAuthHeaders() });
    if (!response.ok) {
        throw new Error('Failed to fetch clubs');
    }
    return response.json();
};

export const fetchAircrafts = async (): Promise<Aircraft[]> => {
    const response = await fetch(`${API_BASE_URL}aircraft/`, { headers: getAuthHeaders() });
    if (!response.ok) {
        throw new Error('Failed to fetch aircrafts');
    }
    return response.json();
};

export const fetchPilots = async (): Promise<Copilot[]> => {
    const response = await fetch(`/display/api/person/signuplist/`, { headers: getAuthHeaders() });
    if (!response.ok) {
        throw new Error('Failed to fetch pilots');
    }
    return response.json();
};

export const registerForContest = async (payload: RegisterTeamPayload): Promise<any> => {
    const { contestId, ...apiPayload } = payload;
    const response = await fetch(document.configuration.contestSignUpUrl(contestId), {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(apiPayload),
    });
    if (!response.ok) {
        throw new Error('Failed to register for contest');
    }
    return response.json();
};


export const scheduleFlight = async (contestId: number, navigationTaskId: number, payload: ScheduleFlightPayload): Promise<any> => {
    const response = await fetch(
        `${API_BASE_URL}contests/${contestId}/navigationtasks/${navigationTaskId}/contestant_self_registration/`,
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
    const response = await fetch(
        `${API_BASE_URL}contests/${contestId}/navigationtasks/${navigationTaskId}/delete_self_managed_contestant/${futureContestantId}/`,
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
    const response = await fetch(`${API_BASE_URL}contests/${contestId}/withdraw/`, {
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
