import { describe, expect, it, vi } from 'vitest';
import { addSpeeds, speedMapsProblem, speedsInRange } from './preparedMaps';
import { waitForGeneratedPdf } from './api';

describe('speedsInRange', () => {
  it('counts from the first speed in steps, including the last when the step reaches it', () => {
    expect(speedsInRange(70, 100, 10)).toEqual([70, 80, 90, 100]);
    expect(speedsInRange(70, 95, 10)).toEqual([70, 80, 90]);
    expect(speedsInRange(80, 80, 5)).toEqual([80]);
  });

  it('does not drift with fractional steps', () => {
    expect(speedsInRange(60, 61, 0.1)).toHaveLength(11);
    expect(speedsInRange(60, 61, 0.1).slice(-1)).toEqual([61]);
  });

  it('gives none for a range that makes no sense', () => {
    expect(speedsInRange(100, 70, 5)).toEqual([]);
    expect(speedsInRange(70, 100, 0)).toEqual([]);
    expect(speedsInRange(NaN, 100, 5)).toEqual([]);
  });
});

describe('addSpeeds', () => {
  it('keeps each speed once, slowest first', () => {
    expect(addSpeeds([90, 70], [80, 70, 100])).toEqual([70, 80, 90, 100]);
  });
});

describe('speedMapsProblem', () => {
  it('accepts speeds in a lighter wind', () => {
    expect(speedMapsProblem([70, 90], 15, 250)).toBeNull();
    expect(speedMapsProblem([70], 0, 0)).toBeNull();
  });

  it('says what is wrong, as the server does', () => {
    expect(speedMapsProblem([], 10, 0)).toMatch(/at least one speed/i);
    expect(speedMapsProblem(Array.from({ length: 21 }, (_, n) => 60 + n), 0, 0)).toMatch(/At most 20/);
    expect(speedMapsProblem([10, 90], 0, 0)).toMatch(/between 20 and 400/);
    expect(speedMapsProblem([70], -1, 0)).toMatch(/wind speed/);
    expect(speedMapsProblem([70], 5, 361)).toMatch(/direction/);
    expect(speedMapsProblem([60, 90], 60, 0)).toMatch(/lower than the slowest speed \(60 knots\)/);
  });
});

describe('waitForGeneratedPdf', () => {
  const answer = (body: object, ok = true) => ({ ok, json: async () => body }) as Response;

  it('asks again while pending and gives the complete status', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(answer({ status: 'pending' }))
      .mockResolvedValueOnce(answer({ status: 'complete', url: '/x.pdf', warning: 'w' }));
    vi.stubGlobal('fetch', fetchMock);
    const sleep = vi.fn().mockResolvedValue(undefined);
    await expect(waitForGeneratedPdf('/status', () => false, sleep)).resolves.toMatchObject({ url: '/x.pdf', warning: 'w' });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenCalledTimes(1);
  });

  it('ends with the reason when the server says it failed', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(answer({ status: 'error', message: 'no tiles' })));
    await expect(waitForGeneratedPdf('/status', () => false, async () => {})).rejects.toThrow('no tiles');
  });

  it('tries again after a failed request', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(answer({}, false))
      .mockResolvedValueOnce(answer({ status: 'complete', url: '/x.pdf' }));
    vi.stubGlobal('fetch', fetchMock);
    const sleep = vi.fn().mockResolvedValue(undefined);
    await expect(waitForGeneratedPdf('/status', () => false, sleep)).resolves.toMatchObject({ url: '/x.pdf' });
    expect(sleep).toHaveBeenCalledWith(5000);
  });

  it('stops when it is cancelled', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(answer({ status: 'pending' })));
    let cancelled = false;
    const sleep = vi.fn(async () => {
      cancelled = true;
    });
    await expect(waitForGeneratedPdf('/status', () => cancelled, sleep)).resolves.toBeNull();
  });
});
