// @vitest-environment jsdom
import React, { act, createRef } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import GenerateSpeedMapsModal, { GenerateSpeedMapsModalHandle } from './GenerateSpeedMapsModal';

const api = vi.hoisted(() => ({
  generateSpeedMaps: vi.fn(),
  waitForGeneratedPdf: vi.fn(),
}));
vi.mock('../api', () => api);

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

describe('GenerateSpeedMapsModal', () => {
  let container: HTMLDivElement;
  let root: Root;
  const handle = createRef<GenerateSpeedMapsModalHandle>();

  beforeEach(() => {
    // jsdom has no modal dialogs
    HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
      this.setAttribute('open', '');
    };
    HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) {
      this.removeAttribute('open');
    };
    api.generateSpeedMaps.mockReset().mockResolvedValue({ status_check_url: '/status' });
    api.waitForGeneratedPdf.mockReset().mockResolvedValue({ status: 'complete', warning: 'Lower zoom.' });
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    act(() =>
      root.render(
        <GenerateSpeedMapsModal
          ref={handle}
          contestId={7}
          navigationTaskId={9}
          defaultSpeeds={[90, 70, 90]}
          defaultWindSpeed={12}
          defaultWindDirection={250}
        />
      )
    );
    act(() => handle.current!.open());
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  const button = (text: string) =>
    Array.from(container.querySelectorAll('button')).find((element) => element.textContent?.trim().startsWith(text))!;
  const chips = () => Array.from(container.querySelectorAll('[aria-label="Chosen speeds"] .badge')).map((chip) => chip.textContent?.replace('✕', '').trim());
  const inputs = () => Array.from(container.querySelectorAll<HTMLInputElement>('input[type="number"]'));
  const type = (input: HTMLInputElement, value: string) =>
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });

  it('starts from the speeds of the contestants, each once, and the wind of the task', () => {
    expect(chips()).toEqual(['70 kt', '90 kt']);
    const [, , , , windDirection, windSpeed] = inputs();
    expect([windDirection.value, windSpeed.value]).toEqual(['250', '12']);
  });

  it('adds a speed and a range and removes a speed', () => {
    const [single, from, to, step] = inputs();
    type(single, '80');
    act(() => button('Add').click());
    expect(chips()).toEqual(['70 kt', '80 kt', '90 kt']);
    type(from, '100');
    type(to, '120');
    type(step, '10');
    act(() => button('Add range').click());
    expect(chips()).toEqual(['70 kt', '80 kt', '90 kt', '100 kt', '110 kt', '120 kt']);
    act(() => (container.querySelector('[aria-label="Remove 80 knots"]') as HTMLButtonElement).click());
    expect(chips()).toEqual(['70 kt', '90 kt', '100 kt', '110 kt', '120 kt']);
  });

  it('will not make maps in a wind that is as strong as the slowest speed, and says why', () => {
    const windSpeed = inputs()[5];
    type(windSpeed, '70');
    expect((button('Make') as HTMLButtonElement).disabled).toBe(true);
    expect(container.textContent).toContain('lower than the slowest speed (70 knots)');
    type(windSpeed, '10');
    expect((button('Make') as HTMLButtonElement).disabled).toBe(false);
  });

  it('asks for the maps and says when they are ready, with the server warning', async () => {
    await act(async () => {
      button('Make 2 maps').click();
    });
    expect(api.generateSpeedMaps).toHaveBeenCalledWith(7, 9, { speeds: [70, 90], wind_speed: 12, wind_direction: 250 });
    expect(api.waitForGeneratedPdf).toHaveBeenCalledWith('/status', expect.any(Function));
    expect(container.textContent).toContain('The maps are ready');
    expect(container.textContent).toContain('Lower zoom.');
  });

  it('shows why the maps could not be made and goes back to the form', async () => {
    api.waitForGeneratedPdf.mockRejectedValue(new Error('no tiles'));
    await act(async () => {
      button('Make 2 maps').click();
    });
    expect(container.textContent).toContain('no tiles');
    act(() => button('Back').click());
    expect(button('Make 2 maps')).toBeTruthy();
  });
});
