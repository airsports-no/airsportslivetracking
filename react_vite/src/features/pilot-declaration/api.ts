import { reverse } from '../../urls';

// Helper to get CSRF token
const getCsrfToken = () => {
    return (window as any).document?.configuration?.csrftoken || '';
};

export const fetchDeclarationData = async (contestantId: string) => {
    const url = reverse('contestant_declaration_api', contestantId);
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Failed to fetch declaration: ${res.statusText}`);
    return res.json();
};

export const saveDeclarationData = async (contestantId: string, configuration: any) => {
    const url = reverse('contestant_declaration_api', contestantId);
    const res = await fetch(url, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ declared_configuration: configuration })
    });
    if (!res.ok) throw new Error(`Failed to save declaration: ${res.statusText}`);
    return res.json();
};

export const fetchNavigationTask = async (contestId: string, taskId: string) => {
    // Assuming DRF nested router structure: /api/v1/contests/{cid}/navigationtasks/{tid}/
    // Check if we have a reverse URL for this. 'navigationtasks-detail' usually.
    // But nested routers have specific names. 'contests-navigationtasks-detail'?
    // Let's try to construct it or use reverse if we know the name.
    // DRF nested simple router usually generates names like `contests-navigationtasks-detail`.
    
    // Let's assume standard URL construction if reverse fails or is unknown.
    const url = `/api/v1/contests/${contestId}/navigationtasks/${taskId}/`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Failed to fetch task: ${res.statusText}`);
    return res.json();
};
