import type { NavigationTask, PaginatedTrackResponse, ContestantScoreData } from './types';

export async function fetchNavigationTask(contestId: number, navigationTaskId: number): Promise<NavigationTask> {
  const res = await fetch(`/api/v1/contests/${contestId}/navigationtasks/${navigationTaskId}/`, {
    headers: { 'Accept': 'application/json' }
  });
  if (!res.ok) throw new Error(`Failed to fetch navigation task ${navigationTaskId}`);
  return res.json();
}

export async function fetchContestantPaginatedTrack(contestId: number, navigationTaskId: number, contestantId: number, cursor?: string | null): Promise<PaginatedTrackResponse> {
  const url = new URL(`/api/v1/contests/${contestId}/navigationtasks/${navigationTaskId}/contestants/${contestantId}/paginated_track_data`, window.location.origin);
  if (cursor) url.searchParams.set('cursor', cursor);
  const res = await fetch(url.toString(), { headers: { 'Accept': 'application/json' } });
  if (!res.ok) throw new Error(`Failed to fetch track for contestant ${contestantId}`);
  return res.json();
}

export async function fetchContestantScoreData(contestId: number, navigationTaskId: number, contestantId: number): Promise<ContestantScoreData> {
  const res = await fetch(`/api/v1/contests/${contestId}/navigationtasks/${navigationTaskId}/contestants/${contestantId}/score_data/`, {
    headers: { 'Accept': 'application/json' }
  });
  if (!res.ok) throw new Error(`Failed to fetch score data for contestant ${contestantId}`);
  return res.json();
}

export function makeWebSocket(navigationTaskId: number): WebSocket {
  const { host, protocol } = window.location;
  const wsProtocol = protocol === 'https:' ? 'wss' : 'ws';
  return new WebSocket(`${wsProtocol}://${host}/ws/tracks/${navigationTaskId}/`);
}
