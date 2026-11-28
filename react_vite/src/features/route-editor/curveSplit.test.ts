import { describe, expect, it } from 'vitest';
import { curvePointAt, joinCurves, nearestCurveParameter, splitCurve } from './curveSplit';

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

  it('is one curve through the middle point, by chord lengths, when a half was reshaped', () => {
    const { firstControl, middle, secondControl } = splitCurve(P0, C, P2, 0.5);
    const reshaped = { lat: secondControl.lat + 0.03, lng: secondControl.lng + 0.01 };
    const joined = joinCurves(P0, firstControl, middle, reshaped, P2);
    expect(joined.exact).toBe(false);
    // It passes through the middle point at the parameter the chord lengths give
    const toMiddle = Math.hypot((middle.lng - P0.lng) * Math.cos(((P0.lat + P2.lat) / 2) * Math.PI / 180), middle.lat - P0.lat);
    const fromMiddle = Math.hypot((P2.lng - middle.lng) * Math.cos(((P0.lat + P2.lat) / 2) * Math.PI / 180), P2.lat - middle.lat);
    const t = toMiddle / (toMiddle + fromMiddle);
    expect(distance(curvePointAt(P0, joined.control, P2, t), middle)).toBeLessThan(1e-12);
  });

  it('does not fail on a middle point that is not between the controls', () => {
    const joined = joinCurves(P0, { lat: 60.02, lng: 11.05 }, { lat: 60.1, lng: 11.0 }, { lat: 60.02, lng: 11.05 }, P2);
    expect(joined.exact).toBe(false);
    expect(Number.isFinite(joined.control.lat) && Number.isFinite(joined.control.lng)).toBe(true);
  });
});
