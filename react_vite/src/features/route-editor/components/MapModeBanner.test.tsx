// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MapModeBanner from './MapModeBanner';
import { getModeBanner, MODE_TEXTS, type PlacingMode } from '../modeBanner';
import type { Mode } from '../../../types';
import type { RouteRequirementTool } from '../api';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

// What RouteEditor renders: the banner for the state, or nothing in select mode.
const Harness = ({ mode, tool = null, onStop, onDone, doneLabel = 'Done, next step' }: {
  mode: Mode; tool?: RouteRequirementTool | null; onStop: () => void; onDone: () => void; doneLabel?: string;
}) => {
  const banner = getModeBanner({ mode, tempGatePoint: null, activeGuideTool: tool });
  return banner
    ? <MapModeBanner banner={banner} onStop={onStop} guideAction={tool ? { label: doneLabel, onDone } : null} />
    : <span>select</span>;
};

describe('map mode banner', () => {
  let container: HTMLDivElement;
  let root: Root;
  const onStop = vi.fn();
  const onDone = vi.fn();
  const render = (props: Partial<React.ComponentProps<typeof Harness>> & { mode: Mode }) => act(() => {
    root.render(<Harness onStop={onStop} onDone={onDone} {...props} />);
  });
  const banner = () => container.querySelector('[data-testid="map-mode-banner"]');
  const button = (label: string) => [...container.querySelectorAll('button')].find((item) => item.textContent === label || item.getAttribute('aria-label') === label) as HTMLButtonElement | undefined;

  beforeEach(() => {
    onStop.mockClear();
    onDone.mockClear();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('is shown in every placing mode, with what a click does and how to stop', () => {
    for (const mode of Object.keys(MODE_TEXTS) as PlacingMode[]) {
      render({ mode });
      expect(banner(), mode).not.toBeNull();
      expect(banner()!.textContent, mode).toContain('Esc to stop');
      expect(button('Stop'), mode).toBeDefined();
    }
    render({ mode: 'add_point' });
    expect(banner()!.textContent).toContain('Adding waypoints: click the map to place the next one.');
  });

  it('is absent in select mode', () => {
    render({ mode: 'view' });
    expect(banner()).toBeNull();
  });

  it('stops with its button', () => {
    render({ mode: 'add_polygon' });
    act(() => button('Stop')!.click());
    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it('carries the guide button of an active step, with the tool prompt', () => {
    render({ mode: 'add_point', tool: 'route_waypoint' });
    expect(banner()!.textContent).toContain('Click the map to place the next route waypoint.');
    act(() => button('Done, next step')!.click());
    expect(onDone).toHaveBeenCalledTimes(1);
    act(() => button('Stop')!.click());
    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it('shows a guide step that is active in select mode (a click on a leg places)', () => {
    render({ mode: 'view', tool: 'hidden_gate' });
    expect(banner()!.textContent).toContain('Click a leg of the route to place a hidden gate.');
  });

  it('has one stop button when the guide button is the stop button', () => {
    render({ mode: 'add_point', tool: 'circle_start', doneLabel: 'Stop' });
    expect(container.querySelectorAll('button')).toHaveLength(1);
    act(() => button('Stop')!.click());
    expect(onDone).toHaveBeenCalledTimes(1);
  });
});
