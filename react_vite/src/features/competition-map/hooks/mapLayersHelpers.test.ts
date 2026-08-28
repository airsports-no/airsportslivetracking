import { hslColor, lastMinutesPositions, splitSegments } from './mapLayersHelpers';
import type { TrackPosition } from '../types';

describe('hslColor', () => {
  it('returns hue 0 for the first of a set', () => {
    expect(hslColor(0, 4)).toBe('hsl(0, 70%, 50%)');
  });

  it('spreads hues proportionally across the total count', () => {
    expect(hslColor(2, 4)).toBe('hsl(180, 70%, 50%)');
  });

  it('does not divide by zero when total is 0', () => {
    expect(hslColor(0, 0)).toBe('hsl(0, 70%, 50%)');
  });
});

describe('lastMinutesPositions', () => {
  const now = new Date('2026-01-01T12:00:00Z');

  function makePosition(minutesAgo: number): TrackPosition {
    return { time: new Date(now.getTime() - minutesAgo * 60_000).toISOString(), latitude: 60, longitude: 11 };
  }

  it('keeps positions within the window and drops older ones', () => {
    const positions = [makePosition(10), makePosition(4), makePosition(1)];
    const result = lastMinutesPositions(positions, 5, now);
    expect(result).toHaveLength(2);
    expect(result.every((p) => new Date(p.time) >= new Date(now.getTime() - 5 * 60_000))).toBe(true);
  });

  it('includes a position exactly at the cutoff', () => {
    const positions = [makePosition(5)];
    expect(lastMinutesPositions(positions, 5, now)).toHaveLength(1);
  });

  it('returns an empty array when nothing is within the window', () => {
    expect(lastMinutesPositions([makePosition(30)], 5, now)).toEqual([]);
  });
});

describe('splitSegments', () => {
  function makePosition(lat: number, lng: number, interpolated = false): TrackPosition {
    return { time: '2026-01-01T00:00:00Z', latitude: lat, longitude: lng, interpolated };
  }

  it('returns empty solid/dashed for fewer than 2 positions', () => {
    expect(splitSegments([])).toEqual({ solid: [], dashed: [] });
    expect(splitSegments([makePosition(60, 11)])).toEqual({ solid: [], dashed: [] });
  });

  it('produces a single solid polyline for an all-real track', () => {
    const positions = [makePosition(60, 11), makePosition(60.1, 11.1), makePosition(60.2, 11.2)];
    const result = splitSegments(positions);
    expect(result.dashed).toEqual([]);
    expect(result.solid).toEqual([
      [
        [60, 11],
        [60.1, 11.1],
        [60.2, 11.2],
      ],
    ]);
  });

  it('keeps a short run of interpolated points (under 10) solid', () => {
    const positions = [
      makePosition(60, 11),
      makePosition(60.01, 11.01, true),
      makePosition(60.02, 11.02, true),
      makePosition(60.03, 11.03),
    ];
    const result = splitSegments(positions);
    expect(result.dashed).toEqual([]);
    expect(result.solid).toHaveLength(1);
  });

  it('dashes a long run (>= 10) of interpolated points, including the connecting segments to real neighbors', () => {
    const positions = [
      makePosition(60, 11), // real, index 0
      ...Array.from({ length: 10 }, (_, i) => makePosition(60.01 * (i + 1), 11.01 * (i + 1), true)), // 10 interpolated, indices 1-10
      makePosition(60.2, 11.2), // real, index 11
    ];
    const result = splitSegments(positions);
    expect(result.solid).toEqual([]);
    expect(result.dashed).toHaveLength(1);
    // The dashed run includes the leading real point and the trailing real point.
    expect(result.dashed[0][0]).toEqual([60, 11]);
    expect(result.dashed[0][result.dashed[0].length - 1]).toEqual([60.2, 11.2]);
  });

  it('merges two long interpolated runs separated by a single real point into one continuous dashed run', () => {
    // The "mark the adjacent connecting segment too" rule dashes the segment
    // on both sides of realB, so there is no solid gap between the two
    // interpolated runs to break the dashed polyline at realB.
    const realA = makePosition(60, 11);
    const realB = makePosition(61, 11);
    const realC = makePosition(62, 11);
    const interpolatedRun = (base: number) => Array.from({ length: 10 }, (_, i) => makePosition(base + i * 0.01, 11, true));
    const positions = [realA, ...interpolatedRun(60), realB, ...interpolatedRun(61), realC];
    const result = splitSegments(positions);
    expect(result.solid).toEqual([]);
    expect(result.dashed).toHaveLength(1);
    expect(result.dashed[0][0]).toEqual([60, 11]);
    expect(result.dashed[0][result.dashed[0].length - 1]).toEqual([62, 11]);
  });

  it('keeps two long interpolated runs as separate dashed segments when a real gap separates them by more than one point', () => {
    const realA = makePosition(60, 11);
    const realGap1 = makePosition(60.5, 11);
    const realGap2 = makePosition(60.6, 11);
    const realC = makePosition(62, 11);
    const interpolatedRun = (base: number) => Array.from({ length: 10 }, (_, i) => makePosition(base + i * 0.01, 11, true));
    const positions = [realA, ...interpolatedRun(60), realGap1, realGap2, ...interpolatedRun(61), realC];
    const result = splitSegments(positions);
    expect(result.dashed).toHaveLength(2);
    expect(result.solid).toHaveLength(1);
    expect(result.solid[0]).toEqual([
      [60.5, 11],
      [60.6, 11],
    ]);
  });

  it('treats a leading interpolated run the same as an internal one (no out-of-bounds access)', () => {
    const positions = [
      ...Array.from({ length: 10 }, (_, i) => makePosition(60 + i * 0.01, 11, true)),
      makePosition(60.2, 11),
    ];
    const result = splitSegments(positions);
    expect(result.solid).toEqual([]);
    expect(result.dashed).toHaveLength(1);
  });

  it('treats a trailing interpolated run the same as an internal one (no out-of-bounds access)', () => {
    const positions = [
      makePosition(60, 11),
      ...Array.from({ length: 10 }, (_, i) => makePosition(60 + i * 0.01, 11, true)),
    ];
    const result = splitSegments(positions);
    expect(result.solid).toEqual([]);
    expect(result.dashed).toHaveLength(1);
  });

  it('merges several short interpolated runs bridged by lone real points into one dashed run, even though none individually reaches the threshold', () => {
    // Mirrors a tracking source (e.g. Traccar) partially backfilling an outage
    // with a handful of recovered real fixes: each triggers its own short
    // interpolated run against the previous point, none of which alone is >= 10,
    // but together they represent one sustained gap that should render dashed.
    const real = (n: number) => makePosition(60 + n, 11);
    const shortRun = (base: number) => Array.from({ length: 6 }, (_, i) => makePosition(base + i * 0.01, 11, true));
    const positions = [
      real(0),
      ...shortRun(60),
      real(1),
      ...shortRun(61),
      real(2),
      ...shortRun(62),
      real(3),
    ];
    const result = splitSegments(positions);
    expect(result.solid).toEqual([]);
    expect(result.dashed).toHaveLength(1);
    expect(result.dashed[0][0]).toEqual([60, 11]);
    expect(result.dashed[0][result.dashed[0].length - 1]).toEqual([63, 11]);
  });

  it('does not bridge runs separated by 2+ consecutive real points, even if individually short', () => {
    const real = (n: number) => makePosition(60 + n, 11);
    const shortRun = (base: number) => Array.from({ length: 6 }, (_, i) => makePosition(base + i * 0.01, 11, true));
    const positions = [real(0), ...shortRun(60), real(1), real(1.5), ...shortRun(61), real(2)];
    const result = splitSegments(positions);
    expect(result.dashed).toEqual([]);
    expect(result.solid).toHaveLength(1);
  });
});
