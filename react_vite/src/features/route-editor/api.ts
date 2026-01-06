import { getCookie } from '../../utils/csrf';
import { RouteData, SavePayload } from './types';
import { Route } from '../../types'; // Add this import
import { reverse } from '../../urls';

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
        throw new Error(`Failed to load route: ${response.statusText}`);
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
        throw new Error(`Error saving route: ${response.statusText}`);
    }
};

export const fetchEditableRoutes = async (): Promise<Route[]> => {
    const url = reverse('editableroutes-list');
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Failed to fetch editable routes: ${response.statusText}`);
    }
    const data = await response.json();
    return data;
};

