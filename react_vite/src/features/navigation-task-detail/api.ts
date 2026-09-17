import { reverse } from '../../urls';
import { getCookie } from '../../utils/csrf';

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

export type NavigationTaskVisibility = 'public' | 'private' | 'unlisted';

export async function fetchRunningCalculators(navigationTaskId: number): Promise<[number, boolean][]> {
  const url = reverse('navigationtask_getrunningcalculators', navigationTaskId);
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to fetch calculator running status: ${errorMessages}`);
  }
  return response.json();
}

async function postContestantAction(
  actionUrlName: string,
  contestId: number,
  navigationTaskId: number,
  contestantId: number,
  failureVerb: string
): Promise<void> {
  const url = reverse(actionUrlName, contestId, navigationTaskId, contestantId);
  const response = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to ${failureVerb}: ${errorMessages}`);
  }
}

export const terminateCalculator = (contestId: number, navigationTaskId: number, contestantId: number) =>
  postContestantAction('contestants-terminate', contestId, navigationTaskId, contestantId, 'stop the calculator');

export const restartCalculator = (contestId: number, navigationTaskId: number, contestantId: number) =>
  postContestantAction('contestants-restart', contestId, navigationTaskId, contestantId, 'restart the calculator');

export const recalculateTrack = (contestId: number, navigationTaskId: number, contestantId: number) =>
  postContestantAction('contestants-recalculate-track', contestId, navigationTaskId, contestantId, 'recalculate the live track');

export async function shareNavigationTask(
  contestId: number,
  navigationTaskId: number,
  visibility: NavigationTaskVisibility
): Promise<{ visibility: NavigationTaskVisibility }> {
  const url = reverse('navigationtasks-share', contestId, navigationTaskId);
  const response = await fetch(url, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify({ visibility }),
  });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to update sharing: ${errorMessages}`);
  }
  return response.json();
}
