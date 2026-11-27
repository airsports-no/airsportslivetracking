import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import ScoringExplanationCard from './ScoringExplanationCard';
import { penaltyExplanation, qualityExplanation } from './scoringExplanationFixtures';

describe('ScoringExplanationCard', () => {
    it('shows every part of a CIMA task explanation, the provisional warning and the choice of the best score', () => {
        const html = renderToStaticMarkup(<ScoringExplanationCard explanation={qualityExplanation} />);
        expect(html).toContain('How this task is scored');
        expect(html).toContain(qualityExplanation.headline);
        for (const line of qualityExplanation.raw_points) expect(html).toContain(line);
        expect(html).toContain('From raw points to the task score');
        expect(html).toContain('Backtracking: each backtrack costs 50% of the task score.');
        expect(html).toContain('Can the score change after landing?');
        expect(html).toContain('alert-warning');
        expect(html).toContain('How the best score is determined');
        expect(html).toContain('Scaled against a perfect flight');
        expect(html).toContain('In use');
    });

    it('leaves out the sections a task does not have', () => {
        const html = renderToStaticMarkup(<ScoringExplanationCard explanation={qualityExplanation} />);
        expect(html).not.toContain('Always shared against the best pilot');
        const withTerm = renderToStaticMarkup(
            <ScoringExplanationCard explanation={{ ...qualityExplanation, relative_terms: ['Speed term: not used in this task.'] }} />,
        );
        expect(withTerm).toContain('Always shared against the best pilot');
        expect(withTerm).toContain('Speed term: not used in this task.');
    });

    it('explains a penalty task briefly, without the quality sections', () => {
        const html = renderToStaticMarkup(<ScoringExplanationCard explanation={penaltyExplanation} />);
        expect(html).toContain('Penalty points are added up; the lowest total wins.');
        expect(html).not.toContain('From raw points to the task score');
        expect(html).not.toContain('Can the score change after landing?');
        expect(html).not.toContain('How the best score is determined');
    });

    it('shows a footer, such as the link to the scorecard', () => {
        const html = renderToStaticMarkup(<ScoringExplanationCard explanation={qualityExplanation} footer={<a href="/scorecard">Open the scorecard</a>} />);
        expect(html).toContain('Open the scorecard');
    });
});
