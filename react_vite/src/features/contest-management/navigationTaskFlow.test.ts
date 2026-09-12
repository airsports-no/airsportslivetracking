import { requiredParameters, nextStep, contestLocalTimeToIso, ANR_CORRIDOR, AIRSPORTS, AIRSPORT_CHALLENGE, PRECISION, LANDING } from './navigationTaskFlow';

describe('contestLocalTimeToIso', () => {
    it('embeds the contest timezone offset rather than the browser/server one', () => {
        // Europe/Oslo is UTC+2 in August (CEST).
        expect(contestLocalTimeToIso('2026-08-01T09:00', 'Europe/Oslo')).toBe('2026-08-01T09:00:00+02:00');
    });

    it('uses +00:00 for UTC', () => {
        expect(contestLocalTimeToIso('2026-08-01T09:00', 'UTC')).toBe('2026-08-01T09:00:00+00:00');
    });

    it('handles a negative offset', () => {
        // America/New_York is UTC-4 in August (EDT).
        expect(contestLocalTimeToIso('2026-08-01T09:00', 'America/New_York')).toBe('2026-08-01T09:00:00-04:00');
    });
});

describe('requiredParameters', () => {
    it('requires both corridor_width and rounded_corners for ANR', () => {
        expect(requiredParameters(ANR_CORRIDOR)).toEqual(['rounded_corners', 'corridor_width']);
    });

    it('requires only rounded_corners for airsports and airsport challenge', () => {
        expect(requiredParameters(AIRSPORTS)).toEqual(['rounded_corners']);
        expect(requiredParameters(AIRSPORT_CHALLENGE)).toEqual(['rounded_corners']);
    });

    it('requires nothing for precision/poker/landing', () => {
        expect(requiredParameters(PRECISION)).toEqual([]);
        expect(requiredParameters(LANDING)).toEqual([]);
    });
});

describe('nextStep', () => {
    it('contest entry: template -> route -> details when no parameters needed', () => {
        const entry = { kind: 'contest' as const, contestId: 1 };
        expect(nextStep('template', entry, PRECISION)).toBe('route');
        expect(nextStep('route', entry, PRECISION)).toBe('details');
        expect(nextStep('details', entry, PRECISION)).toBe('submit');
    });

    it('contest entry: template -> route -> parameters -> details when parameters needed', () => {
        const entry = { kind: 'contest' as const, contestId: 1 };
        expect(nextStep('route', entry, ANR_CORRIDOR)).toBe('parameters');
        expect(nextStep('parameters', entry, ANR_CORRIDOR)).toBe('details');
    });

    it('route entry: goes to the contest step instead of route-selection', () => {
        const entry = { kind: 'route' as const, editableRouteId: 42 };
        expect(nextStep('template', entry, PRECISION)).toBe('contest');
        expect(nextStep('contest', entry, PRECISION)).toBe('details');
        expect(nextStep('contest', entry, ANR_CORRIDOR)).toBe('parameters');
    });
});
