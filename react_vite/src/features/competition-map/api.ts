import type { NavigationTask, PaginatedTrackResponse, ContestantScoreData } from './types';
import { reverse } from '../../urls';
import { getCookie } from '../../utils/csrf';

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

export interface NavigationTaskFilters {
  pks?: number[];
  startTimeGte?: string;
  finishTimeLte?: string;
}

export async function fetchNavigationTask(contestId: number, navigationTaskId: number, filters?: Omit<NavigationTaskFilters, 'pks'>): Promise<NavigationTask> {
  const url = new URL(reverse('navigationtasks-detail', contestId, navigationTaskId), window.location.origin);
  if (filters?.startTimeGte) {
    url.searchParams.set('start_time__gte', filters.startTimeGte);
  }
  if (filters?.finishTimeLte) {
    url.searchParams.set('finish_time__lte', filters.finishTimeLte);
  }
  const res = await fetch(url.toString(), {
    headers: { 'Accept': 'application/json' }
  });
  if (!res.ok) {
    const errorMessages = await getErrorMessages(res);
    const error = new Error(`Failed to fetch navigation task ${navigationTaskId}: ${errorMessages}`) as any;
    error.status = res.status;
    throw error;
  }
  return res.json();
}

export async function fetchNavigationTasks(contestId: number, filters?: NavigationTaskFilters): Promise<NavigationTask[]> {
  const url = new URL(reverse('navigationtasks-list', contestId), window.location.origin);
  if (filters?.pks?.length) {
    url.searchParams.set('pks', filters.pks.join(','));
  }
  if (filters?.startTimeGte) {
    url.searchParams.set('start_time__gte', filters.startTimeGte);
  }
  if (filters?.finishTimeLte) {
    url.searchParams.set('finish_time__lte', filters.finishTimeLte);
  }

  const res = await fetch(url.toString(), {
    headers: { 'Accept': 'application/json' }
  });
  if (!res.ok) {
    const errorMessages = await getErrorMessages(res);
    throw new Error(`Failed to fetch navigation tasks for contest ${contestId}: ${errorMessages}`);
  }
  return res.json();
}

export async function fetchContestantPaginatedTrack(contestId: number, navigationTaskId: number, contestantId: number, cursor?: string | null): Promise<PaginatedTrackResponse> {
  const url = new URL(reverse('contestants-paginated-track-data', contestId, navigationTaskId, contestantId), window.location.origin);
  if (cursor) url.searchParams.set('cursor', cursor);
  const res = await fetch(url.toString(), { headers: { 'Accept': 'application/json' } });
  if (!res.ok) {
    const errorMessages = await getErrorMessages(res);
    throw new Error(`Failed to fetch track for contestant ${contestantId}: ${errorMessages}`);
  }
  return res.json();
}

export async function fetchContestantScoreData(contestId: number, navigationTaskId: number, contestantId: number): Promise<ContestantScoreData> {
  const url = reverse('contestants-score-data', contestId, navigationTaskId, contestantId);
  const res = await fetch(url, {
    headers: { 'Accept': 'application/json' }
  });
  if (!res.ok) {
    const errorMessages = await getErrorMessages(res);
    throw new Error(`Failed to fetch score data for contestant ${contestantId}: ${errorMessages}`);
  }
  return res.json();
}

export async function fetchContestantSlice(contestantId: number, minuteIndex: number, count: number = 1): Promise<any[]> {
  // Use the new top-level contestant slice API
  const url = new URL(`/api/v1/contestant/${contestantId}/slice/${minuteIndex}/`, window.location.origin);
  if (count > 1) {
    url.searchParams.set('count', count.toString());
  }
  const res = await fetch(url.toString(), {
    headers: { 'Accept': 'application/json' }
  });
  if (!res.ok) {
    const errorMessages = await getErrorMessages(res);
    throw new Error(`Failed to fetch slice for contestant ${contestantId}: ${errorMessages}`);
  }
  return res.json();
}

export function makeWebSocket(navigationTaskId: number): WebSocket {
  const { host, protocol } = window.location;
  const wsProtocol = protocol === 'https:' ? 'wss' : 'ws';
  // Assuming the ws path is not part of django-js-reverse
  return new WebSocket(`${wsProtocol}://${host}/ws/tracks/${navigationTaskId}/`);
}

export async function fetchPhotos(contestId: number, navigationTaskId: number): Promise<any[]> {
    const url = reverse('navigationtasks-photos', contestId, navigationTaskId);
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error(`Failed to fetch photos: ${res.statusText}`);
    }
    return res.json();
}

export async function createPhoto(photoData: any): Promise<any> {
    const url = reverse('photos-list');
    const res = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')!
        },
        body: JSON.stringify(photoData)
    });
    if (!res.ok) {
        throw new Error(`Failed to create photo: ${res.statusText}`);
    }
    return res.json();
}

export async function updatePhoto(photoId: number, photoData: any): Promise<any> {
    const url = reverse('photos-detail', photoId);
    const res = await fetch(url, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')!
        },
        body: JSON.stringify(photoData)
    });
    if (!res.ok) {
        throw new Error(`Failed to update photo: ${res.statusText}`);
    }
    return res.json();
}

export async function deletePhoto(photoId: number): Promise<void> {
    const url = reverse('photos-detail', photoId);
    const res = await fetch(url, {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')!
        }
    });
    if (!res.ok) {
        throw new Error(`Failed to delete photo: ${res.statusText}`);
    }
}

export async function uploadPhotoFile(photoId: number, file: File): Promise<any> {
    const url = reverse('photos-detail', photoId);
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(url, {
        method: 'PATCH',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')!
        },
        body: formData
    });
    if (!res.ok) {
        throw new Error(`Failed to upload photo: ${res.statusText}`);
    }
    return res.json();
}

export async function fetchContestDetails(contestId: number): Promise<any> {
    const url = reverse("contests-detail", contestId);
    const res = await fetch(url);
    if (!res.ok) {
        const errorMessages = await getErrorMessages(res);
        throw new Error(`Failed to fetch contest details: ${errorMessages}`);
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
        const errorMessages = await getErrorMessages(res);
        throw new Error(`Failed to fetch disclaimer: ${errorMessages}`);
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

