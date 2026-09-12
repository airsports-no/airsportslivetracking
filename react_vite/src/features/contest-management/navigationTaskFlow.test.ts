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

    it('resolves a local time shortly before the spring-forward transition to the pre-transition offset', () => {
        // Europe/Oslo's 2026 spring-forward is at 2026-03-29 01:00 UTC (02:00->03:00 local).
        // 01:30 local is a valid, unambiguous time *before* the gap - naively treating it as UTC
        // lands after the transition instant and would wrongly resolve to +02:00.
        expect(contestLocalTimeToIso('2026-03-29T01:30', 'Europe/Oslo')).toBe('2026-03-29T01:30:00+01:00');
    });

    it('resolves a local time shortly after the autumn fall-back transition to the post-transition offset', () => {
        // Europe/Oslo's 2026 fall-back is at 2026-10-25 01:00 UTC (03:00 CEST -> 02:00 CET local);
        // local 02:00-02:59 is the ambiguous, repeated hour. 03:30 local is unambiguously after
        // it, at +01:00 (CET) - naively treating it as UTC would still land after the transition
        // instant here, so this mainly guards against a future regression rather than the bug
        // itself (which only bites the transition's immediate vicinity).
        expect(contestLocalTimeToIso('2026-10-25T03:30', 'Europe/Oslo')).toBe('2026-10-25T03:30:00+01:00');
    });

    it('still resolves an ordinary time on the same day as a DST transition correctly', () => {
        // Well after the spring-forward gap, on the same day.
        expect(contestLocalTimeToIso('2026-03-29T12:00', 'Europe/Oslo')).toBe('2026-03-29T12:00:00+02:00');
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
