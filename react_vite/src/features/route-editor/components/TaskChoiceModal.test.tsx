// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TaskChoiceModal from './TaskChoiceModal';
import { shouldOfferTaskChoice } from '../guideProgress';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

// The same gate RouteEditor uses: shown for a new route, never for one with an id in the URL.
const Harness = ({ routeId, groups, onChoose, onClosed }: { routeId?: string; groups: string[]; onChoose: (id: string) => void; onClosed: () => void }) => {
  const [open, setOpen] = React.useState(() => shouldOfferTaskChoice(routeId));
  return (
    <div>
      <span data-testid="editor">editor</span>
      {open && <TaskChoiceModal visibleTaskTypeGroups={groups} onChoose={(id) => { setOpen(false); onChoose(id); }} onClose={() => { setOpen(false); onClosed(); }} />}
    </div>
  );
};

describe('task choice', () => {
  let container: HTMLDivElement;
  let root: Root;
  const onChoose = vi.fn();
  const onClosed = vi.fn();

  const render = (props: { routeId?: string; groups?: string[] }) => {
    act(() => {
      root.render(<Harness routeId={props.routeId} groups={props.groups ?? ['legacy']} onChoose={onChoose} onClosed={onClosed} />);
    });
  };
  const dialog = () => container.querySelector('[role="dialog"]');
  const button = (text: string) => [...container.querySelectorAll('button')].find((item) => item.textContent?.includes(text)) as HTMLButtonElement;

  beforeEach(() => {
    onChoose.mockClear();
    onClosed.mockClear();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('is shown for a new route and not for an existing one', () => {
    render({});
    expect(dialog()).not.toBeNull();
    act(() => root.unmount());
    root = createRoot(container);
    render({ routeId: '17' });
    expect(dialog()).toBeNull();
    expect(container.querySelector('[data-testid="editor"]')).not.toBeNull();
  });

  it('offers the task types the user may see, grouped, one line each', () => {
    render({ groups: ['legacy'] });
    const text = dialog()!.textContent!;
    expect(text).toContain('Legacy');
    expect(text).toContain('Precision');
    expect(text).toContain('Start, turn points and finish, with optional hidden gates.');
    expect(text).not.toContain('CIMA');
    expect(text).not.toContain('2.A7 Circle');
  });

  it('shows the CIMA task types to a user with the CIMA group, and only the granted one for a fine-grained grant', () => {
    render({ groups: ['legacy', 'cima'] });
    expect(dialog()!.textContent).toContain('2.A7 Circle');
    expect(dialog()!.textContent).toContain('2.B3 Duration');
    act(() => root.unmount());
    root = createRoot(container);
    render({ groups: ['legacy', 'cima:circle'] });
    expect(dialog()!.textContent).toContain('2.A7 Circle');
    expect(dialog()!.textContent).not.toContain('2.B3 Duration');
  });

  it('hands the chosen task on and goes away', () => {
    render({ groups: ['legacy', 'cima'] });
    act(() => button('2.A7 Circle').click());
    expect(onChoose).toHaveBeenCalledWith('cima_a7');
    expect(onClosed).not.toHaveBeenCalled();
    expect(dialog()).toBeNull();
  });

  it('"Build without a guide" closes it without choosing anything', () => {
    render({});
    act(() => button('Build without a guide').click());
    expect(onClosed).toHaveBeenCalledTimes(1);
    expect(onChoose).not.toHaveBeenCalled();
    expect(dialog()).toBeNull();
    expect(container.querySelector('[data-testid="editor"]')).not.toBeNull();
  });

  it('the close button and Esc do the same', () => {
    render({});
    act(() => (container.querySelector('button[aria-label="Close"]') as HTMLButtonElement).click());
    expect(onClosed).toHaveBeenCalledTimes(1);
    expect(dialog()).toBeNull();

    act(() => root.unmount());
    root = createRoot(container);
    render({});
    act(() => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(onClosed).toHaveBeenCalledTimes(2);
    expect(onChoose).not.toHaveBeenCalled();
    expect(dialog()).toBeNull();
  });
});
