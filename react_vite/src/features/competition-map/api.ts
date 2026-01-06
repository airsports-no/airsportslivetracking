import type { NavigationTask, PaginatedTrackResponse, ContestantScoreData } from './types';
import { reverse } from '../../urls';

export async function fetchNavigationTask(contestId: number, navigationTaskId: number): Promise<NavigationTask> {
  const url = reverse('navigationtasks-detail', contestId, navigationTaskId);
  const res = await fetch(url, {
    headers: { 'Accept': 'application/json' }
  });
  if (!res.ok) throw new Error(`Failed to fetch navigation task ${navigationTaskId}`);
  return res.json();
}

export async function fetchContestantPaginatedTrack(contestId: number, navigationTaskId: number, contestantId: number, cursor?: string | null): Promise<PaginatedTrackResponse> {
  const url = new URL(reverse('contestants-paginated-track-data', contestId, navigationTaskId, contestantId), window.location.origin);
  if (cursor) url.searchParams.set('cursor', cursor);
  const res = await fetch(url.toString(), { headers: { 'Accept': 'application/json' } });
  if (!res.ok) throw new Error(`Failed to fetch track for contestant ${contestantId}`);
  return res.json();
}

export async function fetchContestantScoreData(contestId: number, navigationTaskId: number, contestantId: number): Promise<ContestantScoreData> {
  const url = reverse('contestants-score-data', contestId, navigationTaskId, contestantId);
  const res = await fetch(url, {
    headers: { 'Accept': 'application/json' }
  });
  if (!res.ok) throw new Error(`Failed to fetch score data for contestant ${contestantId}`);
  return res.json();
}

export function makeWebSocket(navigationTaskId: number): WebSocket {
  const { host, protocol } = window.location;
  const wsProtocol = protocol === 'https:' ? 'wss' : 'ws';
  // Assuming the ws path is not part of django-js-reverse
  return new WebSocket(`${wsProtocol}://${host}/ws/tracks/${navigationTaskId}/`);
}

export async function fetchContestDetails(contestId: number): Promise<any> {
    const url = reverse("contests-detail", contestId);
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error(`Failed to fetch contest details: ${res.statusText}`);
    }
    return await res.json();
}

export async function fetchDisclaimerHtml(): Promise<string> {
    // Assume 'terms_and_conditions' is the Django URL name for the disclaimer page
    const disclaimerUrl = reverse('terms_and_conditions'); 
    if (!disclaimerUrl) {
        throw new Error("Disclaimer URL not found in configuration or URL reversing service.");
    }

    const res = await fetch(disclaimerUrl);
    if (!res.ok) {
        throw new Error(`Failed to fetch disclaimer: ${res.statusText}`);
    }
    const html = await res.text();
    
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    
    // Extract styles and links from the head
    const styleTags = Array.from(doc.head.querySelectorAll('style'));
    const linkTags = Array.from(doc.head.querySelectorAll('link[rel="stylesheet"]'));
    const stylesHtml = styleTags.map(tag => tag.outerHTML).join('');
    const linksHtml = linkTags.map(tag => tag.outerHTML).join('');

    // Extract body content
    const bodyContent = doc.body.innerHTML;

    return stylesHtml + linksHtml + bodyContent;
}

