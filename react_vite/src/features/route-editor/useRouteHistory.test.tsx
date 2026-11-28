// @vitest-environment jsdom
import React, { act, useCallback, useEffect, useMemo, useState } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import useRouteHistory, { type RouteHistoryApi } from './useRouteHistory';
import type { RouteSnapshot } from './routeHistory';
import type { Gate, RoutePoint } from '../../types';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const point = (id: string, name = id): RoutePoint => ({
  id, name, lat: 60, lng: 11, type: 'tp', width: 1852, isTiming: true, isPassing: true, segmentType: 'straight',
} as RoutePoint);

interface Harness {
  api: RouteHistoryApi;
  routePoints: RoutePoint[];
  gates: Gate[];
  setRoutePoints: React.Dispatch<React.SetStateAction<RoutePoint[]>>;
  setGates: React.Dispatch<React.SetStateAction<Gate[]>>;
  load: (points: RoutePoint[]) => void;
}

let harness: Harness;

const Probe = () => {
  const [routePoints, setRoutePoints] = useState<RoutePoint[]>([]);
  const [gates, setGates] = useState<Gate[]>([]);
  const content = useMemo<RouteSnapshot>(() => ({
    routePoints, standalonePoints: [], gates, observationMarkers: [], polygons: [],
  }), [routePoints, gates]);
  const restore = useCallback((snapshot: RouteSnapshot) => {
    setRoutePoints(snapshot.routePoints);
    setGates(snapshot.gates);
  }, []);
  const api = useRouteHistory(content, restore);
  const load = (points: RoutePoint[]) => {
    setRoutePoints(points);
    api.reset();
  };
  useEffect(() => {
    harness = { api, routePoints, gates, setRoutePoints, setGates, load };
  });
  return null;
};

describe('useRouteHistory', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => root.render(<Probe />));
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('records a change as a step and undoes and redoes it', () => {
    expect(harness.api.canUndo).toBe(false);
    act(() => harness.setRoutePoints([point('a')]));
    expect(harness.api.canUndo).toBe(true);
    act(() => { harness.api.undo(); });
    expect(harness.routePoints).toEqual([]);
    expect(harness.api.canRedo).toBe(true);
    act(() => { harness.api.redo(); });
    expect(harness.routePoints.map((p) => p.id)).toEqual(['a']);
    expect(harness.api.canRedo).toBe(false);
  });

  it('makes changes made together one step', () => {
    act(() => {
      harness.setRoutePoints([point('a')]);
      harness.setGates([{ id: 'g' } as Gate]);
    });
    act(() => { harness.api.undo(); });
    expect(harness.routePoints).toEqual([]);
    expect(harness.gates).toEqual([]);
    expect(harness.api.canUndo).toBe(false);
  });

  it('does not take a loaded route as a step', () => {
    act(() => harness.load([point('a'), point('b')]));
    expect(harness.api.canUndo).toBe(false);
    act(() => harness.setRoutePoints((points) => [...points, point('c')]));
    act(() => { harness.api.undo(); });
    expect(harness.routePoints.map((p) => p.id)).toEqual(['a', 'b']);
  });

  it('forgets the history when another route is loaded', () => {
    act(() => harness.setRoutePoints([point('a')]));
    act(() => harness.load([point('z')]));
    expect(harness.api.canUndo).toBe(false);
    expect(harness.api.canRedo).toBe(false);
  });

  it('joins the edits of one field into one step and not those of another', () => {
    act(() => harness.setRoutePoints([point('a', 'A')]));
    const rename = (name: string, field = 'name') => act(() => {
      harness.api.noteEdit(`a:${field}`);
      harness.setRoutePoints((points) => points.map((p) => ({ ...p, name })));
    });
    rename('Ab');
    rename('Abc');
    rename('Abcd');
    act(() => { harness.api.undo(); });
    expect(harness.routePoints[0].name).toBe('A');
    act(() => { harness.api.redo(); });
    rename('Other', 'other');
    act(() => { harness.api.undo(); });
    expect(harness.routePoints[0].name).toBe('Abcd');
  });

  it('makes a gesture one step even when its changes are rendered apart', () => {
    act(() => harness.setRoutePoints([point('a'), point('b')]));
    act(() => harness.api.beginGesture());
    act(() => harness.setRoutePoints((points) => [...points, point('inserted')]));
    act(() => {
      harness.setRoutePoints((points) => points.map((p) => (p.id === 'inserted' ? { ...p, lat: 61 } : p)));
      harness.api.endGesture();
    });
    act(() => { harness.api.undo(); });
    expect(harness.routePoints.map((p) => p.id)).toEqual(['a', 'b']);
  });

  it('gives a handle that undoes exactly the step it ran', () => {
    act(() => harness.setRoutePoints([point('a'), point('b')]));
    let step!: ReturnType<RouteHistoryApi['runUndoableStep']>;
    act(() => {
      step = harness.api.runUndoableStep(() => {
        harness.setRoutePoints((points) => points.filter((p) => p.id !== 'b'));
        harness.setGates([{ id: 'g' } as Gate]);
      });
    });
    expect(harness.routePoints.map((p) => p.id)).toEqual(['a']);
    expect(step.isLatest()).toBe(true);
    act(() => { step.undo(); });
    expect(harness.routePoints.map((p) => p.id)).toEqual(['a', 'b']);
    expect(harness.gates).toEqual([]);
    expect(step.undo()).toBe(false);
  });

  it('lets the handle undo its step after later steps, which stay redoable', () => {
    let step!: ReturnType<RouteHistoryApi['runUndoableStep']>;
    act(() => harness.setRoutePoints([point('a'), point('b')]));
    act(() => {
      step = harness.api.runUndoableStep(() => harness.setRoutePoints((points) => points.slice(0, 1)));
    });
    act(() => harness.setGates([{ id: 'g' } as Gate]));
    expect(step.isLatest()).toBe(false);
    act(() => { step.undo(); });
    expect(harness.routePoints.map((p) => p.id)).toEqual(['a', 'b']);
    expect(harness.api.canRedo).toBe(true);
  });
});
