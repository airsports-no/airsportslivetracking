import { getCookie } from '../../utils/csrf';
import { MapSource, RouteData, SavePayload } from './types';
import { Route } from '../../types'; // Add this import
import { reverse } from '../../urls';

type ErrorMessage = string | string[];

export interface MapSourceFetchError extends Error {
  transient?: boolean;
  attempts?: number;
}

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

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const isTransientMapSourceError = (response: Response, errorMessages: ErrorMessage): boolean => {
    if (response.status === 502 || response.status === 503 || response.status === 504) return true;
    const normalized = Array.isArray(errorMessages) ? errorMessages.join(' ') : String(errorMessages || '');
    return /timeout|timed out|temporar|unavailable|bad gateway|gateway timeout/i.test(normalized);
};

async function fetchMapSourcesWithRetry(url: string, failureLabel: string): Promise<MapSource[]> {
    const maxAttempts = 10;
    const retryDelayMs = 30000;

    let lastError: MapSourceFetchError | null = null;

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        const response = await fetch(url);
        if (response.ok) {
            return await response.json();
        }

        const errorMessages = await getErrorMessages(response);
        const transient = isTransientMapSourceError(response, errorMessages);
        const error = new Error(`${failureLabel}: ${errorMessages}`) as MapSourceFetchError;
        error.transient = transient;
        error.attempts = attempt;
        lastError = error;

        const shouldRetry = transient && attempt < maxAttempts;
        if (!shouldRetry) {
            throw error;
        }
        await sleep(retryDelayMs);
    }

    if (lastError) {
        throw lastError;
    }
    throw new Error(`${failureLabel}: retries exhausted`);
}

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

export const fetchEditableRouteMapSources = async (routeId: number): Promise<MapSource[]> => {
    const url = reverse('editableroutes-map-sources', routeId);
    return fetchMapSourcesWithRetry(url, 'Failed to fetch route editor map sources');
};

export const fetchGlobalEditableRouteMapSources = async (): Promise<MapSource[]> => {
    const url = reverse('editableroutes-global-map-sources');
    return fetchMapSourcesWithRetry(url, 'Failed to fetch global route editor map sources');
};

