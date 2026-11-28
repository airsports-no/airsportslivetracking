import { describe, expect, it } from 'vitest';
import {
  adoptSnapshot,
  canRedo,
  canUndo,
  createHistory,
  isLatestStep,
  MAX_HISTORY_STEPS,
  recordSnapshot,
  redo,
  selectionAfterRestore,
  undo,
  undoStep,
  type RouteSnapshot,
} from './routeHistory';

const record = (history: ReturnType<typeof createHistory<number>>, value: number, options = {}) => recordSnapshot(history, value, options);

describe('route history', () => {
  it('undoes and redoes steps in order', () => {
    let history = createHistory(0);
    expect(canUndo(history)).toBe(false);
    history = record(record(history, 1), 2);
    expect(history.present.snapshot).toBe(2);
    history = undo(history);
    expect(history.present.snapshot).toBe(1);
    expect(canRedo(history)).toBe(true);
    history = undo(history);
    expect(history.present.snapshot).toBe(0);
    expect(undo(history)).toBe(history);
    history = redo(redo(history));
    expect(history.present.snapshot).toBe(2);
    expect(redo(history)).toBe(history);
  });

  it('clears the redo steps by a new change', () => {
    let history = record(record(createHistory(0), 1), 2);
    history = undo(history);
    history = record(history, 5);
    expect(canRedo(history)).toBe(false);
    expect(undo(history).present.snapshot).toBe(1);
  });

  it('does not record an identical snapshot', () => {
    const history = recordSnapshot(createHistory({ a: 1 }), { a: 1 });
    expect(history.past).toHaveLength(0);
    const next = recordSnapshot(history, { a: 2 });
    expect(recordSnapshot(next, { a: 2 })).toBe(next);
  });

  it('keeps at most 100 steps', () => {
    let history = createHistory(0);
    for (let value = 1; value <= 150; value += 1) history = record(history, value);
    expect(history.past).toHaveLength(MAX_HISTORY_STEPS);
    for (let step = 0; step < 200; step += 1) history = undo(history);
    expect(history.present.snapshot).toBe(150 - MAX_HISTORY_STEPS);
  });

  it('joins changes with the same key into one step', () => {
    let history = createHistory(0);
    history = record(history, 1, { key: 'drag' });
    history = record(history, 2, { key: 'drag' });
    history = record(history, 3, { key: 'drag' });
    expect(history.past).toHaveLength(1);
    expect(undo(history).present.snapshot).toBe(0);
    history = record(history, 4, { key: 'other' });
    expect(history.past).toHaveLength(2);
  });

  it('joins keyed edits only inside the time window', () => {
    let history = createHistory(0);
    history = record(history, 1, { key: 'name', now: 1000, windowMs: 1000 });
    history = record(history, 2, { key: 'name', now: 1800, windowMs: 1000 });
    expect(history.past).toHaveLength(1);
    history = record(history, 3, { key: 'name', now: 3000, windowMs: 1000 });
    expect(history.past).toHaveLength(2);
  });

  it('leaves no step when a joined edit returns to where it began', () => {
    let history = record(createHistory(0), 1, { key: 'name', now: 0, windowMs: 1000 });
    history = record(history, 0, { key: 'name', now: 10, windowMs: 1000 });
    expect(history.past).toHaveLength(0);
    expect(history.present.snapshot).toBe(0);
  });

  it('does not join an edit onto a restored step', () => {
    let history = record(createHistory(0), 1, { key: 'name', now: 0, windowMs: 1000 });
    history = record(history, 2, { key: 'other', now: 1 });
    history = undo(history);
    history = record(history, 3, { key: 'name', now: 5, windowMs: 1000 });
    expect(history.past).toHaveLength(2);
  });

  it('does not join an edit onto a restored step when there is no window', () => {
    let history = record(createHistory(0), 1, { key: 'a' });
    history = record(history, 2, { key: 'b' });
    history = undo(history);
    history = record(history, 3, { key: 'a' });
    expect(history.past.map((entry) => entry.snapshot)).toEqual([0, 1]);
    expect(undo(history).present.snapshot).toBe(1);
  });

  it('undoes one step by its key, with the later steps staying redoable', () => {
    let history = createHistory(0);
    history = record(history, 1, { key: 'a' });
    history = record(history, 2, { key: 'b' });
    history = record(history, 3, { key: 'c' });
    expect(isLatestStep(history, 'c')).toBe(true);
    expect(isLatestStep(history, 'b')).toBe(false);
    const undone = undoStep(history, 'b')!;
    expect(undone.present.snapshot).toBe(1);
    expect(undone.future.map((entry) => entry.snapshot)).toEqual([2, 3]);
    expect(redo(redo(undone)).present.snapshot).toBe(3);
    expect(undoStep(history, 'c')!.present.snapshot).toBe(2);
    expect(undoStep(history, 'a')!.present.snapshot).toBe(0);
  });

  it('cannot undo a step that is gone', () => {
    let history = record(record(createHistory(0), 1, { key: 'a' }), 2, { key: 'b' });
    expect(undoStep(history, 'missing')).toBeNull();
    history = undo(history);
    expect(undoStep(history, 'b')).toBeNull();
    history = record(history, 9, { key: 'c' });
    expect(undoStep(history, 'b')).toBeNull();
    expect(undoStep(createHistory(0), 'a')).toBeNull();
  });

  it('adopts a changed snapshot without a step and keeps the redo steps', () => {
    let history = record(record(createHistory(0), 1), 2);
    history = undo(history);
    const adopted = adoptSnapshot(history, 11);
    expect(adopted.present.snapshot).toBe(11);
    expect(adopted.past).toEqual(history.past);
    expect(adopted.future).toEqual(history.future);
  });
});

const content = (overrides: Partial<RouteSnapshot> = {}): RouteSnapshot => ({
  routePoints: [], standalonePoints: [], gates: [], observationMarkers: [], polygons: [], ...overrides,
});

describe('selection after a restore', () => {
  const point = { id: 'p1' } as RouteSnapshot['routePoints'][number];

  it('keeps a selection that still exists', () => {
    expect(selectionAfterRestore('p1', 'point', content({ routePoints: [point] }))).toEqual({ selectedId: 'p1', selectionType: 'point' });
  });

  it('clears a selection whose item is gone, whatever its kind', () => {
    expect(selectionAfterRestore('p1', 'point', content())).toEqual({ selectedId: null, selectionType: null });
    expect(selectionAfterRestore('g1', 'gate', content({ routePoints: [point] }))).toEqual({ selectedId: null, selectionType: null });
    expect(selectionAfterRestore('o1', 'observation', content())).toEqual({ selectedId: null, selectionType: null });
    expect(selectionAfterRestore('z1', 'polygon', content())).toEqual({ selectedId: null, selectionType: null });
    expect(selectionAfterRestore('s1', 'standalone_point', content())).toEqual({ selectedId: null, selectionType: null });
  });

  it('leaves no selection and non-item selections alone', () => {
    expect(selectionAfterRestore(null, null, content())).toEqual({ selectedId: null, selectionType: null });
    expect(selectionAfterRestore('x', 'wizard', content())).toEqual({ selectedId: 'x', selectionType: 'wizard' });
  });
});
