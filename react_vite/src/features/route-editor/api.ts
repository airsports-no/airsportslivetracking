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
    // Field errors ({"route": ["...", "..."]}) as the sentences they are
    if (typeof errorData === 'object' && errorData !== null) {
      const sentences = Object.values(errorData).flat();
      if (sentences.length > 0 && sentences.every((item) => typeof item === 'string')) {
        return (sentences as string[]).join(' ');
      }
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

// One route requirement of a task type as the backend evaluated it against the route's current
// content (display.services.route_compatibility.evaluate_route_requirements). A maximum of null
// means no upper limit; a maximum of 0 means the feature is forbidden (or, for derived facts such
// as unknown_leg_extension, that no offenders are allowed).
export interface RouteRequirementResult {
    key: string;
    label: string;
    minimum: number;
    maximum: number | null;
    found: number;
    satisfied: boolean;
    message: string;
    // Whether the route must meet it (minimum above 0). A requirement that is not required and has no maximum is an
    // optional step of the guide: always satisfied.
    required: boolean;
    // What the guide tells the user to do; empty when there is nothing to say.
    help: string;
    // The tool that satisfies it (one of ROUTE_REQUIREMENT_TOOLS), null when no tool does (an order, a prohibition).
    tool: RouteRequirementTool | null;
    // For a requirement met by any of several kinds of feature: the further tools that also count.
    other_tools: RouteRequirementTool[];
}

export const ROUTE_REQUIREMENT_TOOLS = [
    'route_waypoint',
    'hidden_gate',
    'known_time_gate',
    'catalogue_turnpoint',
    'circle_start',
    'circle_center',
    'circle_entry',
    'circle_exit',
    'photo',
    'landing_area',
    'takeoff_gate',
    'landing_gate',
    'unknown_leg_point',
    'extension_waypoint',
    'curved_leg',
] as const;

export type RouteRequirementTool = typeof ROUTE_REQUIREMENT_TOOLS[number];

// The special behaviour of the route editor per task type (display.utilities.task_types.TaskTypeDefinition).
export interface TaskTypeRouteEditorFlags {
    // The route is exactly SP, MP and FP.
    three_point_backbone: boolean;
    // No backbone: three timed turn points and catalogue turn points on the free map.
    standalone_timed_turnpoints: boolean;
    // The route is the circle's start, centre, entry and exit markers.
    circle_markers: boolean;
    // At least one leg must be curved.
    curve_required: boolean;
    // Unknown-leg points are followed by extension waypoints.
    extension_waypoints: boolean;
}

export interface TaskCompatibilitySubtype {
    key: string;
    display_name: string;
    group: 'Legacy' | 'CIMA';
    coarse_family: string;
    compatible: boolean;
    missing_reasons: string[];
    // Absent in responses from a backend older than the route requirements; treat as empty.
    requirements?: RouteRequirementResult[];
    // Absent in responses from a backend older than the flags; treat as all false.
    flags?: TaskTypeRouteEditorFlags;
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

// The task_compatibility action reports every known task subtype regardless of route content, so
// an empty feature collection is enough to get the full {key -> display_name/group} catalog - used
// by the route list to label compatible/intended task types without hand-duplicating the registry.
export const fetchTaskSubtypeCatalog = async (): Promise<TaskCompatibilitySubtype[]> => {
    const result = await fetchTaskCompatibility({ type: 'FeatureCollection', features: [] });
    return result.subtypes;
};

export const fetchEditableRouteMapSources = async (routeId: number): Promise<MapSource[]> => {
    const url = reverse('editableroutes-map-sources', routeId);
    return fetchMapSourcesWithRetry(url, 'Failed to fetch route editor map sources');
};

export const fetchGlobalEditableRouteMapSources = async (): Promise<MapSource[]> => {
    const url = reverse('editableroutes-global-map-sources');
    return fetchMapSourcesWithRetry(url, 'Failed to fetch global route editor map sources');
};

