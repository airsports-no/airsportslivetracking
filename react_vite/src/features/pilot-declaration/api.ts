import { getCookie } from '../../utils/csrf';
import { reverse } from '../../urls';
import { PilotDeclaration } from './types';

export class DeclarationApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
        super(message);
        this.status = status;
    }
}

// The server writes its messages for pilots: use them as they are.
const messageOf = async (response: Response, fallback: string): Promise<string> => {
    try {
        const data = await response.json();
        if (typeof data?.detail === 'string') return data.detail;
        if (data && typeof data === 'object') {
            const parts = Object.values(data).flatMap((value) => (Array.isArray(value) ? value : [value])).filter((v) => typeof v === 'string');
            if (parts.length > 0) return parts.join(' ');
        }
    } catch {
        // not JSON
    }
    return fallback;
};

export const fetchDeclaration = async (contestantId: number): Promise<PilotDeclaration> => {
    const response = await fetch(reverse('declarations-detail', contestantId), { headers: { 'Content-Type': 'application/json' } });
    if (!response.ok) {
        throw new DeclarationApiError(await messageOf(response, 'The declaration could not be loaded.'), response.status);
    }
    return response.json();
};

export const saveDeclaration = async (contestantId: number, declarationPayload: Record<string, unknown>): Promise<PilotDeclaration> => {
    const response = await fetch(reverse('declarations-detail', contestantId), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') ?? '' },
        body: JSON.stringify({ declaration_payload: declarationPayload }),
    });
    if (!response.ok) {
        throw new DeclarationApiError(await messageOf(response, 'The declaration could not be saved.'), response.status);
    }
    return response.json();
};
