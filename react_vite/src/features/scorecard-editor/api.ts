import { getCookie } from '../../utils/csrf';
import { reverse } from '../../urls';
import { SavePayload } from './scorecardEditorLogic';
import { ScorecardData } from './types';

type ErrorMessage = string | string[];

async function getErrorMessages(response: Response): Promise<ErrorMessage> {
    try {
        const errorData = await response.json();
        if (Array.isArray(errorData) && errorData.every((item) => typeof item === 'string')) {
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

export async function fetchScorecard(contestId: number, navigationTaskId: number): Promise<ScorecardData> {
    const url = reverse('navigationtasks-scorecard', contestId, navigationTaskId);
    const response = await fetch(url, { headers: { Accept: 'application/json' } });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to load scorecard: ${errorMessages}`);
    }
    return response.json();
}

export async function saveScorecard(
    contestId: number,
    navigationTaskId: number,
    payload: SavePayload,
): Promise<ScorecardData> {
    const url = reverse('navigationtasks-scorecard', contestId, navigationTaskId);
    const response = await fetch(url, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to save scorecard: ${errorMessages}`);
    }
    return response.json();
}

export async function resetScorecard(contestId: number, navigationTaskId: number): Promise<ScorecardData> {
    const url = reverse('navigationtasks-reset-scorecard', contestId, navigationTaskId);
    const response = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to reset scorecard: ${errorMessages}`);
    }
    return response.json();
}
