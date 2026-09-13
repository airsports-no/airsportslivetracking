import { getCookie } from '../../utils/csrf';
import { reverse } from '../../urls';
import {
    AdminTeamRegistrationPayload,
    ContestTeamListItem,
    NavigationTaskCreatePayload,
    NavigationTaskCreateResponse,
    ScorecardChoice,
    TaskTemplatesResponse,
} from './types';
import { ContestCreationFormValues } from './schemas/contestCreationSchema';
import { Contest } from '../mission-dashboard/types';

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

const getAuthHeaders = () => ({
    'Content-Type': 'application/json',
    'X-CSRFToken': getCookie('csrftoken')!,
});

export const fetchTaskTemplates = async (editableRouteId?: number): Promise<TaskTemplatesResponse> => {
    let url = reverse('editableroutes-task-templates');
    if (editableRouteId) {
        url += `?editable_route=${editableRouteId}`;
    }
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Failed to fetch task templates: ${await getErrorMessages(response)}`);
    }
    return response.json();
};

export const fetchScorecardChoices = async (taskType?: string): Promise<ScorecardChoice[]> => {
    let url = reverse('scorecards-choices');
    if (taskType) {
        url += `?task_type=${encodeURIComponent(taskType)}`;
    }
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Failed to fetch scorecards: ${await getErrorMessages(response)}`);
    }
    return response.json();
};

export const createContest = async (payload: ContestCreationFormValues): Promise<Contest> => {
    const url = reverse('contests-list');
    const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        throw new Error(`Failed to create contest: ${await getErrorMessages(response)}`);
    }
    return response.json();
};

export const fetchContestTeams = async (contestId: number): Promise<ContestTeamListItem[]> => {
    const url = reverse('contests-teams', contestId);
    const response = await fetch(url, { headers: { 'Content-Type': 'application/json' } });
    if (!response.ok) {
        throw new Error(`Failed to fetch registered teams: ${await getErrorMessages(response)}`);
    }
    return response.json();
};

export const registerTeam = async (
    contestId: number,
    payload: AdminTeamRegistrationPayload
): Promise<ContestTeamListItem> => {
    const url = reverse('contests-register-team', contestId);
    const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        throw new Error(`Failed to register team: ${await getErrorMessages(response)}`);
    }
    return response.json();
};

export const removeTeamFromContest = async (contestId: number, contestTeamId: number): Promise<void> => {
    const url = reverse('contestteams-detail', contestId, contestTeamId);
    const response = await fetch(url, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    });
    if (!response.ok) {
        throw new Error(`Failed to remove team: ${await getErrorMessages(response)}`);
    }
};

export const importTeams = async (
    contestId: number,
    sourceContestId: number,
    teamIds?: number[]
): Promise<ContestTeamListItem[]> => {
    const url = reverse('contests-import-teams', contestId);
    const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ source_contest: sourceContestId, ...(teamIds ? { team_ids: teamIds } : {}) }),
    });
    if (!response.ok) {
        throw new Error(`Failed to import teams: ${await getErrorMessages(response)}`);
    }
    return response.json();
};

export const createNavigationTask = async (
    contestId: number,
    payload: NavigationTaskCreatePayload
): Promise<NavigationTaskCreateResponse> => {
    const url = reverse('navigationtasks-list', contestId);
    const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const error = new Error(`Failed to create navigation task: ${await getErrorMessages(response)}`) as Error & {
            status?: number;
        };
        error.status = response.status;
        throw error;
    }
    return response.json();
};
