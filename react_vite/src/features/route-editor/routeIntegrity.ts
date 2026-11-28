import type { SetStateAction } from 'react';
import type { ObservationMarker, RoutePoint } from '../../types';
import { type CurveSegment, joinCurveRun } from './curveSplit';
import { getMinimumObservationDistance } from './routeEditorMapClickHelpers';

// What a change of the route takes with it. A hidden ("secret") gate lies on one leg and cannot bend the route, and a
// photo is of a feature that must stay within the maximum observation distance of the route. Neither can be moved to
// follow a changed leg (they belong to a feature on the ground), so they are removed and the user is told.
//
// Only hidden gates sit on legs: known time gates, catalogue turn points, circle markers and extension waypoints are
// standalone points (not in routePoints, or not tied to a leg), and unknown-leg points are backbone points. They are
// never removed by a change of the route.

const isHidden = (point: RoutePoint): boolean => point.type === 'secret';

// A leg: the run from one route point that is not a hidden gate to the next, with the hidden gates between them.
export interface Leg {
  from: RoutePoint;
  to: RoutePoint;
  hiddenGates: RoutePoint[];
  // The control points of the curved segments of the leg, in order from [from] to [to]. A straight leg has none, and
  // a hidden gate on a straight leg does not add one.
  controls: Array<[number, number]>;
  // The control points of the curved segments as they are, not joined (a curve with hidden gates on it has one per part).
  segmentControls: Array<[number, number]>;
  // Whether every join of curved segments was of the two halves of one curve (see joinCurveRun). Parts that are not (one
  // was reshaped) are joined into a curve that only approximates them, which is not the leg it was.
  exact: boolean;
}

const hasCurve = (point: RoutePoint): boolean => point.segmentType === 'curved' && !!point.controlLat && !!point.controlLng;

// The curves of the run of points [chain] (a leg: its two end points and the hidden gates between them). Consecutive
// curved segments are joined into one curve (see joinCurveRun), so a curve with hidden gates on it has the control point
// of the curve it was split from, and a leg is the same leg whether or not a hidden gate splits its curve. A straight
// segment between curved ones keeps them apart.
const legControls = (chain: RoutePoint[]): Pick<Leg, 'controls' | 'segmentControls' | 'exact'> => {
  const controls: Array<[number, number]> = [];
  const segmentControls: Array<[number, number]> = [];
  let exact = true;
  // The run of consecutive curved segments being collected, to be joined at once (the result does not depend on order)
  let runStart: RoutePoint | null = null;
  let run: CurveSegment[] = [];
  const flush = () => {
    if (runStart && run.length > 0) {
      const join = joinCurveRun(runStart, run);
      controls.push([join.control.lat, join.control.lng]);
      exact = exact && join.exact;
    }
    runStart = null;
    run = [];
  };
  for (let index = 1; index < chain.length; index += 1) {
    const segmentEnd = chain[index];
    if (!hasCurve(segmentEnd)) {
      flush();
      continue;
    }
    const segmentControl = { lat: segmentEnd.controlLat as number, lng: segmentEnd.controlLng as number };
    segmentControls.push([segmentControl.lat, segmentControl.lng]);
    if (!runStart) runStart = chain[index - 1];
    run.push({ control: segmentControl, end: segmentEnd });
  }
  flush();
  return { controls, segmentControls, exact };
};

export const routeLegs = (points: RoutePoint[]): Leg[] => {
  const legs: Leg[] = [];
  let startIndex = -1;
  points.forEach((point, index) => {
    if (isHidden(point)) return;
    if (startIndex >= 0) {
      const run = points.slice(startIndex + 1, index + 1);
      legs.push({
        from: points[startIndex],
        to: point,
        hiddenGates: run.filter(isHidden),
        ...legControls(points.slice(startIndex, index + 1)),
      });
    }
    startIndex = index;
  });
  return legs;
};

const legKey = (leg: Leg): string => [leg.from.id, leg.to.id].sort().join('|');

const samePosition = (a: RoutePoint, b: RoutePoint): boolean => a.lat === b.lat && a.lng === b.lng;

// Within a tenth of a millimetre: a curve split and joined again comes back with rounding errors only
const CONTROL_TOLERANCE = 1e-9;

const sameControls = (a: Array<[number, number]>, b: Array<[number, number]>): boolean => (
  a.length === b.length
  && a.every((control, index) => (
    Math.abs(control[0] - b[index][0]) <= CONTROL_TOLERANCE && Math.abs(control[1] - b[index][1]) <= CONTROL_TOLERANCE
  ))
);

// Whether [leg] is the same line as [old] (the same end points in the same places and the same curve), the route
// reversed or not.
const sameLeg = (leg: Leg, old: Leg): boolean => {
  const sameDirection = leg.from.id === old.from.id;
  const oldFrom = sameDirection ? old.from : old.to;
  const oldTo = sameDirection ? old.to : old.from;
  const oldControls = sameDirection ? old.controls : [...old.controls].reverse();
  if (!samePosition(leg.from, oldFrom) || !samePosition(leg.to, oldTo) || !sameControls(leg.controls, oldControls)) return false;
  if (leg.exact) return true;
  // A curve whose parts do not make one curve is the same leg only when no part changed
  const oldSegments = sameDirection ? old.segmentControls : [...old.segmentControls].reverse();
  return sameControls(leg.segmentControls, oldSegments);
};

export interface RouteRemoval {
  hiddenGates: RoutePoint[];
  photos: ObservationMarker[];
  // How many changed legs the removed hidden gates were on.
  legCount: number;
}

export const EMPTY_REMOVAL: RouteRemoval = { hiddenGates: [], photos: [], legCount: 0 };

export const hasRemoval = (removal: RouteRemoval): boolean => removal.hiddenGates.length > 0 || removal.photos.length > 0;

const segmentKey = (from: RoutePoint, to: RoutePoint): string => (
  `${from.lat},${from.lng},${to.lat},${to.lng},${to.segmentType === 'curved' ? `${to.controlLat},${to.controlLng}` : ''}`
);

// Builds the check for changes of [before]: the legs and the photos' distances of the route as it is are worked out
// once, and the distances of a segment are remembered, so that a drag (many changes of the same route, each moving
// only the legs of one point) only works out the legs that moved.
export const createRouteIntegrityCheck = (before: RoutePoint[], photos: ObservationMarker[], maxObsDist: number) => {
  const oldLegs = new Map<string, Leg>();
  routeLegs(before).forEach((leg) => oldLegs.set(legKey(leg), leg));
  const segmentDistances = new Map<string, number>();

  // The distance from the route, with the same geometry as the editor's check when a photo is placed: straight legs
  // and the drawn curves.
  const distanceToRoute = (photo: ObservationMarker, points: RoutePoint[]): number => {
    let nearest = Infinity;
    for (let index = 0; index < points.length - 1; index += 1) {
      const key = `${photo.id}|${photo.lat},${photo.lng}|${segmentKey(points[index], points[index + 1])}`;
      let distance = segmentDistances.get(key);
      if (distance === undefined) {
        distance = getMinimumObservationDistance(photo, [points[index], points[index + 1]]);
        if (segmentDistances.size > 5000) segmentDistances.clear();
        segmentDistances.set(key, distance);
      }
      if (distance < nearest) nearest = distance;
    }
    return nearest;
  };
  // A photo that was out of range already is not this change's doing
  const inRangeBefore = photos.filter((photo) => distanceToRoute(photo, before) <= maxObsDist);
  const wasHidden = new Map(before.map((point) => [point.id, isHidden(point)]));

  return (after: RoutePoint[]): RouteRemoval => {
    const hiddenGates: RoutePoint[] = [];
    let legCount = 0;
    for (const leg of routeLegs(after)) {
      if (leg.hiddenGates.length === 0) continue;
      const old = oldLegs.get(legKey(leg));
      if (old && sameLeg(leg, old)) continue;
      // A point the change itself made a hidden gate is the user's choice, not something to take away
      const removed = leg.hiddenGates.filter((gate) => wasHidden.get(gate.id) !== false);
      if (removed.length === 0) continue;
      hiddenGates.push(...removed);
      legCount += 1;
    }
    // The photos are measured against the route that is left: the removed hidden gates no longer bend it. Without a
    // route (fewer than two points) there is nothing to measure against: the photos stay.
    const removedIds = new Set(hiddenGates.map((gate) => gate.id));
    const remaining = removedIds.size > 0 ? after.filter((point) => !removedIds.has(point.id)) : after;
    const removedPhotos = remaining.length < 2
      ? []
      : inRangeBefore.filter((photo) => distanceToRoute(photo, remaining) > maxObsDist);
    return { hiddenGates, photos: removedPhotos, legCount };
  };
};

// What the change from [before] to [after] removes.
export const removedByRouteChange = (
  before: RoutePoint[],
  after: RoutePoint[],
  photos: ObservationMarker[],
  maxObsDist: number,
): RouteRemoval => createRouteIntegrityCheck(before, photos, maxObsDist)(after);

// The route points and photos without what [removal] removes.
export const withoutRemoval = (
  points: RoutePoint[],
  photos: ObservationMarker[],
  removal: RouteRemoval,
): { routePoints: RoutePoint[]; observationMarkers: ObservationMarker[] } => {
  const gateIds = new Set(removal.hiddenGates.map((gate) => gate.id));
  const photoIds = new Set(removal.photos.map((photo) => photo.id));
  return {
    routePoints: gateIds.size > 0 ? points.filter((point) => !gateIds.has(point.id)) : points,
    observationMarkers: photoIds.size > 0 ? photos.filter((photo) => !photoIds.has(photo.id)) : photos,
  };
};

// Joins the curves back together where hidden gates were taken off them. When a hidden gate between two curved segments
// is gone (deleted by hand, or removed because its leg changed), the curve that ends at the next point is no longer
// from the point before the gate: its control point becomes that of the one curve from the point before the gates to
// that point (see joinCurveRun). [points] is the route without the gates; [sequence] has them, in order, with the data
// they had (the route before the change, or the route with the gates still in it).
export const joinCurvesOverRemovedGates = (
  points: RoutePoint[],
  sequence: RoutePoint[],
  removedIds: ReadonlySet<string>,
): RoutePoint[] => {
  if (removedIds.size === 0) return points;
  const sequenceIndex = new Map(sequence.map((point, index) => [point.id, index]));
  let joined: RoutePoint[] | null = null;
  for (let index = 1; index < points.length; index += 1) {
    const end = points[index];
    const endIndex = sequenceIndex.get(end.id);
    if (endIndex === undefined || !hasCurve(end)) continue;
    const gates: RoutePoint[] = [];
    let before = endIndex - 1;
    while (before >= 0 && removedIds.has(sequence[before].id)) {
      gates.unshift(sequence[before]);
      before -= 1;
    }
    // The run must start at the point this one now follows, and all of it must be curves to join
    if (gates.length === 0 || before < 0 || sequence[before].id !== points[index - 1].id || !gates.every(hasCurve)) continue;
    const start = points[index - 1];
    const control = joinCurveRun(
      start,
      [...gates, end].map((part) => ({ control: { lat: part.controlLat as number, lng: part.controlLng as number }, end: part })),
    ).control;
    joined = joined ?? [...points];
    joined[index] = { ...end, controlLat: control.lat, controlLng: control.lng };
  }
  return joined ?? points;
};

const MAX_NAMES = 5;

// "A", "A and B", "A, B and C"; more than five names: the first five and "N more".
const nameList = (names: string[]): string => {
  const shown = names.length > MAX_NAMES ? [...names.slice(0, MAX_NAMES), `${names.length - MAX_NAMES} more`] : names;
  if (shown.length === 1) return shown[0];
  return `${shown.slice(0, -1).join(', ')} and ${shown[shown.length - 1]}`;
};

const nauticalMiles = (metres: number): string => String(Number((metres / 1852).toFixed(2)));

// The notice after a change that removed something, or null when it removed nothing.
export const removalNotice = (removal: RouteRemoval, maxObsDist: number): string | null => {
  const gates = removal.hiddenGates.map((gate) => gate.name);
  const photos = removal.photos.map((photo) => photo.name);
  if (gates.length === 0 && photos.length === 0) return null;

  const parts: string[] = [];
  if (gates.length > 0) parts.push(`hidden ${gates.length === 1 ? 'gate' : 'gates'} ${nameList(gates)}`);
  if (photos.length > 0) parts.push(`${photos.length === 1 ? 'photo' : 'photos'} ${nameList(photos)}`);

  const reasons: string[] = [];
  if (gates.length > 0) {
    const manyLegs = removal.legCount > 1;
    reasons.push(`the ${manyLegs ? 'legs' : 'leg'} ${gates.length === 1 ? 'it was' : 'they were'} on ${manyLegs ? 'have' : 'has'} changed`);
  }
  if (photos.length > 0) {
    const distance = `more than ${nauticalMiles(maxObsDist)} NM from the route`;
    if (gates.length > 0) reasons.push(`${photos.length === 1 ? 'the photo is' : 'the photos are'} now too far from the route`);
    else reasons.push(`${photos.length === 1 ? 'it is' : 'they are'} now ${distance}`);
  }
  return `Removed ${parts.join(' and ')}: ${reasons.join(' and ')}.`;
};

export interface RouteChangePlan {
  // The route points after the change and the removal (the same array when the change changes nothing).
  points: RoutePoint[];
  observationMarkers: ObservationMarker[];
  removal: RouteRemoval;
}

// A change of the route points ([update] as given to a state setter) with what it takes with it.
export const planRouteChange = (
  before: RoutePoint[],
  update: SetStateAction<RoutePoint[]>,
  photos: ObservationMarker[],
  maxObsDist: number,
): RouteChangePlan => {
  const changed = typeof update === 'function' ? update(before) : update;
  if (changed === before) return { points: before, observationMarkers: photos, removal: EMPTY_REMOVAL };
  // A hidden gate deleted by hand leaves its curve in one piece
  const changedIds = new Set(changed.map((point) => point.id));
  const deletedGates = new Set(before.filter((point) => isHidden(point) && !changedIds.has(point.id)).map((point) => point.id));
  const joinedChange = joinCurvesOverRemovedGates(changed, before, deletedGates);
  const removal = removedByRouteChange(before, joinedChange, photos, maxObsDist);
  const { routePoints, observationMarkers } = withoutRemoval(joinedChange, photos, removal);
  const joinedPoints = joinCurvesOverRemovedGates(routePoints, joinedChange, new Set(removal.hiddenGates.map((gate) => gate.id)));
  return { points: joinedPoints, observationMarkers, removal };
};
