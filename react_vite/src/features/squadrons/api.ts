import { getCookie } from '../../utils/csrf';
import { reverse } from '../../urls';

export type SquadronRole = 'admin' | 'member';

export interface Squadron {
    id: number;
    name: string;
    description: string;
    created_at: string;
    my_role: SquadronRole | null;
    member_count: number;
    contest_count: number;
}

export interface SquadronMember {
    id: number;
    user_id: number;
    name: string;
    email_hint: string;
    role: SquadronRole;
    joined_at: string;
}

export interface SquadronInvitation {
    id: number;
    squadron: number;
    squadron_name: string;
    squadron_description: string;
    role: SquadronRole;
    status: string;
    invited_by_name: string;
    created_at: string;
}

export interface SentInvitation extends SquadronInvitation {
    email_hint: string;
}

/** A contest shared with a squadron, with who added it and whether the user may take it away again */
export interface SquadronContest {
    id: number;
    name: string;
    start_time: string;
    shared_by_name: string;
    shared_by_me: boolean;
    can_remove: boolean;
}

export interface SquadronDetail extends Squadron {
    members: SquadronMember[];
    invitations: SentInvitation[];
    contests: SquadronContest[];
    /** Only for admins: the key in the squadron's invite link, empty while the link is off */
    invite_token: string | null;
}

/** What an invite link shows before the user decides to join */
export interface JoinPreview {
    name: string;
    description: string;
    member_count: number;
    already_member: boolean;
}

export interface SharedSquadron {
    id: number;
    name: string;
    shared_by_name: string;
    can_remove: boolean;
}

/** A contest the user can open through squadrons, with every squadron that gives the access */
export interface ContestAccess {
    id: number;
    name: string;
    start_time: string;
    finish_time: string;
    squadrons: { id: number; name: string }[];
}

export interface ShareableContest {
    id: number;
    name: string;
    start_time: string;
}

const headers = () => ({
    'Content-Type': 'application/json',
    'X-CSRFToken': getCookie('csrftoken')!,
});

async function errorMessage(response: Response): Promise<string> {
    try {
        const data = await response.json();
        if (Array.isArray(data)) return data.join(' ');
        if (data && typeof data === 'object') {
            if ('detail' in data) return String(data.detail);
            return Object.values(data).flat().join(' ');
        }
    } catch {
        // fall through to the status text
    }
    return response.statusText;
}

export class ApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
        super(message);
        this.status = status;
    }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
    const response = await fetch(url, { headers: headers(), ...init });
    if (!response.ok) {
        throw new ApiError(await errorMessage(response), response.status);
    }
    return response.status === 204 ? (undefined as T) : response.json();
}

const send = (method: string, body?: unknown): RequestInit => ({
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
});

export const fetchMySquadrons = () => request<Squadron[]>(reverse('squadrons-list'));

export const createSquadron = (name: string, description: string) =>
    request<Squadron>(reverse('squadrons-list'), send('POST', { name, description }));

export const fetchSquadron = (squadronId: number) => request<SquadronDetail>(reverse('squadrons-detail', squadronId));

export const updateSquadron = (squadronId: number, name: string, description: string) =>
    request<Squadron>(reverse('squadrons-detail', squadronId), send('PATCH', { name, description }));

export const deleteSquadron = (squadronId: number) =>
    request<void>(reverse('squadrons-detail', squadronId), send('DELETE'));

/** identifier: a user id (from the people search) or an e-mail address */
export const inviteToSquadron = (squadronId: number, identifier: string, role: SquadronRole) =>
    request<SentInvitation>(reverse('squadrons-invite', squadronId), send('POST', { identifier, role }));

export const revokeSquadronInvitation = (squadronId: number, invitationId: number) =>
    request<void>(reverse('squadrons-invitation', squadronId, invitationId), send('DELETE'));

export const setSquadronMemberRole = (squadronId: number, membershipId: number, role: SquadronRole) =>
    request<{ role: SquadronRole }>(reverse('squadrons-member', squadronId, membershipId), send('PUT', { role }));

export const removeSquadronMember = (squadronId: number, membershipId: number) =>
    request<void>(reverse('squadrons-member', squadronId, membershipId), send('DELETE'));

export const leaveSquadron = (squadronId: number) => request<void>(reverse('squadrons-leave', squadronId), send('POST'));

export const fetchContestAccess = () => request<ContestAccess[]>(reverse('squadrons-contest-access'));

export const fetchShareableContests = (squadronId: number) =>
    request<ShareableContest[]>(reverse('squadrons-shareable-contests', squadronId));

export const addContestToSquadron = (squadronId: number, contestId: number) =>
    request<SquadronContest>(reverse('squadrons-contests', squadronId), send('POST', { contest: contestId }));

export const removeContestFromSquadron = (squadronId: number, contestId: number) =>
    request<void>(reverse('squadrons-contest', squadronId, contestId), send('DELETE'));

export const enableSquadronInviteLink = (squadronId: number) =>
    request<{ invite_token: string }>(reverse('squadrons-invite-link', squadronId), send('POST'));

export const disableSquadronInviteLink = (squadronId: number) =>
    request<void>(reverse('squadrons-invite-link', squadronId), send('DELETE'));

export const fetchJoinPreview = (token: string) => request<JoinPreview>(reverse('squadron-join-detail', token));

export const joinSquadronViaLink = (token: string) =>
    request<{ id: number; my_role: SquadronRole }>(reverse('squadron-join-join', token), send('POST'));

/** The address to share: opening it, logged in, shows the squadron and a Join button */
export const inviteLinkUrl = (token: string) => `${window.location.origin}/squadrons/join/${token}`;

export const fetchMySquadronInvitations = () => request<SquadronInvitation[]>(reverse('squadron-invitations-list'));

export const acceptSquadronInvitation = (invitationId: number) =>
    request<void>(reverse('squadron-invitations-accept', invitationId), send('POST'));

export const declineSquadronInvitation = (invitationId: number) =>
    request<void>(reverse('squadron-invitations-decline', invitationId), send('POST'));

export const fetchContestSquadrons = (contestId: number) =>
    request<SharedSquadron[]>(reverse('contests-shared-squadrons', contestId));

export const shareContestWithSquadron = (contestId: number, squadronId: number) =>
    request<SharedSquadron[]>(reverse('contests-shared-squadrons', contestId), send('POST', { squadron: squadronId }));

export const unshareContestWithSquadron = (contestId: number, squadronId: number) =>
    request<SharedSquadron[]>(reverse('contests-unshare-squadron', contestId, squadronId), send('DELETE'));
