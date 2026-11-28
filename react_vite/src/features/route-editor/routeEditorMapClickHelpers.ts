import { getDestinationPoint, getBearing, getDistance, getDistanceFromLine } from '../../utils/geoUtils';
import { curvePointAt, MIN_CURVE_END_FRACTION, nearestCurveParameter, splitCurve, TOO_CLOSE_TO_LEG_END_NOTICE } from './curveSplit';
import { Gate, LatLng, Mode, ObservationMarker, RoutePoint } from '../../types';

const THREE_POINT_BACKBONE_TEMPLATE: Array<Pick<RoutePoint, 'name' | 'type' | 'featureType'>> = [
  { name: 'SP', type: 'sp', featureType: 'route_waypoint' },
  { name: 'MP', type: 'tp', featureType: 'route_waypoint' },
  { name: 'FP', type: 'fp', featureType: 'route_waypoint' },
];

export function createCatalogueTurnpoint(latlng: LatLng, catalogueCount: number): RoutePoint {
  return {
    id: crypto.randomUUID(),
    lat: latlng.lat,
    lng: latlng.lng,
    name: `TP ${catalogueCount}`,
    type: 'catalogue_turnpoint',
    featureType: 'catalogue_turnpoint',
    width: 1852,
    isTiming: false,
    isPassing: true,
    segmentType: 'straight',
    scoreValue: null,
  };
}

export function createStandaloneWizardPoint(
  latlng: LatLng,
  pointType: RoutePoint['type'],
  featureType: RoutePoint['featureType'] | undefined,
  label: string | null,
  count = 1,
): RoutePoint {
  return {
    id: crypto.randomUUID(),
    lat: latlng.lat,
    lng: latlng.lng,
    name: label || `${pointType} ${count}`,
    type: pointType,
    featureType,
    width: 1852,
    isTiming: pointType === 'timed_turnpoint',
    isPassing: true,
    segmentType: 'straight',
  };
}

export function createInsertedRoutePoint(
  latlng: LatLng,
  pointType: RoutePoint['type'],
  featureType: RoutePoint['featureType'] | undefined,
  label: string | null,
  count: number,
): RoutePoint {
  return {
    id: crypto.randomUUID(),
    lat: latlng.lat,
    lng: latlng.lng,
    name: label || `${pointType} ${count}`,
    type: pointType,
    featureType,
    width: 1852,
    // Secret gates are checked and timed from the start (see SECRET_GATE_CHECKS)
    isTiming: pointType === 'tp' || pointType === 'secret',
    isPassing: true,
    segmentType: 'straight',
  };
}

export function createBackboneRoutePoint(
  latlng: LatLng,
  existingRoutePoints: RoutePoint[],
  isThreePointBackboneTask: boolean,
  addCurveMode: boolean,
): RoutePoint {
  const count = existingRoutePoints.length;
  let segmentType: 'straight' | 'curved' = 'straight';
  let controlLat = 0;
  let controlLng = 0;

  if (addCurveMode && count > 0) {
    const prevPoint = existingRoutePoints[count - 1];
    segmentType = 'curved';
    const midLat = (prevPoint.lat + latlng.lat) / 2;
    const midLng = (prevPoint.lng + latlng.lng) / 2;
    controlLat = midLat + (latlng.lng - prevPoint.lng) * 0.2;
    controlLng = midLng - (latlng.lat - prevPoint.lat) * 0.2;
  }

  const templatePoint = isThreePointBackboneTask ? THREE_POINT_BACKBONE_TEMPLATE[count] : null;
  return {
    id: crypto.randomUUID(),
    lat: latlng.lat,
    lng: latlng.lng,
    name: templatePoint?.name || (count === 0 ? 'Start' : 'Finish'),
    type: templatePoint?.type || (count === 0 ? 'sp' : 'fp'),
    featureType: templatePoint?.featureType || 'route_waypoint',
    width: 1852,
    isTiming: true,
    isPassing: true,
    segmentType,
    controlLat,
    controlLng,
  };
}

export function normalizeRoutePointsBeforeAppend(routePoints: RoutePoint[], isThreePointBackboneTask: boolean): RoutePoint[] {
  const newPoints = [...routePoints];
  const count = newPoints.length;

  if (!isThreePointBackboneTask && count > 0) {
    const lastRoutePointIndex = newPoints.length - 1;
    if (newPoints[lastRoutePointIndex]?.type === 'fp') {
      newPoints[lastRoutePointIndex] = {
        ...newPoints[lastRoutePointIndex],
        type: 'tp',
        featureType: 'route_waypoint',
        name: `WP ${count}`,
      };
    }
  }

  return newPoints;
}

export function createTakeoffLandingGate(latlng: LatLng, tempGatePoint: LatLng, gateType: 'landing' | 'takeoff', gateCount: number): Gate {
  return {
    id: crypto.randomUUID(),
    name: `${gateType === 'landing' ? 'L' : 'TO'} Gate ${gateCount}`,
    type: gateType,
    p1: tempGatePoint,
    p2: latlng,
    width: 50,
  };
}

export function getMinimumObservationDistance(latlng: LatLng, routePoints: RoutePoint[]): number {
  let minDist = Infinity;

  for (let i = 0; i < routePoints.length - 1; i++) {
    const p1 = routePoints[i];
    const p2 = routePoints[i + 1];
    let distance = Infinity;

    if (p2.segmentType === 'curved' && p2.controlLat != null && p2.controlLng != null) {
      const steps = 20;
      let prevPoint: LatLng = { lat: p1.lat, lng: p1.lng };
      for (let j = 1; j <= steps; j++) {
        const t = j / steps;
        const invT = 1 - t;
        const lat = (invT * invT * p1.lat) + (2 * invT * t * p2.controlLat) + (t * t * p2.lat);
        const lng = (invT * invT * p1.lng) + (2 * invT * t * p2.controlLng) + (t * t * p2.lng);
        const curr: LatLng = { lat, lng };
        const segDist = getDistanceFromLine(latlng, prevPoint, curr);
        if (segDist < distance) distance = segDist;
        prevPoint = curr;
      }
    } else {
      distance = getDistanceFromLine(latlng, p1, p2);
    }

    if (distance < minDist) minDist = distance;
  }

  return minDist;
}

/** "Obs 1", "Obs 2", ...: the first of them that is not a name already in use (a photo is its name). */
export function nextObservationName(takenNames: Iterable<string>): string {
  const taken = new Set(takenNames);
  let number = 1;
  while (taken.has(`Obs ${number}`)) number += 1;
  return `Obs ${number}`;
}

export function createObservationMarker(latlng: LatLng, takenNames: Iterable<string>): ObservationMarker {
  return {
    id: crypto.randomUUID(),
    lat: latlng.lat,
    lng: latlng.lng,
    name: nextObservationName(takenNames),
    targetName: '',
  };
}

// --- Which existing thing a click on the map hits ---

// An existing point, gate end, photo or polygon handle is hit by a click within this many pixels of its centre, not only
// on the small mark that is drawn. The same radius decides when a click in a placing mode selects an existing point of
// the kind being placed instead of placing a new one.
export const HIT_RADIUS_PX = 14;

export type HitKind = 'point' | 'standalone_point' | 'gate' | 'observation' | 'polygon_vertex' | 'temp_polygon_start';

export interface PixelPoint {
  x: number;
  y: number;
}

export interface HitCandidate extends PixelPoint {
  key: string;
  kind: HitKind;
}

// The candidate nearest to the click, when it is within [radius] pixels (the first one on a tie); null when none is.
export function findNearestHit<T extends PixelPoint>(click: PixelPoint, candidates: readonly T[], radius: number = HIT_RADIUS_PX): T | null {
  let best: T | null = null;
  let bestDistance = Infinity;
  for (const candidate of candidates) {
    const distance = Math.hypot(candidate.x - click.x, candidate.y - click.y);
    if (distance <= radius && distance < bestDistance) {
      best = candidate;
      bestDistance = distance;
    }
  }
  return best;
}

// The kinds of existing thing a click selects in a placing mode: what the mode places. Select mode has none (the marks'
// own hit areas do it there).
export function hitKindsForMode(mode: Mode): HitKind[] {
  switch (mode) {
    case 'add_point':
      return ['point', 'standalone_point'];
    case 'add_catalogue_turnpoint':
      return ['standalone_point'];
    case 'add_observation':
      return ['observation'];
    case 'add_polygon':
      return ['temp_polygon_start'];
    case 'add_landing':
    case 'add_takeoff':
      return ['gate'];
    default:
      return [];
  }
}

// The existing thing that a click in [mode] selects instead of placing something, or null when it places.
export function findPlacingModeHit<T extends HitCandidate>(click: PixelPoint, candidates: readonly T[], mode: Mode, radius: number = HIT_RADIUS_PX): T | null {
  const kinds = hitKindsForMode(mode);
  if (kinds.length === 0) return null;
  return findNearestHit(click, candidates.filter((candidate) => kinds.includes(candidate.kind)), radius);
}

// The curve of a leg as 20 straight pieces, as it is drawn (the same formula as getQuadraticBezierPoints, which needs Leaflet).
const curvePoints = (from: LatLng, to: LatLng, control: LatLng, pieces = 20): LatLng[] => (
  Array.from({ length: pieces + 1 }, (_, index) => curvePointAt(from, control, to, index / pieces))
);

// The new control point of the point that ends a curve that was split: it keeps the point but gets the second half.
export interface ControlPatch {
  id: string;
  controlLat: number;
  controlLng: number;
}

export type LegClickAction =
  | { kind: 'none' }
  // The click cannot place the point where it is: the editor says why
  | { kind: 'notice'; message: string }
  // A point inserted at [index]; [endControl] is the new control point of the point after it, when the point splits a curve
  | { kind: 'insert'; index: number; point: RoutePoint; endControl?: ControlPatch };

const isCurvedLeg = (end: RoutePoint): boolean => end.segmentType === 'curved' && !!end.controlLat && !!end.controlLng;

// The route with the point of [action] inserted, and the curve it splits cut in two.
export function applyLegInsert(routePoints: RoutePoint[], action: Extract<LegClickAction, { kind: 'insert' }>): RoutePoint[] {
  const next = [...routePoints];
  next.splice(action.index, 0, action.point);
  const patch = action.endControl;
  if (!patch) return next;
  return next.map((point) => (point.id === patch.id ? { ...point, controlLat: patch.controlLat, controlLng: patch.controlLng } : point));
}

/**
 * A click on a curved leg: a point at the nearest point of the curve, and the curve cut in two there. Together the two
 * curves are exactly the old one (see splitCurve): the first ends at the new point with the first control point, the
 * second keeps the old end point with the second control point.
 */
function insertOnCurvedLeg(
  routePoints: RoutePoint[],
  legIndex: number,
  click: LatLng,
  createPoint: (location: LatLng) => RoutePoint,
): LegClickAction {
  const start = routePoints[legIndex];
  const end = routePoints[legIndex + 1];
  const control = { lat: end.controlLat as number, lng: end.controlLng as number };
  const t = nearestCurveParameter(start, control, end, click);
  if (t < MIN_CURVE_END_FRACTION || t > 1 - MIN_CURVE_END_FRACTION) {
    return { kind: 'notice', message: TOO_CLOSE_TO_LEG_END_NOTICE };
  }
  const { firstControl, middle, secondControl } = splitCurve(start, control, end, t);
  const point: RoutePoint = {
    ...createPoint(middle),
    segmentType: 'curved',
    controlLat: firstControl.lat,
    controlLng: firstControl.lng,
  };
  return {
    kind: 'insert',
    index: legIndex + 1,
    point,
    endControl: { id: end.id, controlLat: secondControl.lat, controlLng: secondControl.lng },
  };
}

/**
 * What a click on a leg of the route does. A point is only placed when [legInsertType] says a click places one (the
 * hidden gate tool, or a guide step): in select mode a click on a leg does nothing.
 */
export function legClickAction(routePoints: RoutePoint[], click: LatLng, legInsertType: RoutePoint['type'] | null): LegClickAction {
  if (!legInsertType) return { kind: 'none' };

  let bestIndex = -1;
  let minDistance = Infinity;
  for (let i = 0; i < routePoints.length - 1; i++) {
    const p1 = routePoints[i];
    const p2 = routePoints[i + 1];
    let dist = Infinity;
    if (isCurvedLeg(p2)) {
      const curve = curvePoints(p1, p2, { lat: p2.controlLat as number, lng: p2.controlLng as number });
      for (let j = 0; j < curve.length - 1; j++) {
        const d = getDistanceFromLine(click, curve[j], curve[j + 1]);
        if (d < dist) dist = d;
      }
    } else {
      dist = getDistanceFromLine(click, p1, p2);
    }
    if (dist < minDistance) {
      minDistance = dist;
      bestIndex = i;
    }
  }
  if (bestIndex === -1) return { kind: 'none' };

  const p1 = routePoints[bestIndex];
  const p2 = routePoints[bestIndex + 1];
  const isSecret = legInsertType === 'secret';
  const createPoint = (location: LatLng): RoutePoint => ({
    id: crypto.randomUUID(),
    lat: location.lat,
    lng: location.lng,
    name: isSecret
      ? `Secret ${routePoints.length}`
      : `${legInsertType.toUpperCase()} ${routePoints.filter((existing) => existing.type === legInsertType).length + 1}`,
    type: legInsertType,
    featureType: 'route_waypoint',
    width: isSecret ? 1000 : 1852,
    // Checked and timed from the start, a secret gate too (see SECRET_GATE_CHECKS)
    isTiming: true,
    isPassing: true,
    segmentType: 'straight',
  });
  if (isCurvedLeg(p2)) return insertOnCurvedLeg(routePoints, bestIndex, click, createPoint);

  // On the leg's line: the point of the line at the click's distance from the leg's start
  const newLoc = getDestinationPoint(p1, getDistance(p1, click), getBearing(p1, p2));
  return { kind: 'insert', index: bestIndex + 1, point: createPoint(newLoc) };
}

/** The type of point a click on a leg places: the hidden gate tool's, or the one a guide step asks for; null in select mode. */
export function legInsertTypeFor(mode: Mode, wizardRouteInsertType: RoutePoint['type'] | null): RoutePoint['type'] | null {
  return mode === 'add_hidden_gate' ? 'secret' : wizardRouteInsertType;
}
