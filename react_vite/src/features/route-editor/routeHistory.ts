import type { Gate, ObservationMarker, Polygon, RoutePoint, SelectionType } from '../../types';

// Undo and redo for the route content. Pure: the hook in useRouteHistory.ts keeps one of these and feeds it snapshots.
// The content is what is saved with the route (points, standalone points, gates, photos, polygons). The selection, the
// mode, the map view and the settings are not part of it.

export interface RouteSnapshot {
  routePoints: RoutePoint[];
  standalonePoints: RoutePoint[];
  gates: Gate[];
  observationMarkers: ObservationMarker[];
  polygons: Polygon[];
}

// Steps that can be undone, the oldest ones are dropped beyond this.
export const MAX_HISTORY_STEPS = 100;

export interface HistoryEntry<T> {
  snapshot: T;
  // Changes recorded with the same key are one step (a drag, typing in one field, an undoable step of the caller).
  key?: string;
  // When the entry was last changed; -Infinity for an entry that was restored, so nothing joins onto it.
  time: number;
}

export interface History<T> {
  past: HistoryEntry<T>[];
  present: HistoryEntry<T>;
  future: HistoryEntry<T>[];
}

export const createHistory = <T>(initial: T): History<T> => ({
  past: [],
  present: { snapshot: initial, time: -Infinity },
  future: [],
});

export const canUndo = <T>(history: History<T>): boolean => history.past.length > 0;
export const canRedo = <T>(history: History<T>): boolean => history.future.length > 0;

export const sameSnapshot = <T>(a: T, b: T): boolean => a === b || JSON.stringify(a) === JSON.stringify(b);

export interface RecordOptions {
  // A change with the key of the latest step is part of that step, not a new one.
  key?: string;
  // With windowMs: only while the latest step was changed at most this long ago (typing in a field).
  now?: number;
  windowMs?: number;
}

// Records the content as it is now. Nothing changes when it equals the latest snapshot; a new step clears the redo
// steps. A change that joins the latest step and undoes it entirely leaves no step.
export const recordSnapshot = <T>(history: History<T>, snapshot: T, options: RecordOptions = {}): History<T> => {
  if (sameSnapshot(history.present.snapshot, snapshot)) return history;
  const { key, now = Date.now(), windowMs } = options;
  const joins = key !== undefined
    && history.present.key === key
    && history.past.length > 0
    && (windowMs === undefined || now - history.present.time <= windowMs);
  if (joins) {
    const before = history.past[history.past.length - 1];
    if (sameSnapshot(before.snapshot, snapshot)) {
      return { past: history.past.slice(0, -1), present: { ...before, time: -Infinity }, future: [] };
    }
    return { past: history.past, present: { snapshot, key, time: now }, future: [] };
  }
  const past = [...history.past, history.present].slice(-MAX_HISTORY_STEPS);
  return { past, present: { snapshot, key, time: now }, future: [] };
};

// The restored entry keeps its key (the handle of a step finds it by it) but nothing joins onto it any more.
const restored = <T>(entry: HistoryEntry<T>): HistoryEntry<T> => ({ ...entry, time: -Infinity });

export const undo = <T>(history: History<T>): History<T> => {
  if (!canUndo(history)) return history;
  const previous = history.past[history.past.length - 1];
  return { past: history.past.slice(0, -1), present: restored(previous), future: [history.present, ...history.future] };
};

export const redo = <T>(history: History<T>): History<T> => {
  if (!canRedo(history)) return history;
  const [next, ...rest] = history.future;
  return { past: [...history.past, history.present], present: restored(next), future: rest };
};

// Undoes the step recorded with [key], and every step made after it (they stay redoable). null when that step is no
// longer there: it was undone already, dropped by the limit, or replaced by a new change after an undo.
export const undoStep = <T>(history: History<T>, key: string): History<T> | null => {
  if (history.present.key === key) return history.past.length > 0 ? undo(history) : null;
  const index = history.past.findIndex((entry) => entry.key === key);
  if (index <= 0) return null;
  const undone = [...history.past.slice(index), history.present];
  return {
    past: history.past.slice(0, index - 1),
    present: restored(history.past[index - 1]),
    future: [...undone, ...history.future],
  };
};

// Whether the step recorded with [key] is the latest one (undoing it takes nothing else with it).
export const isLatestStep = <T>(history: History<T>, key: string): boolean => history.present.key === key && canUndo(history);

// The content changed by something that is not a step of its own (a route loaded, an automatic renaming after an undo):
// the latest snapshot becomes it without a step and without clearing the redo steps.
export const adoptSnapshot = <T>(history: History<T>, snapshot: T): History<T> => (
  sameSnapshot(history.present.snapshot, snapshot) ? history : { ...history, present: { ...history.present, snapshot } }
);

// What the selection should be after the content was replaced: the same, or none when the selected item is gone.
export const selectionAfterRestore = (
  selectedId: string | null,
  selectionType: SelectionType | null,
  content: RouteSnapshot,
): { selectedId: string | null; selectionType: SelectionType | null } => {
  if (!selectedId) return { selectedId, selectionType };
  const lists: Partial<Record<SelectionType, Array<{ id: string }>>> = {
    point: content.routePoints,
    standalone_point: content.standalonePoints,
    gate: content.gates,
    observation: content.observationMarkers,
    polygon: content.polygons,
  };
  const list = selectionType ? lists[selectionType] : undefined;
  // A selection that is not an item of the content (settings, help, the guide) stays.
  if (!list) return { selectedId, selectionType };
  return list.some((item) => item.id === selectedId) ? { selectedId, selectionType } : { selectedId: null, selectionType: null };
};
