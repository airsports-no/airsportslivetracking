import { useCallback, useEffect, useRef, useState } from 'react';
import {
  adoptSnapshot,
  canRedo as historyCanRedo,
  canUndo as historyCanUndo,
  createHistory,
  isLatestStep,
  recordSnapshot,
  redo as redoHistory,
  type History,
  undo as undoHistory,
  undoStep,
  type RouteSnapshot,
} from './routeHistory';

// Edits to the same field of the same item that follow each other within this long are one step: typing a name is one
// step, not one per key. (A debounce on the edit, not recorded on blur: the sidebar's fields do not tell when they end.)
export const EDIT_STEP_WINDOW_MS = 1500;
// A key noted for the next change is only for the change that comes right after it.
const EDIT_NOTE_MS = 300;
// An ending gesture or step that no change followed is dropped after this long.
const GESTURE_GRACE_MS = 250;

export interface UndoableStep {
  // Undoes this step, and any step made after it (they stay redoable). false when the step is no longer there.
  undo: () => boolean;
  // Whether this is still the latest step.
  isLatest: () => boolean;
}

export interface RouteHistoryApi {
  canUndo: boolean;
  canRedo: boolean;
  undo: () => boolean;
  redo: () => boolean;
  // The route was loaded: its content is the new start, with nothing to undo.
  reset: () => void;
  // The next change to the content is an edit of [key] (an item's field): edits in a row to it are one step.
  noteEdit: (key: string) => void;
  // Everything that changes the content between the two calls is one step (a drag that first inserts a point).
  beginGesture: () => void;
  endGesture: () => void;
  // Runs [change] as one undoable step and gives a handle to undo exactly that step.
  runUndoableStep: (change: () => void) => UndoableStep;
}

/**
 * The route content's undo history. It records every change of [content] as a step, except the changes it makes itself
 * by restoring a snapshot ([restore] puts a snapshot back into the editor's state) and a loaded route. A change made
 * all at once (a drag ends with one set of state updates, a click places one point) is one step by being one render.
 */
export default function useRouteHistory(content: RouteSnapshot, restore: (snapshot: RouteSnapshot) => void): RouteHistoryApi {
  const [history, setHistoryState] = useState<History<RouteSnapshot>>(() => createHistory(content));
  const historyRef = useRef(history);
  const pendingRef = useRef<'baseline' | 'adopt' | null>(null);
  const gestureRef = useRef<{ key: string; closing: boolean } | null>(null);
  const editRef = useRef<{ key: string; time: number } | null>(null);
  const counterRef = useRef(0);
  const restoreRef = useRef(restore);
  useEffect(() => {
    restoreRef.current = restore;
  });

  const setHistory = useCallback((next: History<RouteSnapshot>) => {
    historyRef.current = next;
    setHistoryState(next);
  }, []);

  useEffect(() => {
    const current = historyRef.current;
    const pending = pendingRef.current;
    pendingRef.current = null;
    if (pending === 'baseline') {
      setHistory(createHistory(content));
      return;
    }
    if (pending === 'adopt') {
      const adopted = adoptSnapshot(current, content);
      if (adopted !== current) setHistory(adopted);
      return;
    }
    const now = Date.now();
    const gesture = gestureRef.current;
    const edit = editRef.current;
    editRef.current = null;
    let options: Parameters<typeof recordSnapshot>[2];
    if (gesture) {
      options = { key: gesture.key };
      if (gesture.closing) gestureRef.current = null;
    } else if (edit && now - edit.time <= EDIT_NOTE_MS) {
      options = { key: edit.key, now, windowMs: EDIT_STEP_WINDOW_MS };
    }
    const next = recordSnapshot(current, content, options);
    if (next !== current) setHistory(next);
  }, [content, setHistory]);

  const restoreTo = useCallback((next: History<RouteSnapshot>) => {
    gestureRef.current = null;
    pendingRef.current = 'adopt';
    setHistory(next);
    restoreRef.current(next.present.snapshot);
  }, [setHistory]);

  const undo = useCallback(() => {
    const next = undoHistory(historyRef.current);
    if (next === historyRef.current) return false;
    restoreTo(next);
    return true;
  }, [restoreTo]);

  const redo = useCallback(() => {
    const next = redoHistory(historyRef.current);
    if (next === historyRef.current) return false;
    restoreTo(next);
    return true;
  }, [restoreTo]);

  const reset = useCallback(() => {
    gestureRef.current = null;
    editRef.current = null;
    pendingRef.current = 'baseline';
  }, []);

  const noteEdit = useCallback((key: string) => {
    editRef.current = { key, time: Date.now() };
  }, []);

  const beginGesture = useCallback(() => {
    counterRef.current += 1;
    gestureRef.current = { key: `gesture-${counterRef.current}`, closing: false };
  }, []);

  // The changes of the gesture's last event are still to be rendered: it closes when the effect has recorded them, or
  // after a moment if there were none.
  const endGesture = useCallback(() => {
    const gesture = gestureRef.current;
    if (!gesture) return;
    gesture.closing = true;
    setTimeout(() => {
      if (gestureRef.current === gesture) gestureRef.current = null;
    }, GESTURE_GRACE_MS);
  }, []);

  const runUndoableStep = useCallback((change: () => void): UndoableStep => {
    counterRef.current += 1;
    const key = `step-${counterRef.current}`;
    const gesture = { key, closing: false };
    gestureRef.current = gesture;
    change();
    endGesture();
    return {
      undo: () => {
        const next = undoStep(historyRef.current, key);
        if (!next) return false;
        restoreTo(next);
        return true;
      },
      isLatest: () => isLatestStep(historyRef.current, key),
    };
  }, [endGesture, restoreTo]);

  return {
    canUndo: historyCanUndo(history),
    canRedo: historyCanRedo(history),
    undo,
    redo,
    reset,
    noteEdit,
    beginGesture,
    endGesture,
    runUndoableStep,
  };
}
