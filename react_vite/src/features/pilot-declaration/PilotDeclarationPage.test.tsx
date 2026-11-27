// @vitest-environment jsdom
import React, { act, useEffect } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DeclarationForm, PilotDeclaration } from './types';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({ fetchDeclaration: vi.fn(), saveDeclaration: vi.fn() }));
const bridge = vi.hoisted(() => ({ isEmbeddedInApp: vi.fn(() => false), signalApp: vi.fn() }));
vi.mock('./api', async () => {
    class DeclarationApiError extends Error {
        status: number;
        constructor(message: string, status: number) {
            super(message);
            this.status = status;
        }
    }
    return { ...api, DeclarationApiError };
});
vi.mock('../../utils/appBridge', () => bridge);

import PilotDeclarationPage from './PilotDeclarationPage';

const TIMES: DeclarationForm = {
    time_points: ['TP1', 'FP'], declares_times: true, time_key: 'known_time_gate_predictions',
    adaptive_start: false, start_point_time: '2026-08-01T08:00:00+00:00',
};
const CONTRACT: DeclarationForm = {
    mandatory_points: ['SP', 'MP', 'FP'], turnpoints: ['A', 'B'], asks_for_period: true, declares_times: false, time_key: null,
};
const HUNT: DeclarationForm = {
    compulsory_points: ['CP1', 'CP2'], targets: ['T1', 'T2'], asks_for_fuel_endurance: true, declares_times: true,
    time_key: 'compulsory_point_times', start_point_time: '2026-08-01T08:00:00+00:00',
};

const make = (form: DeclarationForm, overrides: Partial<PilotDeclaration> = {}, status: Partial<PilotDeclaration['status']> = {}): PilotDeclaration => ({
    contestant_id: 5,
    contest_id: 1,
    navigation_task_id: 2,
    contest_name: 'Summer Cup',
    navigation_task_name: 'Navigation 1',
    time_zone: 'Europe/Oslo',
    task_type: 'x',
    status: {
        need: 'required', state: 'missing', errors: ['Give a time for TP1 and FP.'], can_edit: true,
        edit_until: '2026-08-01T07:55:00+00:00', edit_url: '/declaration/5', ...status,
    },
    read_only_reason: null,
    flight_order_status: null,
    declaration_payload: {},
    form,
    ...overrides,
});

let container: HTMLDivElement;
let root: Root;
let seenPath = '';

const Where = () => {
    const { pathname } = useLocation();
    useEffect(() => {
        seenPath = pathname;
    });
    return null;
};

const mount = async (declaration: PilotDeclaration | Error, url = '/declaration/5') => {
    if (declaration instanceof Error) api.fetchDeclaration.mockRejectedValue(declaration);
    else api.fetchDeclaration.mockResolvedValue(declaration);
    await act(async () => {
        root.render(
            <MemoryRouter initialEntries={[url]}>
                <Where />
                <Routes>
                    <Route path="/declaration/:contestantId" element={<PilotDeclarationPage />} />
                    <Route path="*" element={<p>elsewhere</p>} />
                </Routes>
            </MemoryRouter>,
        );
    });
};

const type = (element: Element, value: string) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
    act(() => {
        setter.call(element, value);
        element.dispatchEvent(new Event('input', { bubbles: true }));
    });
};
const input = (label: string) => container.querySelector(`input[aria-label="${label}"]`) as HTMLInputElement;
const button = (text: string | RegExp) =>
    Array.from(container.querySelectorAll('button')).find((b) => (typeof text === 'string' ? b.textContent?.trim() === text : text.test(b.textContent ?? ''))) as HTMLButtonElement | undefined;
const byLabel = (label: string) => container.querySelector(`[aria-label="${label}"]`) as HTMLButtonElement;
const click = async (element: Element | undefined | null) => {
    expect(element).toBeTruthy();
    await act(async () => (element as HTMLElement).click());
};
const submit = async () => {
    await act(async () => {
        container.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    });
};

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    api.fetchDeclaration.mockReset();
    api.saveDeclaration.mockReset();
    bridge.signalApp.mockReset();
    bridge.isEmbeddedInApp.mockReset();
    bridge.isEmbeddedInApp.mockReturnValue(false);
});
afterEach(() => {
    act(() => root.unmount());
    container.remove();
});

describe('times', () => {
    it('are entered as minutes and seconds with the clock time next to them, and sent after the start point', async () => {
        await mount(make(TIMES));
        expect(container.textContent).toContain('Summer Cup');
        expect(container.textContent).toContain('You can change this until 09:55 on 1 August 2026 (Europe/Oslo time).');
        expect(container.textContent).toContain('Give a time for TP1 and FP.');
        type(input('TP1, minutes after the start point'), '12');
        type(input('TP1, seconds'), '30');
        // The start point is at 10:00 in Oslo (08:00 UTC)
        expect(container.querySelector('[data-testid="clock-TP1"]')?.textContent).toContain('10:12:30');

        api.saveDeclaration.mockResolvedValue(make(TIMES, { declaration_payload: { time_reference: 'start_point', relative_times: { TP1: 750 } } }, { state: 'incomplete', errors: ['Give a time for FP.'] }));
        await submit();
        expect(api.saveDeclaration).toHaveBeenCalledWith(5, { known_time_gate_predictions: { TP1: 750 }, time_reference: 'start_point' });
    });

    it('say plainly that there is no clock time with an adaptive start', async () => {
        await mount(make({ ...TIMES, adaptive_start: true, start_point_time: null }));
        expect(container.querySelector('[data-testid="adaptive-note"]')?.textContent).toContain('count from when you cross the start');
        type(input('TP1, minutes after the start point'), '5');
        expect(container.querySelector('[data-testid="clock-TP1"]')).toBeNull();
    });

    it('with seconds over 59 are not sent and nothing is lost', async () => {
        await mount(make(TIMES));
        type(input('TP1, minutes after the start point'), '1');
        type(input('TP1, seconds'), '75');
        await submit();
        expect(api.saveDeclaration).not.toHaveBeenCalled();
        expect(container.querySelector('[data-testid="declaration-problems"]')).toBeTruthy();
        expect(input('TP1, seconds').value).toBe('75');
    });
});

describe('saving', () => {
    it('an incomplete declaration is saved and says it is not finished and what is missing', async () => {
        await mount(make(TIMES));
        type(input('TP1, minutes after the start point'), '10');
        api.saveDeclaration.mockResolvedValue(make(TIMES, {}, { state: 'incomplete', errors: ['Give a time for FP.'] }));
        await submit();
        const banner = container.querySelector('[data-testid="declaration-unfinished"]')!;
        expect(banner.textContent).toContain('Saved, but not finished yet.');
        expect(banner.textContent).toContain('Give a time for FP.');
    });

    it('a complete declaration says so and shows that the flight order is being made', async () => {
        await mount(make(TIMES));
        type(input('TP1, minutes after the start point'), '10');
        api.saveDeclaration.mockResolvedValue(
            make(TIMES, { flight_order_status: { state: 'being_made', path: null, created_at: null, reason: null } }, { state: 'complete', errors: [] }),
        );
        await submit();
        expect(container.textContent).toContain('Saved. Your declaration is complete.');
        expect(container.querySelector('[data-testid="flight-order-being-made"]')?.textContent).toContain('Your flight order is being made');
    });

    it('a failed save keeps everything typed and says so', async () => {
        await mount(make(TIMES));
        type(input('TP1, minutes after the start point'), '10');
        type(input('TP1, seconds'), '20');
        api.saveDeclaration.mockRejectedValue(new Error('The server is not reachable.'));
        await submit();
        const alert = container.querySelector('[data-testid="declaration-save-error"]')!;
        expect(alert.textContent).toContain('Not saved.');
        expect(alert.textContent).toContain('The server is not reachable.');
        expect(input('TP1, minutes after the start point').value).toBe('10');
        expect(input('TP1, seconds').value).toBe('20');
        // and it can be tried again
        api.saveDeclaration.mockResolvedValue(make(TIMES, {}, { state: 'incomplete' }));
        await submit();
        expect(api.saveDeclaration).toHaveBeenCalledTimes(2);
        expect(container.querySelector('[data-testid="declaration-save-error"]')).toBeNull();
    });
});

describe('a sequence with mandatory points (2.A3)', () => {
    it('is chosen by tapping, reordered with the buttons, and sent with SP, MP, FP and the period', async () => {
        await mount(make(CONTRACT, {}, { errors: ['Choose the turn points you will fly.'] }));
        expect(container.querySelector('[data-testid="anchor-MP"]')).toBeTruthy();
        const lane0 = () => container.querySelector('[data-testid="lane-0"]')!;
        await click(lane0().querySelector('button[aria-expanded]'));
        await click(Array.from(lane0().querySelectorAll('button')).find((b) => b.textContent === 'A'));
        // The list of points stays open to add more
        await click(Array.from(lane0().querySelectorAll('button')).find((b) => b.textContent === 'B'));
        expect(Array.from(lane0().querySelectorAll('[data-testid="lane-0-item"]')).map((li) => li.textContent?.trim().slice(0, 1))).toEqual(['A', 'B']);
        await click(byLabel('Move B up'));
        expect(Array.from(lane0().querySelectorAll('[data-testid="lane-0-item"]')).map((li) => li.textContent?.trim().slice(0, 1))).toEqual(['B', 'A']);
        type(input('Period T, minutes after the start point'), '1');
        type(input('Period T, seconds'), '22');

        api.saveDeclaration.mockResolvedValue(make(CONTRACT, {}, { state: 'complete', errors: [] }));
        await submit();
        expect(api.saveDeclaration).toHaveBeenCalledWith(5, { declared_sequence: ['SP', 'B', 'A', 'MP', 'FP'], declared_t_seconds: 82 });
    });

    it('has buttons of at least 44 px', async () => {
        await mount(make(CONTRACT));
        const html = container.innerHTML;
        expect(html).toContain('min-h-11');
        expect(html).not.toMatch(/\bbtn-xs\b/);
    });
});

describe('targets with an optional fuel endurance (hunt)', () => {
    it('are put in order around the compulsory points and sent with the endurance', async () => {
        await mount(make(HUNT));
        type(input('CP1, minutes after the start point'), '10');
        type(input('CP2, minutes after the start point'), '30');
        const lane = (i: number) => container.querySelector(`[data-testid="lane-${i}"]`)!;
        await click(lane(1).querySelector('button[aria-expanded]'));
        await click(Array.from(lane(1).querySelectorAll('button')).find((b) => b.textContent === 'T2'));
        type(input('Fuel endurance in minutes'), '90');
        api.saveDeclaration.mockResolvedValue(make(HUNT, {}, { state: 'complete', errors: [] }));
        await submit();
        expect(api.saveDeclaration).toHaveBeenCalledWith(5, {
            compulsory_point_times: { CP1: 600, CP2: 1800 },
            time_reference: 'start_point',
            declared_sequence: ['CP1', 'T2', 'CP2'],
            fuel_metadata: { declared_endurance_minutes: 90 },
        });
    });
});

describe('after the cut-off', () => {
    it('the declaration can only be read and the reason is given', async () => {
        await mount(
            make(TIMES, { read_only_reason: 'The declaration can no longer be changed: it had to be done before take-off.', declaration_payload: { time_reference: 'start_point', relative_times: { TP1: 600 } } }, { can_edit: false, state: 'complete', errors: [] }),
        );
        const note = container.querySelector('[data-testid="declaration-read-only"]')!;
        expect(note.textContent).toContain('You can only read this declaration.');
        expect(note.textContent).toContain('can no longer be changed');
        expect(button('Save declaration')).toBeUndefined();
        expect(input('TP1, minutes after the start point').disabled).toBe(true);
        expect(input('TP1, minutes after the start point').value).toBe('10');
        expect(container.querySelector('[data-testid="declaration-cutoff"]')).toBeNull();
    });
});

describe('an optional declaration', () => {
    it('can be skipped, and the page says what skipping means', async () => {
        await mount(make(TIMES, {}, { need: 'optional', errors: [] }));
        expect(container.querySelector('[data-testid="optional-note"]')?.textContent).toContain('If you skip it');
        await click(button('Skip the declaration'));
        expect(api.saveDeclaration).not.toHaveBeenCalled();
        expect(seenPath).toBe('/');
    });
    it('is not offered to skip a required one', async () => {
        await mount(make(TIMES));
        expect(button('Skip the declaration')).toBeUndefined();
    });
});

const BOOKING = '/declaration/5?booking=1&contestId=1&navigationTaskId=2';

describe('the declaration step of a booking ends with the one signal the app knows', () => {
    beforeEach(() => bridge.isEmbeddedInApp.mockReturnValue(true));

    it('"Do this later" leaves the booking standing and signals registered', async () => {
        await mount(make(TIMES), BOOKING);
        expect(bridge.signalApp).not.toHaveBeenCalled();
        await click(button('Do this later'));
        expect(bridge.signalApp).toHaveBeenCalledTimes(1);
        expect(bridge.signalApp).toHaveBeenCalledWith('registered', { contestId: 1, navigationTaskId: 2 });
    });

    it('"Done" after a complete declaration signals registered', async () => {
        await mount(make(TIMES, {}, { state: 'complete', errors: [] }), BOOKING);
        expect(button('Do this later')).toBeUndefined();
        await click(button('Done'));
        expect(bridge.signalApp).toHaveBeenCalledWith('registered', { contestId: 1, navigationTaskId: 2 });
    });

    it('saving does not end the booking, "Done" does', async () => {
        await mount(make(TIMES), BOOKING);
        type(input('TP1, minutes after the start point'), '10');
        api.saveDeclaration.mockResolvedValue(make(TIMES, {}, { state: 'complete', errors: [] }));
        await submit();
        expect(bridge.signalApp).not.toHaveBeenCalled();
        await click(button('Done'));
        expect(bridge.signalApp).toHaveBeenCalledTimes(1);
    });

    it('skipping an optional declaration signals registered', async () => {
        await mount(make(TIMES, {}, { need: 'optional', errors: [] }), BOOKING);
        await click(button('Skip the declaration'));
        expect(bridge.signalApp).toHaveBeenCalledWith('registered', { contestId: 1, navigationTaskId: 2 });
    });

    it('a declaration that is already closed offers "Continue", which signals registered', async () => {
        await mount(make(TIMES, { read_only_reason: 'Closed.' }, { can_edit: false }), BOOKING);
        await click(button('Continue'));
        expect(bridge.signalApp).toHaveBeenCalledWith('registered', { contestId: 1, navigationTaskId: 2 });
    });

    it('a page that cannot load still lets the pilot out with the same signal', async () => {
        await mount(new Error('The declaration could not be loaded.'), BOOKING);
        expect(container.textContent).toContain('could not be loaded');
        await click(button('Continue without declaring now'));
        expect(bridge.signalApp).toHaveBeenCalledWith('registered', { contestId: 1, navigationTaskId: 2 });
    });

    it('on the website the booking ends on the map of the task and no signal is sent', async () => {
        bridge.isEmbeddedInApp.mockReturnValue(false);
        await mount(make(TIMES), BOOKING);
        await click(button('Do this later'));
        expect(bridge.signalApp).not.toHaveBeenCalled();
        expect(seenPath).toBe('/competition-map/1/2');
    });
});

describe('outside a booking', () => {
    it('has no booking buttons and no signal', async () => {
        await mount(make(TIMES));
        expect(button('Do this later')).toBeUndefined();
        expect(button('Done')).toBeUndefined();
        expect(bridge.signalApp).not.toHaveBeenCalled();
    });
});
