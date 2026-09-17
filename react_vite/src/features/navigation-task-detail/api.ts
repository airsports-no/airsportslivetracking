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

export async function deleteContestant(contestId: number, navigationTaskId: number, contestantId: number): Promise<void> {
  const url = reverse('contestants-detail', contestId, navigationTaskId, contestantId);
  const response = await fetch(url, { method: 'DELETE', headers: getAuthHeaders() });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to delete contestant: ${errorMessages}`);
  }
}

export async function recalculateWithStartTime(
  contestId: number,
  navigationTaskId: number,
  contestantId: number,
  startingPointTime: string
): Promise<{ id: number }> {
  const url = reverse('contestants-recalculate-with-start-time', contestId, navigationTaskId, contestantId);
  const response = await fetch(url, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ starting_point_time: startingPointTime }),
  });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to recalculate with a new start time: ${errorMessages}`);
  }
  return response.json();
}

export async function uploadGpxTrack(
  contestId: number,
  navigationTaskId: number,
  contestantId: number,
  base64TrackFile: string
): Promise<void> {
  const url = reverse('contestants-gpx-track', contestId, navigationTaskId, contestantId);
  const response = await fetch(url, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ track_file: base64TrackFile }),
  });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to upload GPX track: ${errorMessages}`);
  }
}

export interface AdministrativePenaltyCategory {
  gate: string;
  default_reason: string;
  category: string;
  label: string;
}

export interface GateTimesResponse {
  rendered_waypoints: string[];
  distances: Record<string, number>;
  total_distance: number;
  log: Record<string, { pk: number; text: string }[]>;
  actual_times: Record<string, string>;
  can_apply_quarantine_penalty: boolean;
  administrative_penalty_categories: Record<string, AdministrativePenaltyCategory>;
  compiled_fuel_review: {
    declared_endurance_minutes?: number;
    fuel_deadline?: string;
    duration_residual_fuel_required?: boolean;
  } | null;
}

export async function fetchGateTimes(contestId: number, navigationTaskId: number, contestantId: number): Promise<GateTimesResponse> {
  const url = reverse('contestants-gate-times', contestId, navigationTaskId, contestantId);
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to fetch gate times: ${errorMessages}`);
  }
  return response.json();
}

export async function removeScoreLogEntry(
  contestId: number,
  navigationTaskId: number,
  contestantId: number,
  entryPk: number
): Promise<void> {
  const url = reverse('contestants-remove-score-log-entry', contestId, navigationTaskId, contestantId, entryPk);
  const response = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to remove score log entry: ${errorMessages}`);
  }
}

export async function applyQuarantinePenalty(
  contestId: number,
  navigationTaskId: number,
  contestantId: number,
  payload: { points: number; reason: string; category: string }
): Promise<void> {
  const url = reverse('contestants-apply-quarantine-penalty', contestId, navigationTaskId, contestantId);
  const response = await fetch(url, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to apply penalty: ${errorMessages}`);
  }
}

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

async function postNavigationTaskAction(
  actionUrlName: string,
  contestId: number,
  navigationTaskId: number,
  failureVerb: string
): Promise<void> {
  const url = reverse(actionUrlName, contestId, navigationTaskId);
  const response = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to ${failureVerb}: ${errorMessages}`);
  }
}

export const removeAllContestants = (contestId: number, navigationTaskId: number) =>
  postNavigationTaskAction('navigationtasks-remove-contestants', contestId, navigationTaskId, 'remove all contestants');

export const refreshEditableRoute = (contestId: number, navigationTaskId: number) =>
  postNavigationTaskAction('navigationtasks-refresh-editable-route', contestId, navigationTaskId, 'reload the route');

export async function deleteNavigationTask(contestId: number, navigationTaskId: number): Promise<void> {
  const url = reverse('navigationtasks-detail', contestId, navigationTaskId);
  const response = await fetch(url, { method: 'DELETE', headers: getAuthHeaders() });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to delete navigation task: ${errorMessages}`);
  }
}

export interface NavigationTaskDetailsUpdate {
  name?: string;
  start_time?: string;
  finish_time?: string;
  display_background_map?: boolean;
  display_secrets?: boolean;
  minutes_to_starting_point?: number;
  planning_time?: number;
  minutes_to_landing?: number;
  wind_speed?: number;
  wind_direction?: number;
  allow_self_management?: boolean;
  calculation_delay_minutes?: number;
}

export async function updateNavigationTaskDetails(
  contestId: number,
  navigationTaskId: number,
  payload: NavigationTaskDetailsUpdate
): Promise<void> {
  const url = reverse('navigationtasks-update-details', contestId, navigationTaskId);
  const response = await fetch(url, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to update navigation task details: ${errorMessages}`);
  }
}

export interface FlightOrderConfiguration {
  id: number;
  document_size: string;
  include_turning_point_images: boolean;
  map_include_meridians_and_parallels_lines: boolean;
  map_include_openaip_overlay: boolean;
  map_dpi: number;
  map_zoom_level: number;
  map_orientation: string;
  map_scale: number;
  map_source: string;
  map_include_annotations: boolean;
  map_include_contestant_declarations: boolean;
  map_plot_track_between_waypoints: boolean;
  map_line_width: number;
  map_minute_mark_line_width: number;
  map_line_colour: string;
}

export async function fetchFlightOrderConfiguration(
  contestId: number,
  navigationTaskId: number
): Promise<FlightOrderConfiguration> {
  const url = reverse('navigationtasks-flight-order-configuration', contestId, navigationTaskId);
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to fetch flight order configuration: ${errorMessages}`);
  }
  return response.json();
}

export async function updateFlightOrderConfiguration(
  contestId: number,
  navigationTaskId: number,
  payload: Partial<FlightOrderConfiguration>
): Promise<FlightOrderConfiguration> {
  const url = reverse('navigationtasks-update-flight-order-configuration', contestId, navigationTaskId);
  const response = await fetch(url, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to update flight order configuration: ${errorMessages}`);
  }
  return response.json();
}

export async function quickAddContestant(
  contestId: number,
  navigationTaskId: number,
  payload: { contest_team: number; starting_point_time: string; adaptive_start: boolean }
): Promise<{ id: number }> {
  const url = reverse('navigationtasks-quick-add-contestant', contestId, navigationTaskId);
  const response = await fetch(url, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to add contestant: ${errorMessages}`);
  }
  return response.json();
}

export interface ContestTeamOption {
  id: number;
  team: { crew: { member1: PersonNameLike; member2: PersonNameLike | null }; aeroplane: { registration: string } };
}

interface PersonNameLike {
  first_name: string;
  last_name: string;
}

// Reuses the same contests-teams action the (already-built) contest-management feature's team
// list uses - it nests full crew/aeroplane data, unlike ContestTeamViewSet's plain contestteams
// list action (ContestTeamSerialiser leaves `team` as a bare id).
export async function fetchContestTeams(contestId: number): Promise<ContestTeamOption[]> {
  const url = reverse('contests-teams', contestId);
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to fetch contest teams: ${errorMessages}`);
  }
  return response.json();
}

export interface BatchUpdateContestantsPayload {
  contestant_ids: number[];
  update_wind?: boolean;
  wind_speed?: number;
  wind_direction?: number;
  shift_times?: boolean;
  time_shift_minutes?: number;
}

export async function batchUpdateContestants(
  contestId: number,
  navigationTaskId: number,
  payload: BatchUpdateContestantsPayload
): Promise<{ updated: number }> {
  const url = reverse('navigationtasks-batch-update-contestants', contestId, navigationTaskId);
  const response = await fetch(url, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorMessages = await getErrorMessages(response);
    throw new Error(`Failed to batch-update contestants: ${errorMessages}`);
  }
  return response.json();
}
