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

const withTimeout = async <T>(promise: Promise<T>, timeoutMs: number, timeoutMessage: string): Promise<T> => {
    let timeoutId: number | undefined;
    try {
        return await Promise.race([
            promise,
            new Promise<T>((_, reject) => {
                timeoutId = window.setTimeout(() => reject(new Error(timeoutMessage)), timeoutMs);
            }),
        ]);
    } finally {
        if (timeoutId !== undefined) {
            window.clearTimeout(timeoutId);
        }
    }
};

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

    const response = await withTimeout(
        fetch(url, {
            method,
            headers: getAuthHeaders(),
            body: JSON.stringify(payload)
        }),
        15000,
        'Error saving route: request timed out. The server may be busy generating the route thumbnail or retrying external map tiles.',
    );

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

export interface TaskCompatibilitySubtype {
    key: string;
    display_name: string;
    group: 'Legacy' | 'CIMA';
    coarse_family: string;
    compatible: boolean;
    missing_reasons: string[];
}

export interface TaskCompatibilityResult {
    compatible_task_types: string[];
    subtypes: TaskCompatibilitySubtype[];
}

// Dry-run compatibility check against the route's current (possibly unsaved) content, so the
// intended-task-types picker can grey out task types the route doesn't actually support without
// waiting for a save. See display.services.route_compatibility on the backend, which remains the
// single source of truth for the ruleset.
export const fetchTaskCompatibility = async (route: RouteData['route']): Promise<TaskCompatibilityResult> => {
    const url = reverse('editableroutes-task-compatibility');
    const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ route }),
    });
    if (!response.ok) {
        const errorMessages = await getErrorMessages(response);
        throw new Error(`Failed to check task type compatibility: ${errorMessages}`);
    }
    return response.json();
};

export const fetchEditableRouteMapSources = async (routeId: number): Promise<MapSource[]> => {
    const url = reverse('editableroutes-map-sources', routeId);
    return fetchMapSourcesWithRetry(url, 'Failed to fetch route editor map sources');
};

export const fetchGlobalEditableRouteMapSources = async (): Promise<MapSource[]> => {
    const url = reverse('editableroutes-global-map-sources');
    return fetchMapSourcesWithRetry(url, 'Failed to fetch global route editor map sources');
};

