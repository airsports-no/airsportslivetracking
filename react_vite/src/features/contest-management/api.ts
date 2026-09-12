import { getCookie } from '../../utils/csrf';
import { reverse } from '../../urls';
import { NavigationTaskCreatePayload, NavigationTaskCreateResponse, ScorecardChoice, TaskTemplatesResponse } from './types';

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
