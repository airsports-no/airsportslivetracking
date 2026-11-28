// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Toolbar from './Toolbar';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

describe('toolbar undo and redo', () => {
  let container: HTMLDivElement;
  let root: Root;
  const onUndo = vi.fn();
  const onRedo = vi.fn();
  const onSelect = vi.fn();

  const render = (canUndo: boolean, canRedo: boolean) => act(() => {
    root.render(
      <Toolbar
        mode="view"
        setMode={() => {}}
        setTempGatePoint={() => {}}
        setTempPolygonPoints={() => {}}
        onSelect={onSelect}
        openWizard={() => {}}
        openGateWidths={() => {}}
        canUndo={canUndo}
        canRedo={canRedo}
        onUndo={onUndo}
        onRedo={onRedo}
      />,
    );
  });
  const undoButton = () => container.querySelector('button[aria-label="Undo"]') as HTMLButtonElement;
  const redoButton = () => container.querySelector('button[aria-label="Redo"]') as HTMLButtonElement;

  beforeEach(() => {
    [onUndo, onRedo, onSelect].forEach((fn) => fn.mockClear());
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('disables both buttons when there is nothing to undo or redo', () => {
    render(false, false);
    expect(undoButton().disabled).toBe(true);
    expect(redoButton().disabled).toBe(true);
  });

  it('enables each by what there is, and calls the handlers', () => {
    render(true, false);
    expect(undoButton().disabled).toBe(false);
    expect(redoButton().disabled).toBe(true);
    act(() => undoButton().click());
    expect(onUndo).toHaveBeenCalledTimes(1);
    render(true, true);
    act(() => redoButton().click());
    expect(onRedo).toHaveBeenCalledTimes(1);
  });

  it('names the shortcuts in the tooltips', () => {
    render(true, true);
    expect(undoButton().title).toMatch(/Undo \((Ctrl|Cmd)\+Z\)/);
    expect(redoButton().title).toMatch(/Redo \(.*Shift\+Z/);
  });

  it('has no one-line hint of its own: the banner over the map says what a click does', () => {
    render(false, false);
    expect(container.textContent).not.toContain('Click map');
    expect(container.textContent).not.toContain('Select a point');
  });

  it('goes back to select mode with its select button', () => {
    render(false, false);
    const select = [...container.querySelectorAll('button')].find((item) => item.textContent === 'Select')!;
    act(() => select.click());
    expect(onSelect).toHaveBeenCalledTimes(1);
  });
});

describe('toolbar hidden gate tool', () => {
  it('has a Hidden gate button that starts the tool and shows when it is on', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);
    const setMode = vi.fn();
    const render = (mode: 'view' | 'add_hidden_gate') => act(() => {
      root.render(
        <Toolbar
          mode={mode}
          setMode={setMode}
          setTempGatePoint={() => {}}
          setTempPolygonPoints={() => {}}
          onSelect={() => {}}
          openWizard={() => {}}
          openGateWidths={() => {}}
          canUndo={false}
          canRedo={false}
          onUndo={() => {}}
          onRedo={() => {}}
        />,
      );
    });
    const button = () => Array.from(container.querySelectorAll('button')).find((item) => item.textContent === 'Hidden gate') as HTMLButtonElement;
    render('view');
    expect(button().className).not.toContain('btn-info');
    act(() => button().click());
    expect(setMode).toHaveBeenCalledWith('add_hidden_gate');
    render('add_hidden_gate');
    expect(button().className).toContain('btn-info');
    act(() => root.unmount());
    container.remove();
  });
});

