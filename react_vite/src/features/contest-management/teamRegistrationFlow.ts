import { CopilotSelection, PilotSelection, TeamRegistrationFormValues } from './schemas/teamRegistrationSchema';
import { AdminTeamRegistrationPayload } from './types';

// Mode transitions for the pilot/copilot "search or create" toggles: switching mode resets the
// fields that belonged to the previous mode, so a half-filled "create" form doesn't linger
// (and get silently submitted) after the user picks an existing person instead.
export function pilotForMode(mode: PilotSelection['mode']): PilotSelection {
    if (mode === 'existing') {
        return { mode: 'existing', person: undefined as unknown as number };
    }
    return { mode: 'create', first_name: '', last_name: '', email: '', phone: '', country: '' };
}

export function copilotForMode(mode: CopilotSelection['mode']): CopilotSelection {
    if (mode === 'skip') {
        return { mode: 'skip' };
    }
    if (mode === 'existing') {
        return { mode: 'existing', person: undefined as unknown as number };
    }
    return { mode: 'create', first_name: '', last_name: '', email: '', phone: '', country: '' };
}

// Builds AdminTeamRegistrationSerialiser's request payload from validated form values.
// `contestTeamId`, when given, edits that existing registration (replaces its team) instead of
// registering a new one - see ContestViewSet.register_team.
export function buildRegisterPayload(values: TeamRegistrationFormValues, contestTeamId?: number): AdminTeamRegistrationPayload {
    return {
        ...(contestTeamId ? { contest_team: contestTeamId } : {}),
        pilot: values.pilot,
        copilot: values.copilot,
        aeroplane: values.aeroplane,
        club: values.club,
        air_speed: values.air_speed,
        tracking_service: values.tracking_service,
        tracking_device: values.tracking_device,
        tracker_device_id: values.tracker_device_id || undefined,
    };
}
