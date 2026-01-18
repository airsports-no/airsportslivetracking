import { getCookie } from '../../utils/csrf';
import { RouteData, SavePayload } from './types';
import { Route } from '../../types'; // Add this import
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
    return JSON.stringify(errorData); // Fallback to stringifying the whole object
  } catch {
    return response.statusText; // Fallback to status text if JSON parsing fails
  }
}

const getAuthHeaders = () => {
    return {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')!
    };
};

export const fetchRoute = async (routeId: number): Promise<RouteData> => {
    const url = reverse('editableroutes-detail', routeId);
    const response = await fetch(url);
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to load route: ${errorMessages}`);
    }
    const data = await response.json();
    return data;
};

export const saveRoute = async (routeId: string | null, payload: SavePayload): Promise<{ id: number }> => {
    let url = reverse('editableroutes-list');
    let method = 'POST';

    if (routeId) {
        url = reverse('editableroutes-detail', parseInt(routeId));
        method = 'PUT';
    }

    const response = await fetch(url, {
        method,
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
    });

    if (response.ok) {
        const result = await response.json();
        return result;
    } else {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Error saving route: ${errorMessages}`);
    }
};

export const fetchEditableRoutes = async (): Promise<Route[]> => {
    const url = reverse('editableroutes-list');
    const response = await fetch(url);
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to fetch editable routes: ${errorMessages}`);
    }
    const data = await response.json();
    return data;
};

