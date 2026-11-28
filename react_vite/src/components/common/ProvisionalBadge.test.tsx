// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import ProvisionalBadge from './ProvisionalBadge';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const TEXT = 'Provisional: scores are scaled against the best pilot in the task. Final when all flights are finished.';

describe('ProvisionalBadge', () => {
    it('is closed at first: a badge whose title carries the explanation, and no panel', () => {
        const html = renderToStaticMarkup(<ProvisionalBadge text={TEXT} />);
        expect(html).toContain('Provisional');
        expect(html).toContain(`title="${TEXT}"`);
        expect(html).toContain('aria-expanded="false"');
        expect(html).not.toContain('role="note"');
    });

    describe('opened by touch', () => {
        let container: HTMLDivElement;
        let root: Root;

        beforeEach(() => {
            container = document.createElement('div');
            document.body.appendChild(container);
            root = createRoot(container);
            act(() => root.render(<div><ProvisionalBadge text={TEXT} /><p id="elsewhere">elsewhere</p></div>));
        });

        afterEach(() => {
            act(() => root.unmount());
            container.remove();
        });

        const badge = () => container.querySelector('[data-testid="provisional-badge"]') as HTMLButtonElement;
        const panel = () => container.querySelector('[data-testid="provisional-explanation"]');

        it('opens the explanation on a click or tap and closes it on a second one', () => {
            act(() => badge().click());
            expect(panel()?.textContent).toBe(TEXT);
            expect(badge().getAttribute('aria-expanded')).toBe('true');
            act(() => badge().click());
            expect(panel()).toBeNull();
        });

        it('closes when something else is touched, and on Escape', () => {
            act(() => badge().click());
            act(() => {
                document.getElementById('elsewhere')!.dispatchEvent(new Event('pointerdown', { bubbles: true }));
            });
            expect(panel()).toBeNull();
            act(() => badge().click());
            expect(panel()).not.toBeNull();
            act(() => {
                document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
            });
            expect(panel()).toBeNull();
        });

        it('stays open when the panel itself is touched, so its text can be read and selected', () => {
            act(() => badge().click());
            act(() => {
                panel()!.dispatchEvent(new Event('pointerdown', { bubbles: true }));
            });
            expect(panel()).not.toBeNull();
        });
    });
});
