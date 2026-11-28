import { describe, expect, it } from 'vitest';
import { curvePointAt, joinCurveRun, joinCurves, nearestCurveParameter, splitCurve } from './curveSplit';

const P0 = { lat: 60, lng: 11 };
const C = { lat: 60.08, lng: 11.1 };
const P2 = { lat: 60.01, lng: 11.3 };

const distance = (a: { lat: number; lng: number }, b: { lat: number; lng: number }) => Math.hypot(a.lat - b.lat, a.lng - b.lng);

describe('splitting a curve', () => {
  it('gives two curves whose points all lie on the original curve', () => {
    for (const t of [0.1, 0.37, 0.5, 0.9]) {
      const { firstControl, middle, secondControl } = splitCurve(P0, C, P2, t);
      expect(distance(middle, curvePointAt(P0, C, P2, t))).toBeLessThan(1e-12);
      for (let step = 0; step <= 20; step += 1) {
        const s = step / 20;
        expect(distance(curvePointAt(P0, firstControl, middle, s), curvePointAt(P0, C, P2, s * t))).toBeLessThan(1e-12);
        expect(distance(curvePointAt(middle, secondControl, P2, s), curvePointAt(P0, C, P2, t + s * (1 - t)))).toBeLessThan(1e-12);
      }
    }
  });

  it('is cut again on the half it lands on, still on the original curve', () => {
    const first = splitCurve(P0, C, P2, 0.5);
    const second = splitCurve(P0, first.firstControl, first.middle, 0.4);
    expect(distance(second.middle, curvePointAt(P0, C, P2, 0.2))).toBeLessThan(1e-12);
  });
});

describe('the point of the curve nearest to a click', () => {
  it('is the parameter of a click on the curve', () => {
    for (const t of [0.05, 0.3, 0.5, 0.77, 0.95]) {
      expect(nearestCurveParameter(P0, C, P2, curvePointAt(P0, C, P2, t))).toBeCloseTo(t, 5);
    }
  });

  it('is the parameter of the nearest point for a click beside the curve', () => {
    const t = 0.4;
    const on = curvePointAt(P0, C, P2, t);
    const ahead = curvePointAt(P0, C, P2, t + 0.001);
    // A step to the side of the tangent, a little (about 100 m) away
    const click = { lat: on.lat - (ahead.lng - on.lng) * 20, lng: on.lng + (ahead.lat - on.lat) * 20 };
    expect(Math.abs(nearestCurveParameter(P0, C, P2, click) - t)).toBeLessThan(0.02);
  });

  it('is at the end for a click beyond it', () => {
    expect(nearestCurveParameter(P0, C, P2, { lat: 59.9, lng: 10.9 })).toBeLessThan(1e-6);
    expect(nearestCurveParameter(P0, C, P2, { lat: 60, lng: 11.6 })).toBeGreaterThan(1 - 1e-6);
  });
});

describe('joining two curves', () => {
  it('gives the original control point back for the two halves of a split', () => {
    for (const t of [0.03, 0.25, 0.5, 0.8, 0.98]) {
      const { firstControl, middle, secondControl } = splitCurve(P0, C, P2, t);
      const joined = joinCurves(P0, firstControl, middle, secondControl, P2);
      expect(joined.exact).toBe(true);
      expect(distance(joined.control, C)).toBeLessThan(1e-9);
    }
  });

  it('gives it back for two pieces of one curve that is cut in several places', () => {
    const first = splitCurve(P0, C, P2, 0.3);
    const rest = splitCurve(first.middle, first.secondControl, P2, 0.5);
    const joined = joinCurves(first.middle, rest.firstControl, rest.middle, rest.secondControl, P2);
    expect(joined.exact).toBe(true);
    expect(distance(joined.control, first.secondControl)).toBeLessThan(1e-9);
  });

  it('follows the reshaped shape when a half was reshaped: through the half-arc point of the composite', () => {
    const { firstControl, middle, secondControl } = splitCurve(P0, C, P2, 0.5);
    const reshaped = { lat: secondControl.lat + 0.03, lng: secondControl.lng + 0.01 };
    const joined = joinCurves(P0, firstControl, middle, reshaped, P2);
    expect(joined.exact).toBe(false);
    const q = halfArcPoint(P0, [{ control: firstControl, end: middle }, { control: reshaped, end: P2 }]);
    expect(distance(curvePointAt(P0, joined.control, P2, 0.5), q)).toBeLessThan(2e-4);
    // The drag is not lost: the control point is not the original one
    expect(distance(joined.control, C)).toBeGreaterThan(0.01);
  });

  it('joins three segments as one run, through the half-arc point, and does not depend on the order', () => {
    const first = splitCurve(P0, C, P2, 0.3);
    const rest = splitCurve(first.middle, first.secondControl, P2, 0.5);
    const reshaped = { lat: rest.firstControl.lat - 0.02, lng: rest.firstControl.lng + 0.02 };
    const segments = [
      { control: first.firstControl, end: first.middle },
      { control: reshaped, end: rest.middle },
      { control: rest.secondControl, end: P2 },
    ];
    const joined = joinCurveRun(P0, segments);
    expect(joined.exact).toBe(false);
    expect(distance(curvePointAt(P0, joined.control, P2, 0.5), halfArcPoint(P0, segments))).toBeLessThan(2e-4);
    expect(distance(joined.control, C)).toBeGreaterThan(0.005);
  });

  it('keeps the exact result for three segments that are the parts of one curve', () => {
    const first = splitCurve(P0, C, P2, 0.3);
    const rest = splitCurve(first.middle, first.secondControl, P2, 0.5);
    const joined = joinCurveRun(P0, [
      { control: first.firstControl, end: first.middle },
      { control: rest.firstControl, end: rest.middle },
      { control: rest.secondControl, end: P2 },
    ]);
    expect(joined.exact).toBe(true);
    expect(distance(joined.control, C)).toBeLessThan(1e-9);
  });

  it('is not exact when the middle point is off the line between the controls', () => {
    const joined = joinCurves(
      { lat: 60, lng: 11 },
      { lat: 60, lng: 11.0625 },
      { lat: 60.03125, lng: 11.125 },
      { lat: 60, lng: 11.1875 },
      { lat: 60, lng: 11.25 },
    );
    expect(joined.exact).toBe(false);
    // The joined curve follows the moved shape: it leaves latitude 60
    expect(Math.abs(joined.control.lat - 60)).toBeGreaterThan(0.01);
  });

  it('does not fail on a middle point that is not between the controls', () => {
    const joined = joinCurves(P0, { lat: 60.02, lng: 11.05 }, { lat: 60.1, lng: 11.0 }, { lat: 60.02, lng: 11.05 }, P2);
    expect(joined.exact).toBe(false);
    expect(Number.isFinite(joined.control.lat) && Number.isFinite(joined.control.lng)).toBe(true);
  });
});

// The point at half the arc length of the composite path, found by a much finer sampling than the code under test.
function halfArcPoint(start: { lat: number; lng: number }, segments: Array<{ control: { lat: number; lng: number }; end: { lat: number; lng: number } }>) {
  const scale = Math.cos(((start.lat + segments[segments.length - 1].end.lat) / 2) * Math.PI / 180);
  const path = [start];
  let from = start;
  for (const segment of segments) {
    for (let step = 1; step <= 4000; step += 1) path.push(curvePointAt(from, segment.control, segment.end, step / 4000));
    from = segment.end;
  }
  const step = (a: typeof start, b: typeof start) => Math.hypot((b.lng - a.lng) * scale, b.lat - a.lat);
  let total = 0;
  for (let i = 1; i < path.length; i += 1) total += step(path[i - 1], path[i]);
  let run = 0;
  for (let i = 1; i < path.length; i += 1) {
    run += step(path[i - 1], path[i]);
    if (run >= total / 2) return path[i];
  }
  return path[path.length - 1];
}
