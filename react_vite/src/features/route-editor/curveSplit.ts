import type { LatLng } from '../../types';

// The maths of a hidden gate on a curved leg. A curved leg is a quadratic Bezier curve from P0 to P2 with the control
// point C, drawn (and built by the backend) by interpolating latitude and longitude linearly, as in
// getQuadraticBezierPoints. Everything here works in that same space (degrees of latitude and longitude, no projection),
// so the curves drawn after a split or a join are the same curves as before, not an approximation of them. A de
// Casteljau split and its inverse only use linear interpolation, so they hold in any affine space.

export interface CurveSplit {
  // The control point of the first half (P0 to M) and of the second half (M to P2).
  firstControl: LatLng;
  // The point of the curve at the parameter.
  middle: LatLng;
  secondControl: LatLng;
}

const lerp = (a: LatLng, b: LatLng, t: number): LatLng => ({
  lat: a.lat + (b.lat - a.lat) * t,
  lng: a.lng + (b.lng - a.lng) * t,
});

export const curvePointAt = (start: LatLng, control: LatLng, end: LatLng, t: number): LatLng => (
  lerp(lerp(start, control, t), lerp(control, end, t), t)
);

// Splits the curve at [t] into two quadratic curves that together are exactly the same curve.
export const splitCurve = (start: LatLng, control: LatLng, end: LatLng, t: number): CurveSplit => {
  const firstControl = lerp(start, control, t);
  const secondControl = lerp(control, end, t);
  return { firstControl, middle: lerp(firstControl, secondControl, t), secondControl };
};

// A click this close to an end of the leg (as a fraction of the curve's parameter) is refused.
export const MIN_CURVE_END_FRACTION = 0.02;

export const TOO_CLOSE_TO_LEG_END_NOTICE = 'Too close to the end of the leg';

// Longitude is stretched by the cosine of the latitude so that distances measured in degrees are about right.
const planar = (point: LatLng, lngScale: number): [number, number] => [point.lng * lngScale, point.lat];

// The parameter of the point of the curve nearest to [click], found by sampling and then narrowing the range around the
// nearest sample until it is a few centimetres at most (a golden-section search on the distance).
export const nearestCurveParameter = (start: LatLng, control: LatLng, end: LatLng, click: LatLng): number => {
  const lngScale = Math.cos(((start.lat + end.lat) / 2) * Math.PI / 180);
  const [clickX, clickY] = planar(click, lngScale);
  const distanceAt = (t: number): number => {
    const [x, y] = planar(curvePointAt(start, control, end, t), lngScale);
    return Math.hypot(x - clickX, y - clickY);
  };

  const samples = 200;
  let bestIndex = 0;
  let bestDistance = Infinity;
  for (let index = 0; index <= samples; index += 1) {
    const distance = distanceAt(index / samples);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  }

  let low = Math.max(0, (bestIndex - 1) / samples);
  let high = Math.min(1, (bestIndex + 1) / samples);
  const ratio = (Math.sqrt(5) - 1) / 2;
  let a = high - ratio * (high - low);
  let b = low + ratio * (high - low);
  let distanceA = distanceAt(a);
  let distanceB = distanceAt(b);
  for (let step = 0; step < 40; step += 1) {
    if (distanceA < distanceB) {
      high = b;
      b = a;
      distanceB = distanceA;
      a = high - ratio * (high - low);
      distanceA = distanceAt(a);
    } else {
      low = a;
      a = b;
      distanceA = distanceB;
      b = low + ratio * (high - low);
      distanceB = distanceAt(b);
    }
  }
  const refined = (low + high) / 2;
  // The ends of the range are the samples themselves: keep them when they are nearer than the middle of the range
  const candidates = [refined, bestIndex / samples];
  return candidates.reduce((best, t) => (distanceAt(t) < distanceAt(best) ? t : best));
};

export interface CurveJoin {
  control: LatLng;
  // True when the two curves were the two halves of one quadratic curve, so the joined curve is that curve exactly.
  exact: boolean;
}

// How far the two ways of working out the original control point may differ, as a fraction of the chord, for the two
// curves to count as halves of one curve (1e-4 of a 10 km leg is a metre).
const EXACT_TOLERANCE = 1e-4;

const length = (a: LatLng, b: LatLng): number => Math.hypot(a.lat - b.lat, a.lng - b.lng);

// Joins the curve start-first-middle and the curve middle-second-end into one curve from start to end.
//
// Two curves that are the halves of one curve (the split at t gives C1 = P0 + t (C - P0), C2 = C + t (P2 - C) and
// M = C1 + t (C2 - C1)) are recognised by working out t from the position of M on the line from C1 to C2, and then C in
// the two ways the split gives it, from the first half, C = P0 + (C1 - P0) / t, and from the second,
// C = (C2 - t P2) / (1 - t). When these agree the joined curve is that curve: the control point is C.
//
// When they do not (one half was reshaped afterwards) the joined curve is one curve that passes through M, at the
// parameter t estimated from the lengths of the two chords, t = |P0 M| / (|P0 M| + |M P2|), with the control point
// C = (M - (1 - t)^2 P0 - t^2 P2) / (2 t (1 - t)). It approximates both halves; it is not either of them.
export const joinCurves = (
  start: LatLng,
  firstControl: LatLng,
  middle: LatLng,
  secondControl: LatLng,
  end: LatLng,
): CurveJoin => {
  const chord = length(start, end);
  const dLat = secondControl.lat - firstControl.lat;
  const dLng = secondControl.lng - firstControl.lng;
  const span = dLat * dLat + dLng * dLng;
  if (span > 0) {
    const t = ((middle.lat - firstControl.lat) * dLat + (middle.lng - firstControl.lng) * dLng) / span;
    if (t > 0 && t < 1) {
      const fromFirst: LatLng = {
        lat: start.lat + (firstControl.lat - start.lat) / t,
        lng: start.lng + (firstControl.lng - start.lng) / t,
      };
      const fromSecond: LatLng = {
        lat: (secondControl.lat - t * end.lat) / (1 - t),
        lng: (secondControl.lng - t * end.lng) / (1 - t),
      };
      if (length(fromFirst, fromSecond) <= EXACT_TOLERANCE * chord) {
        return { control: lerp(fromFirst, fromSecond, 0.5), exact: true };
      }
    }
  }

  const lngScale = Math.cos(((start.lat + end.lat) / 2) * Math.PI / 180);
  const toMiddle = Math.hypot((middle.lng - start.lng) * lngScale, middle.lat - start.lat);
  const fromMiddle = Math.hypot((end.lng - middle.lng) * lngScale, end.lat - middle.lat);
  const total = toMiddle + fromMiddle;
  const t = total > 0 ? Math.min(0.99, Math.max(0.01, toMiddle / total)) : 0.5;
  const weight = 2 * t * (1 - t);
  return {
    control: {
      lat: (middle.lat - (1 - t) * (1 - t) * start.lat - t * t * end.lat) / weight,
      lng: (middle.lng - (1 - t) * (1 - t) * start.lng - t * t * end.lng) / weight,
    },
    exact: false,
  };
};
