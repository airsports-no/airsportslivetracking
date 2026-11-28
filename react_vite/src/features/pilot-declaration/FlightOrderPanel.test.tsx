// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import FlightOrderPanel from './FlightOrderPanel';
import { useFlightOrderStatus } from './useFlightOrderStatus';
import FlightDeclarationSummary from './FlightDeclarationSummary';
import { DeclarationStatus, FlightOrderStatus } from './types';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({ fetchDeclaration: vi.fn(), saveDeclaration: vi.fn() }));
const bridge = vi.hoisted(() => ({ isEmbeddedInApp: vi.fn(() => false), signalApp: vi.fn() }));
vi.mock('./api', () => api);
vi.mock('../../utils/appBridge', () => bridge);

const status = (state: FlightOrderStatus['state'], extra: Partial<FlightOrderStatus> = {}): FlightOrderStatus => ({
    state, path: null, created_at: null, reason: null, ...extra,
});

describe('the flight order panel', () => {
    const html = (value: FlightOrderStatus | null) => renderToStaticMarkup(<FlightOrderPanel status={value} retryBySaving />);

    it('waits for the declaration', () => {
        expect(html(status('waiting_for_declaration'))).toContain('Your flight order is made when your declaration is complete.');
    });
    it('says it is being made', () => {
        expect(html(status('being_made'))).toContain('Your flight order is being made');
    });
    it('gives a download button when ready', () => {
        const out = html(status('ready', { path: '/display/maplink/abc/', created_at: '2026-08-01T07:00:00Z' }));
        expect(out).toContain('Download flight order');
        expect(out).toContain('href="/display/maplink/abc/"');
        expect(out).toContain('target="_blank"');
        expect(out).toContain('min-h-11');
    });
    it('opens the flight order where the pilot is inside the app (a web view has no second window)', () => {
        bridge.isEmbeddedInApp.mockReturnValue(true);
        const out = html(status('ready', { path: '/display/maplink/abc/' }));
        bridge.isEmbeddedInApp.mockReturnValue(false);
        expect(out).toContain('href="/display/maplink/abc/"');
        expect(out).not.toContain('target=');
    });
    it('gives the reason and the way to try again when failed', () => {
        const out = html(status('failed', { reason: 'The flight order could not be made.' }));
        expect(out).toContain('The flight order could not be made.');
        expect(out).toContain('Save your declaration again to try again.');
    });
    it('says nothing where the system does not make flight orders', () => {
        expect(html(status('not_available'))).toBe('');
        expect(html(null)).toBe('');
    });
});

describe('asking again while the flight order is made', () => {
    let container: HTMLDivElement;
    let root: Root;
    let seen: FlightOrderStatus | null = null;
    const refresh = vi.fn();

    const Probe = () => {
        seen = useFlightOrderStatus(status('being_made'), refresh, 1000);
        return <p>{seen?.state}</p>;
    };
    const setHidden = (hidden: boolean) => {
        Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden });
    };
    const tick = async (ms: number) => {
        await act(async () => {
            await vi.advanceTimersByTimeAsync(ms);
        });
    };

    beforeEach(() => {
        vi.useFakeTimers();
        setHidden(false);
        refresh.mockReset();
        container = document.createElement('div');
        document.body.appendChild(container);
        root = createRoot(container);
    });
    afterEach(() => {
        act(() => root.unmount());
        container.remove();
        vi.useRealTimers();
        setHidden(false);
    });

    it('asks at a modest interval and stops when it is ready', async () => {
        refresh.mockResolvedValueOnce(status('being_made')).mockResolvedValue(status('ready', { path: '/display/maplink/x/' }));
        act(() => root.render(<Probe />));
        expect(refresh).not.toHaveBeenCalled();
        await tick(1000);
        expect(refresh).toHaveBeenCalledTimes(1);
        await tick(1000);
        expect(refresh).toHaveBeenCalledTimes(2);
        expect(seen?.state).toBe('ready');
        await tick(10000);
        expect(refresh).toHaveBeenCalledTimes(2);
    });

    it('stops when it has failed', async () => {
        refresh.mockResolvedValue(status('failed', { reason: 'x' }));
        act(() => root.render(<Probe />));
        await tick(1000);
        await tick(10000);
        expect(refresh).toHaveBeenCalledTimes(1);
        expect(seen?.state).toBe('failed');
    });

    it('keeps trying after an error', async () => {
        refresh.mockRejectedValueOnce(new Error('offline')).mockResolvedValue(status('ready', { path: '/p/' }));
        act(() => root.render(<Probe />));
        await tick(1000);
        await tick(1000);
        expect(refresh).toHaveBeenCalledTimes(2);
        expect(seen?.state).toBe('ready');
    });

    it('does not ask while the page is hidden, and asks at once when it is shown again', async () => {
        refresh.mockResolvedValue(status('being_made'));
        act(() => root.render(<Probe />));
        setHidden(true);
        await tick(5000);
        expect(refresh).not.toHaveBeenCalled();
        setHidden(false);
        await act(async () => {
            document.dispatchEvent(new Event('visibilitychange'));
        });
        expect(refresh).toHaveBeenCalledTimes(1);
        await tick(1000);
        expect(refresh).toHaveBeenCalledTimes(2);
    });

    it('stops asking when the page goes away', async () => {
        refresh.mockResolvedValue(status('being_made'));
        act(() => root.render(<Probe />));
        act(() => root.unmount());
        await tick(5000);
        expect(refresh).not.toHaveBeenCalled();
        root = createRoot(container);
    });
});

describe('my flights', () => {
    const declaration = (overrides: Partial<DeclarationStatus> = {}): DeclarationStatus => ({
        need: 'required', state: 'missing', errors: [], can_edit: true, edit_until: '2026-08-01T07:55:00+00:00', edit_url: '/declaration/12', ...overrides,
    });
    const html = (declarationStatus: DeclarationStatus | null, order: FlightOrderStatus | null) =>
        renderToStaticMarkup(
            <MemoryRouter>
                <FlightDeclarationSummary flightId={12} declarationStatus={declarationStatus} flightOrderStatus={order} />
            </MemoryRouter>,
        );

    it('shows a declaration that is needed with the way to make it', () => {
        const out = html(declaration(), status('waiting_for_declaration'));
        expect(out).toContain('Declaration needed');
        expect(out).toContain('Make declaration');
        expect(out).toContain('href="/declaration/12"');
        expect(out).toContain('Your flight order is made when your declaration is complete.');
    });
    it('shows saved but not finished with "Edit declaration"', () => {
        const out = html(declaration({ state: 'incomplete' }), status('waiting_for_declaration'));
        expect(out).toContain('Declaration saved, not finished');
        expect(out).toContain('Edit declaration');
    });
    it('shows complete with the flight order download', () => {
        const out = html(declaration({ state: 'complete' }), status('ready', { path: '/display/maplink/abc/' }));
        expect(out).toContain('Declaration complete');
        expect(out).toContain('Download flight order');
    });
    it('shows closed with "View declaration"', () => {
        const out = html(declaration({ state: 'complete', can_edit: false }), status('ready', { path: '/display/maplink/abc/' }));
        expect(out).toContain('Declaration closed');
        expect(out).toContain('View declaration');
        expect(out).not.toContain('Edit declaration');
    });
    it('read-only (a past flight): "View declaration" even if the status would allow editing, and no flight order block without a download', () => {
        const readOnly = (d: DeclarationStatus, order: FlightOrderStatus | null) =>
            renderToStaticMarkup(
                <MemoryRouter>
                    <FlightDeclarationSummary flightId={12} declarationStatus={d} flightOrderStatus={order} readOnly />
                </MemoryRouter>,
            );
        const out = readOnly(declaration({ state: 'complete', can_edit: true }), status('waiting_for_declaration'));
        expect(out).toContain('View declaration');
        expect(out).toContain('href="/declaration/12"');
        expect(out).not.toContain('Edit declaration');
        expect(out).not.toContain('Your flight order is made when');
        expect(readOnly(declaration({ state: 'complete', can_edit: false }), status('being_made'))).not.toContain('flight order');
    });
    it('read-only shows the flight order when there is a download', () => {
        const out = renderToStaticMarkup(
            <MemoryRouter>
                <FlightDeclarationSummary
                    flightId={12}
                    declarationStatus={declaration({ state: 'complete', can_edit: false })}
                    flightOrderStatus={status('ready', { path: '/display/maplink/abc/' })}
                    readOnly
                />
            </MemoryRouter>,
        );
        expect(out).toContain('View declaration');
        expect(out).toContain('Download flight order');
    });
    it('shows nothing about a declaration for a task without one, but the flight order', () => {
        const out = html(declaration({ need: 'not_needed', state: 'complete', can_edit: false, edit_url: null }), status('being_made'));
        expect(out).not.toContain('Declaration');
        expect(out).toContain('Your flight order is being made');
    });
});
