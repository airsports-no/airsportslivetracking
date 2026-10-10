import { describe, expect, it } from 'vitest';
import { appEventUrl } from './appBridge';

describe('appBridge', () => {
    it('builds the private-scheme URL the apps intercept', () => {
        expect(appEventUrl('registered')).toBe('airsportsapp://registered');
        expect(appEventUrl('registered', { contestId: 1, navigationTaskId: 2 })).toBe(
            'airsportsapp://registered?contestId=1&navigationTaskId=2',
        );
    });

    it('encodes values so they cannot break out of the query', () => {
        expect(appEventUrl('x', { a: 'b&c=d' })).toBe('airsportsapp://x?a=b%26c%3Dd');
    });
});
