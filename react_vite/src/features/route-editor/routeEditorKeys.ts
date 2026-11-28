// Which keys the route editor reacts to. Pure apart from reading the element the key went to.

export type EditorKeyAction = 'stop' | 'undo' | 'redo';

export interface EditorKeyEvent {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
  target?: EventTarget | null;
}

const TYPING_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

// A field the user types in: the browser's own text undo and Esc apply there, not the editor's.
export const isTypingTarget = (target: EventTarget | null | undefined): boolean => {
  const element = target as HTMLElement | null | undefined;
  if (!element || typeof element.tagName !== 'string') return false;
  return TYPING_TAGS.has(element.tagName) || element.isContentEditable === true;
};

// Inside a dialog (the modals handle their own keys).
export const isInsideDialog = (target: EventTarget | null | undefined): boolean => {
  const element = target as HTMLElement | null | undefined;
  return !!element && typeof element.closest === 'function' && element.closest('dialog, [role="dialog"], [aria-modal="true"]') !== null;
};

// What the key press means for the editor, or null to leave it alone.
export const editorKeyAction = (event: EditorKeyEvent, modalOpen: boolean): EditorKeyAction | null => {
  if (modalOpen || isTypingTarget(event.target) || isInsideDialog(event.target)) return null;
  const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
  if (key === 'Escape') {
    return event.ctrlKey || event.metaKey || event.altKey || event.shiftKey ? null : 'stop';
  }
  const command = !!event.ctrlKey || !!event.metaKey;
  if (!command || event.altKey) return null;
  if (key === 'z') return event.shiftKey ? 'redo' : 'undo';
  if (key === 'y' && !event.shiftKey) return 'redo';
  return null;
};

// The shortcuts as the tooltips name them.
export const undoShortcutLabels = (platform: string = typeof navigator === 'undefined' ? '' : navigator.platform): { undo: string; redo: string } => (
  /mac|iphone|ipad/i.test(platform)
    ? { undo: 'Cmd+Z', redo: 'Cmd+Shift+Z' }
    : { undo: 'Ctrl+Z', redo: 'Ctrl+Shift+Z or Ctrl+Y' }
);
