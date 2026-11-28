import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import RankingList, { RankingRow } from './RankingList';
import NavLog from './NavLog';
import { ScoreLogEntry } from '../../types';
import { PROVISIONAL_HELP } from '../../../../utils/taskScore';
import { qualityExplanation } from '../../../../components/common/scoringExplanationFixtures';

const quality = { scoring_model: 'quality', task_value: 1000 };
const penalties = { scoring_model: 'penalties', task_value: 1000 };
const rows: RankingRow[] = [
    { id: 1, name: '#1 A', score: 874.4, state: 'Finished' },
    { id: 2, name: '#2 B', score: 'DNF', state: 'Finished' },
];

const ranking = (props: Partial<React.ComponentProps<typeof RankingList>> = {}) =>
    renderToStaticMarkup(<RankingList rows={rows} onSelect={() => {}} {...props} />);

describe('RankingList', () => {
    it('shows a quality score as a whole number under a heading with the task value', () => {
        const html = ranking({ scoring: quality });
        expect(html).toContain('Score (of 1000)');
        expect(html).toContain('>874<');
    });
    it('labels a contestant who did not fly DNF, with its meaning', () => {
        const html = ranking({ scoring: quality });
        expect(html).toContain('>DNF<');
        expect(html).toContain('Did Not Fly');
    });
    it('marks provisional scores with a badge that explains itself, and only while they are provisional', () => {
        expect(ranking({ scoring: quality, provisional: true })).toContain('Provisional');
        expect(ranking({ scoring: quality, provisional: true })).toContain(`title="${PROVISIONAL_HELP}"`);
        expect(ranking({ scoring: quality, provisional: false })).not.toContain('Provisional');
    });
    it('uses the explanation the server wrote for the task, where it sent one', () => {
        const html = ranking({ scoring: { ...quality, scoring_explanation: { ...qualityExplanation, provisional: { ...qualityExplanation.provisional, short: 'Written by the server.' } } }, provisional: true });
        expect(html).toContain('title="Written by the server."');
        expect(html).not.toContain(PROVISIONAL_HELP);
    });
    it('renders a penalty task as it always did: no heading, no badge', () => {
        const html = ranking({ scoring: penalties, provisional: true });
        expect(html).not.toContain('Score (of');
        expect(html).not.toContain('Provisional');
        expect(html).toContain('>874<');
        expect(ranking()).toBe(ranking({ scoring: penalties }));
    });
});

const entry = (id: number, points: number, score_kind: string): ScoreLogEntry => ({
    id, time: '2026-01-01T08:10:00Z', gate: 'TP1', message: 'missed gate', string: '', points, type: 'anomaly', contestant: 1, score_kind,
});
const navLog = (props: Partial<React.ComponentProps<typeof NavLog>>) =>
    renderToStaticMarkup(
        <NavLog entries={[entry(1, -12, 'penalty'), entry(2, 100, 'achievement'), entry(3, 50, 'percentage_penalty')]}
            pointsArePenalties={false} locatableIds={new Set()} onSelect={() => {}} timeZone="UTC" {...props} />,
    );

describe('NavLog', () => {
    it('shows raw points with their meaning for a quality task, and the arithmetic', () => {
        const html = navLog({ scoring: quality, provisional: true, arithmetic: 'Q 812 of best 930 → 873; −50% → 437' });
        expect(html).toContain('−12 raw');
        expect(html).toContain('+100 raw');
        expect(html).toContain('−50% of task score');
        expect(html).toContain('raw quality points (Q)');
        expect(html).toContain('Q 812 of best 930');
        expect(html).toContain(PROVISIONAL_HELP);
    });
    it('shows a penalty task exactly as before', () => {
        const html = navLog({ scoring: penalties, pointsArePenalties: true });
        expect(html).not.toContain('raw');
        expect(html).toContain('>-12<');
        expect(html).toContain('>+100<');
        expect(html).toContain('>+50<');
    });
});
