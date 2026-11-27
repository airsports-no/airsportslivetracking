// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ScoringExplanationPreview from './ScoringExplanationPreview';
import { qualityExplanation } from '../../../components/common/scoringExplanationFixtures';

const api = vi.hoisted(() => ({ fetchScoringExplanation: vi.fn() }));
vi.mock('../api', () => api);

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const changed = { ...qualityExplanation, headline: 'Changed headline for a perfect-flight scale.', qmax_policy: 'theoretical' as const };

describe('ScoringExplanationPreview', () => {
    let container: HTMLDivElement;
    let root: Root;

    beforeEach(() => {
        vi.useFakeTimers();
        api.fetchScoringExplanation.mockReset().mockResolvedValue(changed);
        container = document.createElement('div');
        document.body.appendChild(container);
        root = createRoot(container);
    });

    afterEach(() => {
        act(() => root.unmount());
        container.remove();
        vi.useRealTimers();
    });

    const render = (overrides: Record<string, string>, version: unknown = 'v1') =>
        act(() =>
            root.render(
                <ScoringExplanationPreview contestId={3} navigationTaskId={9} initial={qualityExplanation} overrides={overrides} scorecardVersion={version} />,
            ),
        );
    const settle = async () => {
        await act(async () => {
            await vi.advanceTimersByTimeAsync(500);
        });
    };

    it('shows the explanation of the saved scorecard without asking the server again', async () => {
        render({});
        await settle();
        expect(container.textContent).toContain(qualityExplanation.headline);
        expect(api.fetchScoringExplanation).not.toHaveBeenCalled();
        expect(container.textContent).not.toContain('follows the changes you have made');
    });

    it('asks for a new text when a scoring value is edited, with the edited value, and shows it', async () => {
        render({});
        render({ qmax_policy: 'theoretical' });
        await settle();
        expect(api.fetchScoringExplanation).toHaveBeenCalledTimes(1);
        expect(api.fetchScoringExplanation).toHaveBeenCalledWith(3, 9, { qmax_policy: 'theoretical' });
        expect(container.textContent).toContain(changed.headline);
        expect(container.textContent).toContain('follows the changes you have made');
    });

    it('waits for the typing to stop before it asks', async () => {
        render({});
        render({ task_value: '8' });
        await act(async () => {
            await vi.advanceTimersByTimeAsync(100);
        });
        render({ task_value: '80' });
        await settle();
        expect(api.fetchScoringExplanation).toHaveBeenCalledTimes(1);
        expect(api.fetchScoringExplanation).toHaveBeenCalledWith(3, 9, { task_value: '80' });
    });

    it('asks again, without changes, when the scorecard is loaded again (reset to standard)', async () => {
        render({});
        render({}, 'v2');
        await settle();
        expect(api.fetchScoringExplanation).toHaveBeenCalledWith(3, 9, {});
    });

    it('keeps the last text and says so when the new one cannot be fetched', async () => {
        api.fetchScoringExplanation.mockRejectedValue(new Error('offline'));
        render({});
        render({ qmax_policy: 'theoretical' });
        await settle();
        expect(container.textContent).toContain(qualityExplanation.headline);
        expect(container.textContent).toContain('Could not refresh this text');
    });
});
