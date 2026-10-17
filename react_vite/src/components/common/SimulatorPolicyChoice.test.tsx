import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import SimulatorPolicyChoice from './SimulatorPolicyChoice';

const render = (props: Partial<React.ComponentProps<typeof SimulatorPolicyChoice>> = {}) =>
    renderToStaticMarkup(<SimulatorPolicyChoice value="not_allowed" onChange={() => {}} {...props} />);

describe('SimulatorPolicyChoice', () => {
    it('asks who will fly the task and offers the three policies in plain words', () => {
        const html = render();
        expect(html).toContain('Who will fly this task?');
        expect(html).toContain('Real pilots only');
        expect(html).toContain('Real and simulator pilots');
        expect(html).toContain('Simulator pilots only');
        expect(html.match(/type="radio"/g)).toHaveLength(3);
    });

    it('checks the chosen policy only', () => {
        const html = render({ value: 'simulator_only' });
        expect(html.match(/checked=""/g)).toHaveLength(1);
        expect(html).toMatch(/value="simulator_only"[^>]*checked=""|checked=""[^>]*value="simulator_only"/);
    });

    it('suggests self-management for a simulator-only task that has it off, and only then', () => {
        expect(render({ value: 'simulator_only', suggestSelfManagement: true })).toContain('Allow self-management');
        expect(render({ value: 'simulator_only', suggestSelfManagement: false })).not.toContain('Allow self-management');
        expect(render({ value: 'not_allowed', suggestSelfManagement: true })).not.toContain('Allow self-management');
    });
});
