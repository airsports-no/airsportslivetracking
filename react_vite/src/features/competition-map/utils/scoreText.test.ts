import { describe, expect, it } from 'vitest';
import { shortScoreText } from './scoreText';

// Messages as found in the score logs (the most common kinds with points).
describe('shortScoreText', () => {
    it('keeps the corridor penalty and drops the leg scores and total', () => {
        expect(shortScoreText('outside corridor (19 s). Leg scores: [WP 1: 42.0]. Total: 42.0')).toBe('Outside corridor 19 s');
        expect(shortScoreText('outside corridor (142 s). Leg scores: [TP2: 54.0, TP3: 357.0]. Total: 411.0')).toBe('Outside corridor 142 s');
        expect(shortScoreText('outside corridor (131 s). Total: 378.0')).toBe('Outside corridor 131 s');
        expect(shortScoreText('outside corridor (11 s)')).toBe('Outside corridor 11 s');
        expect(shortScoreText('outside corridor (3 seconds)')).toBe('Outside corridor 3 s');
        expect(shortScoreText('outside corridor (10 seconds) (capped)')).toBe('Outside corridor 10 s (capped)');
    });

    it('names the penalty zone and the time in it', () => {
        expect(shortScoreText('inside penalty zone P5 (12s)')).toBe('In penalty zone P5, 12 s');
        expect(shortScoreText('inside penalty zone   (34s)')).toBe('In penalty zone, 34 s');
        expect(shortScoreText('inside penalty zone odra zachód (10s)')).toBe('In penalty zone odra zachód, 10 s');
        expect(shortScoreText('inside penalty zone P4')).toBe('In penalty zone P4');
    });

    it('tidies gate and prohibited zone messages', () => {
        expect(shortScoreText('passing gate (+21 s)')).toBe('Passing gate +21 s');
        expect(shortScoreText('passing gate')).toBe('Passing gate');
        expect(shortScoreText('entered prohibited zone :')).toBe('Entered prohibited zone');
        expect(shortScoreText('entered prohibited zone P2')).toBe('Entered prohibited zone P2');
    });

    it('passes other messages through with a capital letter', () => {
        expect(shortScoreText('missing gate')).toBe('Missing gate');
        expect(shortScoreText('Received card 8 of diamonds, current hand is High Card')).toBe('Received card 8 of diamonds, current hand is High Card');
        expect(shortScoreText('crossing extended starting gate backwards')).toBe('Crossing extended starting gate backwards');
    });
});
