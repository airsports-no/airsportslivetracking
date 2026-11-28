import { getCookie } from '../../utils/csrf';
import { reverse } from '../../urls';
import { SavePayload } from './scorecardEditorLogic';
import { ScorecardData } from './types';
import { ScoringExplanation } from '../../utils/taskScore';

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

/**
 * The explanation of how the task is scored, with the editor's unsaved scoring values applied (a blank value is the task
 * type's default), so it can be shown to follow what the organiser is about to save.
 */
export async function fetchScoringExplanation(
    contestId: number,
    navigationTaskId: number,
    overrides: Record<string, string> = {},
): Promise<ScoringExplanation> {
    const query = new URLSearchParams(overrides).toString();
    const url = reverse('navigationtasks-scoring-explanation', contestId, navigationTaskId) + (query ? `?${query}` : '');
    const response = await fetch(url, { headers: { Accept: 'application/json' } });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to load the scoring explanation: ${errorMessages}`);
    }
    return response.json();
}
