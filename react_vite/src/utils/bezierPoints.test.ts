// @vitest-environment jsdom
import { getQuadraticBezierPoints } from './bezierPoints';

describe('getQuadraticBezierPoints', () => {
  it('starts at p1 and ends at p2', () => {
    const p1 = { lat: 60, lng: 11 };
    const p2 = { lat: 61, lng: 12 };
    const control = { lat: 60.5, lng: 11.2 };
    const points = getQuadraticBezierPoints(p1, p2, control);
    expect(points[0].lat).toBeCloseTo(p1.lat);
    expect(points[0].lng).toBeCloseTo(p1.lng);
    expect(points[points.length - 1].lat).toBeCloseTo(p2.lat);
    expect(points[points.length - 1].lng).toBeCloseTo(p2.lng);
  });

  it('returns numPoints + 1 points', () => {
    const p1 = { lat: 60, lng: 11 };
    const p2 = { lat: 61, lng: 12 };
    const control = { lat: 60.5, lng: 11.2 };
    expect(getQuadraticBezierPoints(p1, p2, control, 5)).toHaveLength(6);
    expect(getQuadraticBezierPoints(p1, p2, control)).toHaveLength(21);
  });

  it('the midpoint (t=0.5) is the average of the endpoint and control-point averages', () => {
    const p1 = { lat: 60, lng: 11 };
    const p2 = { lat: 62, lng: 13 };
    const control = { lat: 60, lng: 13 };
    const points = getQuadraticBezierPoints(p1, p2, control, 2);
    // At t=0.5: 0.25*p1 + 0.5*control + 0.25*p2
    expect(points[1].lat).toBeCloseTo(0.25 * p1.lat + 0.5 * control.lat + 0.25 * p2.lat);
    expect(points[1].lng).toBeCloseTo(0.25 * p1.lng + 0.5 * control.lng + 0.25 * p2.lng);
  });

  it('degenerates to a straight line when the control point is the segment midpoint', () => {
    const p1 = { lat: 60, lng: 11 };
    const p2 = { lat: 62, lng: 13 };
    const control = { lat: 61, lng: 12 };
    const points = getQuadraticBezierPoints(p1, p2, control, 4);
    points.forEach((point) => {
      // On the straight line lat - lng should stay constant (both increase 1:1).
      expect(point.lat - point.lng).toBeCloseTo(60 - 11);
    });
  });
});
