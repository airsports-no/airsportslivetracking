import { describe, expect, it } from 'vitest';
import { buildRegisterPayload, copilotForMode, pilotForMode } from './teamRegistrationFlow';
import { teamRegistrationDefaults } from './schemas/teamRegistrationSchema';

describe('pilotForMode', () => {
    it('resets to an empty create form', () => {
        expect(pilotForMode('create')).toEqual({ mode: 'create', first_name: '', last_name: '', email: '', phone: '', country: '' });
    });

    it('resets to an unselected existing-person slot', () => {
        expect(pilotForMode('existing')).toEqual({ mode: 'existing', person: undefined });
    });
});

describe('copilotForMode', () => {
    it('supports skip', () => {
        expect(copilotForMode('skip')).toEqual({ mode: 'skip' });
    });

    it('resets to an empty create form', () => {
        expect(copilotForMode('create')).toEqual({ mode: 'create', first_name: '', last_name: '', email: '', phone: '', country: '' });
    });
});

describe('buildRegisterPayload', () => {
    it('omits contest_team when registering a new team', () => {
        const payload = buildRegisterPayload(teamRegistrationDefaults);
        expect(payload.contest_team).toBeUndefined();
        expect(payload.pilot).toEqual(teamRegistrationDefaults.pilot);
        expect(payload.tracking_device).toBe('pilot_app');
    });

    it('includes contest_team when editing an existing registration', () => {
        const payload = buildRegisterPayload(teamRegistrationDefaults, 42);
        expect(payload.contest_team).toBe(42);
    });

    it('drops an empty tracker_device_id rather than sending an empty string', () => {
        const payload = buildRegisterPayload({ ...teamRegistrationDefaults, tracker_device_id: '' });
        expect(payload.tracker_device_id).toBeUndefined();
    });
});
