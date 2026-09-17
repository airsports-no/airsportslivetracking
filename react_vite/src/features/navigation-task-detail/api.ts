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
