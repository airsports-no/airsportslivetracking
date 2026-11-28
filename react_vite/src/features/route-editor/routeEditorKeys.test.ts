// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { editorKeyAction, isTypingTarget } from './routeEditorKeys';

const on = (tag: string) => document.createElement(tag);

describe('editor keys', () => {
  it('Esc stops, undo and redo follow Ctrl and Cmd', () => {
    expect(editorKeyAction({ key: 'Escape' }, false)).toBe('stop');
    expect(editorKeyAction({ key: 'z', ctrlKey: true }, false)).toBe('undo');
    expect(editorKeyAction({ key: 'z', metaKey: true }, false)).toBe('undo');
    expect(editorKeyAction({ key: 'Z', ctrlKey: true, shiftKey: true }, false)).toBe('redo');
    expect(editorKeyAction({ key: 'z', metaKey: true, shiftKey: true }, false)).toBe('redo');
    expect(editorKeyAction({ key: 'y', ctrlKey: true }, false)).toBe('redo');
  });

  it('leaves other keys and combinations alone', () => {
    expect(editorKeyAction({ key: 'z' }, false)).toBeNull();
    expect(editorKeyAction({ key: 'y' }, false)).toBeNull();
    expect(editorKeyAction({ key: 'a', ctrlKey: true }, false)).toBeNull();
    expect(editorKeyAction({ key: 'Enter' }, false)).toBeNull();
    expect(editorKeyAction({ key: 'Escape', ctrlKey: true }, false)).toBeNull();
    expect(editorKeyAction({ key: 'y', ctrlKey: true, shiftKey: true }, false)).toBeNull();
  });

  it('ignores every key while typing in a field', () => {
    for (const tag of ['input', 'textarea', 'select']) {
      const target = on(tag);
      expect(isTypingTarget(target)).toBe(true);
      expect(editorKeyAction({ key: 'Escape', target }, false)).toBeNull();
      expect(editorKeyAction({ key: 'z', ctrlKey: true, target }, false)).toBeNull();
      expect(editorKeyAction({ key: 'y', ctrlKey: true, target }, false)).toBeNull();
    }
    const editable = on('div');
    editable.contentEditable = 'true';
    Object.defineProperty(editable, 'isContentEditable', { value: true });
    expect(editorKeyAction({ key: 'Escape', target: editable }, false)).toBeNull();
  });

  it('works from a button or the map', () => {
    expect(editorKeyAction({ key: 'Escape', target: on('button') }, false)).toBe('stop');
    expect(editorKeyAction({ key: 'z', ctrlKey: true, target: on('div') }, false)).toBe('undo');
  });

  it('ignores every key while a modal is open or the key went into a dialog', () => {
    expect(editorKeyAction({ key: 'Escape' }, true)).toBeNull();
    expect(editorKeyAction({ key: 'z', ctrlKey: true }, true)).toBeNull();
    const dialog = on('div');
    dialog.setAttribute('role', 'dialog');
    const inside = on('button');
    dialog.appendChild(inside);
    expect(editorKeyAction({ key: 'Escape', target: inside }, false)).toBeNull();
  });
});
