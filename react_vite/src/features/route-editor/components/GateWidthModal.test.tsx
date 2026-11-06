// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { RoutePoint } from '../../../types';
import GateWidthModal from './GateWidthModal';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const point = (id: string, type: RoutePoint['type'], width = 926): RoutePoint => ({
  id,
  name: id.toUpperCase(),
  type,
  lat: 60,
  lng: 11,
  segmentType: 'straight',
  width,
  isTiming: false,
  isPassing: true,
  featureType: 'route_waypoint',
});

const points = [point('sp', 'sp'), point('tp1', 'tp'), point('s1', 'secret', 1000), point('tp2', 'tp'), point('fp', 'fp')];

describe('GateWidthModal', () => {
  let container: HTMLDivElement;
  let root: Root;
  const onApply = vi.fn();

  beforeEach(() => {
    // jsdom has no modal dialogs
    HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
      this.setAttribute('open', '');
    };
    HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) {
      this.removeAttribute('open');
    };
    onApply.mockReset();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => root.render(<GateWidthModal isOpen points={points} onApply={onApply} onClose={() => {}} />));
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  const button = (text: string) =>
    Array.from(container.querySelectorAll('button')).find((element) => element.textContent?.trim().startsWith(text))!;
  const checkboxes = () => Array.from(container.querySelectorAll<HTMLInputElement>('tbody input[type="checkbox"]'));
  const click = (element: HTMLElement) => act(() => element.click());
  const typeWidth = (value: string) => {
    const input = container.querySelector<HTMLInputElement>('input[type="number"]')!;
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
  };

  it('lists every gate with its width in nautical miles', () => {
    const rows = Array.from(container.querySelectorAll('tbody tr')).map((row) =>
      Array.from(row.querySelectorAll('td')).map((cell) => cell.textContent),
    );
    expect(rows).toEqual([
      ['', 'SP', 'Start point', '0.50'],
      ['', 'TP1', 'Turning point', '0.50'],
      ['', 'S1', 'Secret gate', '0.54'],
      ['', 'TP2', 'Turning point', '0.50'],
      ['', 'FP', 'Finish point', '0.50'],
    ]);
  });

  it('cannot apply before gates are chosen and a width is written', () => {
    expect(button('Apply').disabled).toBe(true);
    click(button('All'));
    expect(button('Apply').disabled).toBe(true);
    typeWidth('0.75');
    expect(button('Apply').disabled).toBe(false);
    typeWidth('0');
    expect(button('Apply').disabled).toBe(true);
  });

  it('applies the width to the chosen gates only, in metres', () => {
    click(checkboxes()[1]);
    click(checkboxes()[3]);
    typeWidth('1');
    click(button('Apply to 2 gates'));
    expect(onApply).toHaveBeenCalledTimes(1);
    const [ids, widthMetres] = onApply.mock.calls[0];
    expect(Array.from(ids as Set<string>).sort()).toEqual(['tp1', 'tp2']);
    expect(widthMetres).toBe(1852);
    expect(container.textContent).toContain('2 gates set to 1.00 NM.');
  });

  it('chooses all the gates of a type with one button, and all or none', () => {
    click(button('Turning points only'));
    expect(checkboxes().map((checkbox) => checkbox.checked)).toEqual([false, true, false, true, false]);
    click(button('All'));
    expect(checkboxes().every((checkbox) => checkbox.checked)).toBe(true);
    click(button('None'));
    expect(checkboxes().some((checkbox) => checkbox.checked)).toBe(false);
  });
});
