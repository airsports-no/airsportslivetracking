// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ScoringChoiceNote, { ScoringChoiceView } from './ScoringChoiceNote';
import { penaltyExplanation, qualityExplanation } from '../../../components/common/scoringExplanationFixtures';

const api = vi.hoisted(() => ({ fetchTaskTypeExplanation: vi.fn() }));
vi.mock('../api', () => api);

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

describe('ScoringChoiceView', () => {
    it('says that scores follow the best pilot and can change until everyone has flown, and offers the choice', () => {
        const html = renderToStaticMarkup(<ScoringChoiceView explanation={qualityExplanation} value="" onChange={() => {}} />);
        expect(html).toContain('How this task is scored');
        expect(html).toContain(qualityExplanation.headline);
        expect(html).toContain('can change until everyone has flown');
        expect(html).toContain('How is the best score determined?');
        expect(html.match(/type="radio"/g)).toHaveLength(2);
        expect(html).toContain('Scaled against a perfect flight');
    });

    it('preselects the default of the rules while nothing is chosen, and the choice once it is made', () => {
        const blank = renderToStaticMarkup(<ScoringChoiceView explanation={qualityExplanation} value="" onChange={() => {}} />);
        expect(blank.match(/checked=""/g)).toHaveLength(1);
        expect(blank).toMatch(/value="best_in_task"[^>]*checked=""|checked=""[^>]*value="best_in_task"/);
        const chosen = renderToStaticMarkup(<ScoringChoiceView explanation={qualityExplanation} value="theoretical" onChange={() => {}} />);
        expect(chosen).toMatch(/value="theoretical"[^>]*checked=""|checked=""[^>]*value="theoretical"/);
    });

    it('offers no choice where the task type has only one way to score', () => {
        const fixed = { ...qualityExplanation, qmax: { ...qualityExplanation.qmax, offered: false, options: [qualityExplanation.qmax.options[0]] } };
        const html = renderToStaticMarkup(<ScoringChoiceView explanation={fixed} value="" onChange={() => {}} />);
        expect(html).not.toContain('type="radio"');
        expect(html).toContain(qualityExplanation.headline);
    });
});

describe('ScoringChoiceNote', () => {
    let container: HTMLDivElement;
    let root: Root;

    beforeEach(() => {
        api.fetchTaskTypeExplanation.mockReset();
        container = document.createElement('div');
        document.body.appendChild(container);
        root = createRoot(container);
    });

    afterEach(() => {
        act(() => root.unmount());
        container.remove();
    });

    const render = async (onChange = vi.fn(), value = '') => {
        await act(async () => {
            root.render(<ScoringChoiceNote taskSubtype="precision_navigation" scorecard="CIMA Precision" value={value} onChange={onChange} />);
        });
        return onChange;
    };

    it('asks for the explanation of the chosen task type and scorecard, with the choice made so far', async () => {
        api.fetchTaskTypeExplanation.mockResolvedValue(qualityExplanation);
        await render(vi.fn(), 'theoretical');
        expect(api.fetchTaskTypeExplanation).toHaveBeenCalledWith('precision_navigation', 'CIMA Precision', { qmax_policy: 'theoretical' });
        expect(container.querySelector('[data-testid="scoring-choice-note"]')).not.toBeNull();
    });

    it('reports the organiser’s choice', async () => {
        api.fetchTaskTypeExplanation.mockResolvedValue(qualityExplanation);
        const onChange = await render();
        const radio = container.querySelector('input[value="theoretical"]') as HTMLInputElement;
        await act(async () => radio.click());
        expect(onChange).toHaveBeenCalledWith('theoretical');
    });

    it('shows nothing for a task that is scored with penalty points', async () => {
        api.fetchTaskTypeExplanation.mockResolvedValue(penaltyExplanation);
        await render();
        expect(container.innerHTML).toBe('');
    });

    it('does not stop the task from being created when the explanation cannot be fetched', async () => {
        api.fetchTaskTypeExplanation.mockRejectedValue(new Error('offline'));
        await render();
        expect(container.innerHTML).toBe('');
    });
});
