import { describe, expect, it } from 'vitest';
import {
    didNotFly,
    formatScoreOutOf,
    formatTaskScore,
    isPenaltyEntry,
    logPointsText,
    penaltyConsequence,
    replayTaskScores,
    roundHalfUp,
    scoreArithmetic,
    scoreHeading,
    scoresAreProvisional,
    sortByScore,
    sortDirection,
    TaskScoring,
} from './taskScore';

const quality: TaskScoring = { scoring_model: 'quality', qmax_policy: 'best_in_task', task_value: 1000, scores_provisional: true };
const penalties: TaskScoring = { scoring_model: 'penalties', qmax_policy: 'best_in_task', task_value: 1000 };

describe('formatting', () => {
    it('shows a quality score as a whole number and out of the task value', () => {
        expect(formatTaskScore(874.4, quality)).toBe('874');
        expect(formatTaskScore(874.5, quality)).toBe('875');
        expect(formatScoreOutOf(874, quality)).toBe('874 / 1000');
        expect(scoreHeading(quality)).toBe('Score (of 1000)');
        expect(formatScoreOutOf(500, { ...quality, task_value: 1500 })).toBe('500 / 1500');
    });
    it('keeps the formatting of a penalty task, and of a task that says nothing', () => {
        expect(formatTaskScore(42.4, penalties)).toBe('42');
        expect(formatTaskScore(42.45, penalties, 1)).toBe('42.5');
        expect(formatScoreOutOf(42.4, penalties)).toBe('42');
        expect(scoreHeading(penalties)).toBe('Score');
        expect(formatTaskScore(7, undefined)).toBe('7');
        expect(formatScoreOutOf(7, null)).toBe('7');
        expect(scoreHeading(undefined, 'Points')).toBe('Points');
    });
    it('rounds half up like the backend', () => {
        expect(roundHalfUp(874.5)).toBe(875);
        expect(roundHalfUp(875.5)).toBe(876);
        expect(roundHalfUp(874.4999)).toBe(874);
    });
});

describe('ordering', () => {
    const rows = [{ s: 100 }, { s: 900 }, { s: 500 }];
    it('puts the highest quality score first even on an ascending scorecard', () => {
        expect(sortDirection(quality, 'asc')).toBe('desc');
        expect(sortByScore(rows, r => r.s, quality, 'asc').map(r => r.s)).toEqual([900, 500, 100]);
    });
    it('follows the scorecard for a penalty task', () => {
        expect(sortByScore(rows, r => r.s, penalties, 'asc').map(r => r.s)).toEqual([100, 500, 900]);
        expect(sortByScore(rows, r => r.s, penalties, 'desc').map(r => r.s)).toEqual([900, 500, 100]);
        expect(sortByScore(rows, r => r.s, undefined, 'asc').map(r => r.s)).toEqual([100, 500, 900]);
    });
    it('does not change its input', () => {
        const input = [{ s: 2 }, { s: 1 }];
        sortByScore(input, r => r.s, penalties, 'asc');
        expect(input.map(r => r.s)).toEqual([2, 1]);
    });
});

describe('provisional', () => {
    it('is provisional while a flight is not finished', () => {
        expect(scoresAreProvisional(quality, [{ calculator_finished: true }, { calculator_finished: false }])).toBe(true);
        expect(scoresAreProvisional(quality, [{ calculator_finished: true }, { calculator_finished: true }])).toBe(false);
    });
    it('follows the API flag without tracks, and never applies to a penalty task', () => {
        expect(scoresAreProvisional(quality)).toBe(true);
        expect(scoresAreProvisional({ ...quality, scores_provisional: false })).toBe(false);
        expect(scoresAreProvisional(penalties, [{ calculator_finished: false }])).toBe(false);
        expect(scoresAreProvisional(undefined, [{ calculator_finished: false }])).toBe(false);
    });
});

describe('did not fly', () => {
    it('is only for a quality task', () => {
        expect(didNotFly(quality, { calculator_started: false })).toBe(true);
        expect(didNotFly(quality, { calculator_started: true })).toBe(false);
        expect(didNotFly(quality, null)).toBe(true);
        expect(didNotFly(penalties, { calculator_started: false })).toBe(false);
    });
});

describe('score log entries', () => {
    it('shows a quality penalty, achievement and percentage penalty as raw points and a percentage', () => {
        expect(logPointsText({ points: -12, score_kind: 'penalty' }, quality, false)).toMatchObject({ text: '−12 raw', penalty: true });
        expect(logPointsText({ points: 100, score_kind: 'achievement' }, quality, false)).toMatchObject({ text: '+100 raw', penalty: false });
        expect(logPointsText({ points: 50, score_kind: 'percentage_penalty' }, quality, false)).toMatchObject({
            text: '−50% of task score',
            penalty: true,
        });
        expect(logPointsText({ points: 0, score_kind: 'penalty' }, quality, false).text).toBe('0 raw');
    });
    it('reads the sign when an older entry has no kind', () => {
        expect(logPointsText({ points: -3 }, quality, false)).toMatchObject({ text: '−3 raw', penalty: true });
        expect(logPointsText({ points: 3 }, quality, false)).toMatchObject({ text: '+3 raw', penalty: false });
    });
    it('formats a penalty task exactly as before', () => {
        expect(logPointsText({ points: 12 }, penalties, true)).toEqual({ text: '+12', penalty: true, title: '' });
        expect(logPointsText({ points: -12 }, penalties, true)).toEqual({ text: '-12', penalty: false, title: '' });
        expect(logPointsText({ points: 0 }, penalties, true).text).toBe('0');
        expect(logPointsText({ points: 12.6 }, undefined, false)).toMatchObject({ text: '+13', penalty: false });
        expect(isPenaltyEntry({ points: -4 }, penalties, false)).toBe(true);
    });
});

describe('score log entries that carry a measure', () => {
    // As the backend sends them with the task (the registry's relative quality terms)
    const scoring = {
        scoring_model: 'quality',
        score_measures: {
            contract_points: { symbol: 'V', unit: '', is_change: true },
            speed_term: { symbol: 'S', unit: 'kt', is_change: false },
        },
    };
    it('shows the declared points as a change of V', () => {
        expect(logPointsText({ points: 1, score_kind: 'achievement', score_type: 'contract_points' }, scoring, false)).toMatchObject({ text: 'V +1', penalty: false });
        expect(logPointsText({ points: -1, score_kind: 'penalty', score_type: 'contract_points' }, scoring, false)).toMatchObject({ text: 'V −1', penalty: true });
    });
    it('shows the speed as a value in knots', () => {
        const shown = logPointsText({ points: 62.4, score_kind: 'achievement', score_type: 'speed_term' }, scoring, false);
        expect(shown).toMatchObject({ text: 'S = 62.4 kt', penalty: false });
        expect(shown.title).toContain('not points of Q');
    });
    it('does not call a measure raw points', () => {
        for (const entry of [{ points: 1, score_type: 'contract_points' }, { points: 62.4, score_type: 'speed_term' }]) {
            expect(logPointsText(entry, scoring, false).text).not.toContain('raw');
        }
    });
    it('leaves every other entry, and a task that declares no measures, as raw points', () => {
        expect(logPointsText({ points: 60, score_kind: 'achievement', score_type: 'duration_score' }, scoring, false).text).toBe('+60 raw');
        expect(logPointsText({ points: 1, score_kind: 'achievement', score_type: 'contract_points' }, quality, false).text).toBe('+1 raw');
    });
    it('is not applied to a task of the penalty model', () => {
        expect(logPointsText({ points: 1, score_type: 'contract_points' }, { ...scoring, scoring_model: 'penalties' }, true).text).toBe('+1');
    });
});

describe('the arithmetic of a score', () => {
    const tracks = [
        { calculator_started: true, raw_quality: 812, score: 437, percentage_penalty: 50 },
        { calculator_started: true, raw_quality: 930, score: 1000 },
        { calculator_started: false, raw_quality: 5000 },
    ];
    it('shows Q of the best, the scaled score and the percentage penalty', () => {
        const result = scoreArithmetic(quality, tracks[0], tracks);
        expect(result?.text).toBe('Q 812 of best 930 → 873; −50% → 437');
        expect(result?.reference).toBe(930);
    });
    it('leaves out the percentage when there is none', () => {
        expect(scoreArithmetic(quality, tracks[1], tracks)?.text).toBe('Q 930 of best 930 → 1000');
    });
    it('uses the contestants own maximum under the theoretical policy and the scale under the absolute one', () => {
        const theoretical = { ...quality, qmax_policy: 'theoretical' };
        expect(scoreArithmetic(theoretical, { calculator_started: true, raw_quality: 900, quality_theoretical_maximum: 1200, score: 750 }, [])?.text)
            .toBe('Q 900 of maximum 1200 → 750');
        const absolute = { ...quality, qmax_policy: 'absolute', qmax_absolute_reference: 2000 };
        expect(scoreArithmetic(absolute, { calculator_started: true, raw_quality: 1500, score: 750 }, [])?.text).toBe('Q 1500 of scale 2000 → 750');
        expect(scoreArithmetic({ ...quality, qmax_policy: 'absolute' }, { calculator_started: true, raw_quality: 200, score: 200 }, [])?.text).toBe('Q 200 → 200');
    });
    it('is null for a contestant who did not fly and for a penalty task', () => {
        expect(scoreArithmetic(quality, tracks[2], tracks)).toBeNull();
        expect(scoreArithmetic(penalties, tracks[0], tracks)).toBeNull();
    });
});

describe('what a penalty will do', () => {
    it('says it in words for a quality task', () => {
        expect(penaltyConsequence(quality, 'percentage', 50)).toBe('Reduces the task score by 50% after it has been scaled.');
        expect(penaltyConsequence(quality, 'percentage', 100)).toMatch(/to 0/);
        expect(penaltyConsequence(quality, 'points', 12)).toMatch(/12 raw points off/);
        expect(penaltyConsequence(quality, 'points', -5)).toMatch(/5 raw points back/);
    });
    it('says nothing for a penalty task', () => {
        expect(penaltyConsequence(penalties, 'points', 12)).toBe('');
    });
});

describe('replay scores', () => {
    const at = new Date('2026-01-01T08:30:00Z');
    const entry = (minute: number, points: number, score_kind?: string) => ({ time: `2026-01-01T08:${minute}:00Z`, points, score_kind });
    it('derives the task scores from the raw points up to the replay time', () => {
        const contestants = [
            { id: 1, started: true, start: 1200, theoretical: 1200, entries: [] },
            { id: 2, started: true, start: 1200, theoretical: 1200, entries: [entry(10, -300, 'penalty'), entry(50, -300, 'penalty')] },
            { id: 3, started: false, start: null, theoretical: null, entries: [] },
        ];
        expect(replayTaskScores(quality, contestants, at)).toEqual({ 1: 1000, 2: 750, 3: 0 });
        // later in the replay the second penalty has happened
        expect(replayTaskScores(quality, contestants, new Date('2026-01-01T08:59:00Z'))).toEqual({ 1: 1000, 2: 500, 3: 0 });
    });
    it('takes percentage penalties off afterwards', () => {
        const contestants = [{ id: 1, started: true, start: 1000, theoretical: 1000, entries: [entry(5, 50, 'percentage_penalty')] }];
        expect(replayTaskScores(quality, contestants, at)).toEqual({ 1: 500 });
    });
});
