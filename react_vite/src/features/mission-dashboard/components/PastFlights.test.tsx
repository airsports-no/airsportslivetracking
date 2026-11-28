// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const flight = (id: number, task: number, declaration: unknown, order: unknown = null) => ({
    id, contest_id: 1, navigation_task: task, declaration_status: declaration, flight_order_status: order,
});
const state = vi.hoisted(() => ({ flights: [] as any[] }));
const stable = vi.hoisted(() => ({
    contests: [{ id: 1, name: 'Spring Cup', finish_time: '2026-05-02T10:00:00Z', country: 'NO' }],
    fetchMyPreviousFlights: async () => undefined,
    fetchContests: async () => undefined,
}));

vi.mock('../store', () => {
    const store: any = () => ({
        myPreviousFlights: state.flights,
        ...stable,
    });
    store.getState = () => ({ myPreviousFlights: state.flights });
    return { useMissionDashboardStore: store };
});
vi.mock('../../competition-map/api', () => ({
    fetchNavigationTask: async (_contestId: number, taskId: number) => ({ pk: taskId, name: `Task ${taskId}`, contestant_set: [] }),
}));
vi.mock('../components/TaskScoreDisplay', () => ({ default: () => <p>scores</p> }));
vi.mock('../components/ContestCard', () => ({ default: () => <p>Spring Cup card</p> }));
vi.mock('../../route-editor/components/basicComponents', () => ({ Loading: () => <p>loading</p> }));
vi.mock('../../pilot-declaration/api', () => ({ fetchDeclaration: vi.fn() }));
vi.mock('../../../utils/appBridge', () => ({ isEmbeddedInApp: () => false, signalApp: vi.fn() }));

import PastFlights from './PastFlights';

let container: HTMLDivElement;
let root: Root;

const declaration = (overrides: Record<string, unknown> = {}) => ({
    need: 'required', state: 'complete', errors: [], can_edit: false, edit_until: null, edit_url: '/declaration/11', ...overrides,
});

const open = async () => {
    await act(async () => {
        root.render(<MemoryRouter><PastFlights /></MemoryRouter>);
    });
    await act(async () => {
        (container.querySelector('.cursor-pointer') as HTMLElement).click();
    });
};

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(() => {
    act(() => root.unmount());
    container.remove();
});

describe('the declaration in past flights', () => {
    it('is shown read-only, with "View declaration", for a flight that had one', async () => {
        state.flights = [flight(11, 5, declaration())];
        await open();
        const summaries = container.querySelectorAll('[data-testid="past-flight-declaration"]');
        expect(summaries).toHaveLength(1);
        expect(summaries[0].textContent).toContain('View declaration');
        expect(summaries[0].querySelector('a')?.getAttribute('href')).toBe('/declaration/11');
        expect(summaries[0].textContent).not.toContain('Edit declaration');
    });

    it('is not shown for a task without a declaration or a declaration that was never made', async () => {
        state.flights = [flight(11, 5, declaration({ need: 'not_needed' })), flight(12, 5, declaration({ state: 'missing' })), flight(13, 5, undefined)];
        await open();
        expect(container.querySelectorAll('[data-testid="past-flight-declaration"]')).toHaveLength(0);
    });

    it('shows the flight order only when a download exists', async () => {
        state.flights = [
            flight(11, 5, declaration(), { state: 'ready', path: '/display/maplink/abc/', created_at: null, reason: null }),
            flight(12, 5, declaration({ edit_url: '/declaration/12' }), { state: 'waiting_for_declaration', path: null, created_at: null, reason: null }),
        ];
        await open();
        const summaries = Array.from(container.querySelectorAll('[data-testid="past-flight-declaration"]'));
        expect(summaries).toHaveLength(2);
        expect(summaries[0].textContent).toContain('Download flight order');
        expect(summaries[1].textContent).not.toContain('flight order');
    });
});
