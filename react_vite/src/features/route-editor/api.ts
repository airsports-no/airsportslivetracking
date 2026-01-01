import { getCookie } from '../../utils/csrf';
import { RouteData, SavePayload } from './types';
import { Route } from '../../types'; // Add this import

// Declare global configuration for editableRouteUrl, etc.
declare global {
    interface Document {
        configuration: {
            editableRouteUrl: (routeId: number) => string;
            EDITABLE_ROUTES_URL: string;
            editRouteViewUrl: (routeId: number) => string;
            isAuthenticated?: boolean; // Add this line
        }
    }
}

const getAuthHeaders = () => {
    return {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')!
    };
};

export const fetchRoute = async (routeId: number): Promise<RouteData> => {
    const url = document.configuration.editableRouteUrl(routeId);
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Failed to load route: ${response.statusText}`);
    }
    const data = await response.json();
    return data;
};

export const saveRoute = async (routeId: string | null, payload: SavePayload): Promise<{ id: number }> => {
    let url = document.configuration.EDITABLE_ROUTES_URL;
    let method = 'POST';

    if (routeId) {
        url = document.configuration.editableRouteUrl(parseInt(routeId));
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
    const url = document.configuration.EDITABLE_ROUTES_URL;
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Failed to fetch editable routes: ${response.statusText}`);
    }
    const data = await response.json();
    return data;
};
