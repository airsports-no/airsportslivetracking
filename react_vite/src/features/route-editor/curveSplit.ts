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
  // True when the curves were the parts of one quadratic curve, so the joined curve is that curve exactly.
  exact: boolean;
}

// One curved segment of a run: the control point of the curve that ends at [end].
export interface CurveSegment {
  control: LatLng;
  end: LatLng;
}

// How far the two ways of working out the original control point may differ, as a fraction of the chord, for the two
// curves to count as halves of one curve (1e-4 of a 10 km leg is a metre).
const EXACT_TOLERANCE = 1e-4;

const length = (a: LatLng, b: LatLng): number => Math.hypot(a.lat - b.lat, a.lng - b.lng);

// The control point of the one curve that the two curves start-first-middle and middle-second-end are the halves of, or
// null when they are not (one was reshaped afterwards).
//
// Two curves that are the halves of one curve (the split at t gives C1 = P0 + t (C - P0), C2 = C + t (P2 - C) and
// M = C1 + t (C2 - C1)) are recognised by working out t from the position of M on the line from C1 to C2, and then C in
// the two ways the split gives it, from the first half, C = P0 + (C1 - P0) / t, and from the second,
// C = (C2 - t P2) / (1 - t). When these agree the joined curve is that curve: the control point is C.
const exactHalvesControl = (
  start: LatLng,
  firstControl: LatLng,
  middle: LatLng,
  secondControl: LatLng,
  end: LatLng,
): LatLng | null => {
  const chord = length(start, end);
  const dLat = secondControl.lat - firstControl.lat;
  const dLng = secondControl.lng - firstControl.lng;
  const span = dLat * dLat + dLng * dLng;
  if (span <= 0) return null;
  const t = ((middle.lat - firstControl.lat) * dLat + (middle.lng - firstControl.lng) * dLng) / span;
  if (!(t > 0 && t < 1)) return null;
  const fromFirst: LatLng = {
    lat: start.lat + (firstControl.lat - start.lat) / t,
    lng: start.lng + (firstControl.lng - start.lng) / t,
  };
  const fromSecond: LatLng = {
    lat: (secondControl.lat - t * end.lat) / (1 - t),
    lng: (secondControl.lng - t * end.lng) / (1 - t),
  };
  return length(fromFirst, fromSecond) <= EXACT_TOLERANCE * chord ? lerp(fromFirst, fromSecond, 0.5) : null;
};

const PATH_SAMPLES_PER_SEGMENT = 64;

// The point at half the arc length of the path made by the curved segments of the run, measured as the curves are drawn
// (linear in latitude and longitude, with longitude scaled by the cosine of the latitude for the length).
const arcMidpoint = (start: LatLng, segments: CurveSegment[]): LatLng => {
  const lngScale = Math.cos(((start.lat + segments[segments.length - 1].end.lat) / 2) * Math.PI / 180);
  const path: LatLng[] = [start];
  let from = start;
  for (const segment of segments) {
    for (let step = 1; step <= PATH_SAMPLES_PER_SEGMENT; step += 1) {
      path.push(curvePointAt(from, segment.control, segment.end, step / PATH_SAMPLES_PER_SEGMENT));
    }
    from = segment.end;
  }
  const lengths: number[] = [0];
  for (let index = 1; index < path.length; index += 1) {
    lengths.push(lengths[index - 1] + Math.hypot(
      (path[index].lng - path[index - 1].lng) * lngScale,
      path[index].lat - path[index - 1].lat,
    ));
  }
  const half = lengths[lengths.length - 1] / 2;
  let index = 1;
  while (index < path.length - 1 && lengths[index] < half) index += 1;
  const stretch = lengths[index] - lengths[index - 1];
  return lerp(path[index - 1], path[index], stretch > 0 ? (half - lengths[index - 1]) / stretch : 0);
};

// Joins the run of curved segments from [start] (each ends at the start of the next) into one curve from start to the
// end of the last segment.
//
// When the segments are the parts of one curve (a curve split by hidden gates) the joined curve is that curve exactly,
// and the control point is the original one. Otherwise (a part was reshaped) the joined curve follows the shape the
// segments have now: it passes at t = 0.5 through the point Q at half the arc length of their composite path, which
// gives the control point C = 2 Q - (P0 + P2) / 2. The whole run is joined at once, so the result does not depend on
// the order of the segments.
export const joinCurveRun = (start: LatLng, segments: CurveSegment[]): CurveJoin => {
  if (segments.length === 1) return { control: segments[0].control, exact: true };

  // Parts of one curve fold from the left, each fold being the halves of the curve so far and the next part
  let folded = segments[0].control;
  let foldedEnd = segments[0].end;
  let allExact = true;
  for (const next of segments.slice(1)) {
    const control = exactHalvesControl(start, folded, foldedEnd, next.control, next.end);
    if (!control) {
      allExact = false;
      break;
    }
    folded = control;
    foldedEnd = next.end;
  }
  if (allExact) return { control: folded, exact: true };

  const end = segments[segments.length - 1].end;
  const middle = arcMidpoint(start, segments);
  return {
    control: {
      lat: 2 * middle.lat - (start.lat + end.lat) / 2,
      lng: 2 * middle.lng - (start.lng + end.lng) / 2,
    },
    exact: false,
  };
};

// Joins the curve start-first-middle and the curve middle-second-end into one curve from start to end (see
// joinCurveRun).
export const joinCurves = (
  start: LatLng,
  firstControl: LatLng,
  middle: LatLng,
  secondControl: LatLng,
  end: LatLng,
): CurveJoin => joinCurveRun(start, [{ control: firstControl, end: middle }, { control: secondControl, end }]);
