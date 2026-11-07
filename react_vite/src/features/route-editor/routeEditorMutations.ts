import { Gate, ObservationMarker, Polygon, RoutePoint } from '../../types';

export function updateItemById<T extends { id: string }>(
  items: T[],
  selectedId: string | null,
  updater: (item: T) => T,
): T[] {
  return items.map((item) => (item.id === selectedId ? updater(item) : item));
}

export function reorderItemsById<T extends { id: string }>(
  items: T[],
  selectedId: string | null,
  direction: 'up' | 'down',
): T[] {
  const index = items.findIndex((item) => item.id === selectedId);
  if (index === -1) return items;

  const reordered = [...items];
  if (direction === 'up' && index > 0) {
    [reordered[index], reordered[index - 1]] = [reordered[index - 1], reordered[index]];
  } else if (direction === 'down' && index < reordered.length - 1) {
    [reordered[index], reordered[index + 1]] = [reordered[index + 1], reordered[index]];
  }
  return reordered;
}

export function deleteItemById<T extends { id: string }>(items: T[], selectedId: string | null): T[] {
  return items.filter((item) => item.id !== selectedId);
}

/** A secret (hidden) gate is a gate that is checked and timed, like any other: its time check and gate check start on. */
export const SECRET_GATE_CHECKS = { isTiming: true, isPassing: true } as const;

const METRES_PER_NAUTICAL_MILE = 1852;

/** A gate's width is kept in metres and shown in nautical miles. */
export const nauticalMilesToMetres = (nauticalMiles: number): number => Math.round(nauticalMiles * METRES_PER_NAUTICAL_MILE);
export const metresToNauticalMiles = (metres: number): number => metres / METRES_PER_NAUTICAL_MILE;

/** The points with the given ids given the width (in metres); the others are as they were. */
export function setWidthOfPoints(points: RoutePoint[], ids: ReadonlySet<string>, widthMetres: number): RoutePoint[] {
  return points.map((point) => (ids.has(point.id) ? { ...point, width: widthMetres } : point));
}

export function normalizeDeletedBackboneRoutePoints(points: RoutePoint[]): RoutePoint[] {
  if (points.length === 0) return points;
  const normalized = [...points];
  normalized[0] = { ...normalized[0], type: 'sp', featureType: 'route_waypoint', name: 'SP' };
  normalized[normalized.length - 1] = {
    ...normalized[normalized.length - 1],
    type: 'fp',
    featureType: 'route_waypoint',
    name: 'FP',
  };
  return normalized;
}

export function renumberRoutePoints(points: RoutePoint[], isThreePointBackboneTask: boolean): RoutePoint[] {
  let waypointCounter = 0;
  let secretCounter = 1;

  return points.map((point, index) => {
    const nextPoint = { ...point };
    if (index === 0) {
      nextPoint.type = 'sp';
      nextPoint.name = 'SP';
      waypointCounter = 0;
      secretCounter = 1;
    } else if (index === points.length - 1) {
      nextPoint.type = 'fp';
      nextPoint.name = 'FP';
    } else if (isThreePointBackboneTask && index === 1) {
      // Three-point backbone tasks keep the middle backbone point fixed as MP
      // even after reverse/reorder actions.
      nextPoint.type = 'tp';
      nextPoint.name = 'MP';
    } else if (point.type === 'secret') {
      nextPoint.name = `Secret ${waypointCounter}.${secretCounter++}`;
    } else {
      waypointCounter += 1;
      nextPoint.name = `WP ${waypointCounter}`;
      // An unknown-leg trigger stays one: only its name follows the numbering
      if ((nextPoint.featureType === 'route_waypoint' || !nextPoint.featureType) && nextPoint.type !== 'ul') {
        nextPoint.type = 'tp';
      }
      secretCounter = 1;
    }
    return nextPoint;
  });
}

export function reverseRoutePoints(points: RoutePoint[], isThreePointBackboneTask: boolean): RoutePoint[] {
  if (points.length < 2) {
    return points;
  }

  const reversedPoints = [...points].reverse();
  const segmentInfo = points.slice(1).map((point) => ({
    segmentType: point.segmentType,
    controlLat: point.controlLat,
    controlLng: point.controlLng,
  }));
  const reversedSegmentInfo = segmentInfo.reverse();

  const updated = reversedPoints.map((point, index) => {
    const nextPoint = { ...point };

    if (index === 0) {
      nextPoint.type = 'sp';
      nextPoint.name = 'SP';
    } else if (index === reversedPoints.length - 1) {
      nextPoint.type = 'fp';
      nextPoint.name = 'FP';
    } else if (isThreePointBackboneTask && index === 1) {
      nextPoint.type = 'tp';
      nextPoint.name = 'MP';
    } else if (nextPoint.type !== 'secret' && nextPoint.type !== 'ul') {
      nextPoint.type = 'tp';
    }

    if (index > 0) {
      const segment = reversedSegmentInfo[index - 1];
      nextPoint.segmentType = segment.segmentType || 'straight';
      nextPoint.controlLat = segment.controlLat;
      nextPoint.controlLng = segment.controlLng;
    } else {
      nextPoint.segmentType = 'straight';
      delete nextPoint.controlLat;
      delete nextPoint.controlLng;
    }

    return nextPoint;
  });

  return renumberRoutePoints(updated, isThreePointBackboneTask);
}

export type SelectionCollectionMap = {
  routePoints: RoutePoint[];
  standalonePoints: RoutePoint[];
  gates: Gate[];
  observationMarkers: ObservationMarker[];
  polygons: Polygon[];
};
