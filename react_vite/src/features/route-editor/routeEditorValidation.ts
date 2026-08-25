import { getBearing, getDistance, isCollinear, toRad } from '../../utils/geoUtils.ts';
import { Gate, ObservationMarker, Polygon, RoutePoint } from '../../types';
import { SavePayload } from './types';
import { isSecretPointType } from '../../gateTypes';

const getAngleDiff = (a: number, b: number) => {
  let diff = a - b;
  while (diff > 180) diff -= 360;
  while (diff < -180) diff += 360;
  return diff;
};

export function validateRouteEditorState(
  routePoints: RoutePoint[],
  isThreePointBackboneTask: boolean,
  isCircleStandaloneTask: boolean,
  isTimedTurnpointStandaloneTask: boolean = false,
  isCurveRequiredTask: boolean = false,
): string[] {
  const errors: string[] = [];

  // 2.A1 explicitly includes curves: the route editor should make sure the
  // route contains at least one curved leg. 2.A2 (and every other CIMA
  // template) has no such requirement.
  if (isCurveRequiredTask && !routePoints.some((point) => point.segmentType === 'curved')) {
    errors.push('2.A1 requires at least one curved leg. Use the curve tool to add a curved segment between two route points.');
  }

  // Authoring contract notes:
  // - 3-point backbone tasks intentionally keep the ordered backbone limited to
  //   SP/MP/FP while catalogue/evidence points live outside the backbone lane.
  // - Circle tasks, and 2.A6/2.B2 turnpoint-hunt tasks, do the opposite: all
  //   authored markers stay in the standalone lane and route_path should
  //   remain empty - there is no backbone at all.
  const isStandaloneOnlyTask = isCircleStandaloneTask || isTimedTurnpointStandaloneTask;

  if (!isStandaloneOnlyTask) {
    if (routePoints.length < 2) {
      errors.push('Route must have at least 2 backbone points.');
    } else {
      if (routePoints[0].type !== 'sp') errors.push("First route backbone point must be type 'Start'.");
      if (routePoints[routePoints.length - 1].type !== 'fp') errors.push("Last route backbone point must be type 'Finish'.");

      for (let i = 1; i < routePoints.length - 1; i++) {
        if (routePoints[i].type === 'sp') errors.push(`Backbone point ${i + 1} cannot be Start (middle of route).`);
        if (routePoints[i].type === 'fp') errors.push(`Backbone point ${i + 1} cannot be Finish (middle of route).`);
      }
    }
  }

  if (isThreePointBackboneTask && routePoints.length !== 3) {
    errors.push('This task requires exactly three route backbone points: SP, MP, and FP.');
  }

  if (isStandaloneOnlyTask && routePoints.length > 0) {
    errors.push(
      isCircleStandaloneTask
        ? 'Circle tasks should not use a route backbone. Place all circle markers as standalone points.'
        : 'This task requires no route backbone. Place the timed and catalogue turnpoints as standalone points.'
    );
  }

  routePoints.forEach((point, index) => {
    if (!isSecretPointType(point.type)) return;
    if (index === 0 || index === routePoints.length - 1) {
      errors.push(`Secret point "${point.name}" cannot be Start or Finish.`);
      return;
    }

    const previous = routePoints[index - 1];
    const next = routePoints[index + 1];
    const isCurved = point.segmentType === 'curved' || next.segmentType === 'curved';
    if (!isCurved && !isCollinear(previous, point, next)) {
      errors.push(`Secret point "${point.name}" is not on a straight line between previous and next points.`);
    }
  });

  if (!isStandaloneOnlyTask && routePoints.length >= 3) {
    for (let index = 1; index < routePoints.length - 1; index++) {
      const point = routePoints[index];
      if (point.name.startsWith('Curve')) continue;

      const previous = routePoints[index - 1];
      const next = routePoints[index + 1];
      const firstBearing = getBearing(previous, point);
      const secondBearing = getBearing(point, next);
      const diff = getAngleDiff(secondBearing, firstBearing);
      const miterFactor = Math.min(1 / Math.cos(toRad(diff / 2)), 5);
      const miterLength = (point.width / 2) * miterFactor;
      const previousDistance = getDistance(previous, point);
      const nextDistance = getDistance(point, next);

      if (miterLength > previousDistance) {
        errors.push(`Waypoint "${point.name}" turn is too sharp for the corridor width and the previous leg length (${(previousDistance / 1852).toFixed(2)} NM). Rendering may break.`);
      } else if (miterLength > previousDistance * 0.7) {
        errors.push(`Waypoint "${point.name}" turn is nearly too sharp for the previous leg. Rendering might be distorted.`);
      }

      if (miterLength > nextDistance) {
        const message = `Waypoint "${point.name}" turn is too sharp for the corridor width and the next leg length (${(nextDistance / 1852).toFixed(2)} NM). Rendering may break.`;
        if (!errors.includes(message)) errors.push(message);
      } else if (miterLength > nextDistance * 0.7) {
        const message = `Waypoint "${point.name}" turn is nearly too sharp for the next leg. Rendering might be distorted.`;
        if (!errors.includes(message)) errors.push(message);
      }
    }
  }

  return errors;
}

export function buildRouteEditorSavePayload(args: {
  routeName: string;
  routePoints: RoutePoint[];
  standalonePoints: RoutePoint[];
  gates: Gate[];
  observationMarkers: ObservationMarker[];
  polygons: Polygon[];
  showCorridor: boolean;
  maxObsDist: number;
  hideLabels: boolean;
  selectedTaskTemplateId: string | null;
  intendedTaskTypes: string[];
}): SavePayload {
  const {
    routeName,
    routePoints,
    standalonePoints,
    gates,
    observationMarkers,
    polygons,
    showCorridor,
    maxObsDist,
    hideLabels,
    selectedTaskTemplateId,
    intendedTaskTypes,
  } = args;

  // Persistence contract: route_path is derived from ordered backbone points
  // only. Standalone authored primitives (catalogue/circle/etc.) are persisted
  // as separate Point features and must never leak into the route backbone.
  const routePathCoordinates = routePoints.map((point) => [point.lng, point.lat]);
  const dummyBranchPoints = standalonePoints.filter((point) => point.featureType === 'dummy_branch_waypoint');
  const otherStandalonePoints = standalonePoints.filter((point) => point.featureType !== 'dummy_branch_waypoint');

  return {
    name: routeName,
    route: {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { featureType: 'route_path' },
          geometry: {
            type: 'LineString',
            coordinates: routePathCoordinates,
          },
        },
        ...routePoints.map((point, index) => ({
          type: 'Feature',
          properties: {
            id: point.id,
            name: point.name,
            pointType: point.type,
            featureType: point.featureType || 'route_waypoint',
            segmentType: point.segmentType || 'straight',
            controlLat: point.controlLat,
            controlLng: point.controlLng,
            width: point.width,
            isTiming: point.isTiming,
            isPassing: point.isPassing,
            scoreValue: point.scoreValue ?? undefined,
            unknownLegHeading: point.unknownLegHeading ?? undefined,
            sequence: index,
          },
          geometry: {
            type: 'Point',
            coordinates: [point.lng, point.lat],
          },
        })),
        ...otherStandalonePoints.map((point, index) => ({
          type: 'Feature',
          properties: {
            id: point.id,
            name: point.name,
            pointType: point.type,
            featureType: point.featureType,
            segmentType: point.segmentType || 'straight',
            width: point.width,
            isTiming: point.isTiming,
            isPassing: point.isPassing,
            scoreValue: point.scoreValue ?? undefined,
            sequence: routePoints.length + index,
          },
          geometry: {
            type: 'Point',
            coordinates: [point.lng, point.lat],
          },
        })),
        ...dummyBranchPoints.map((point, index) => ({
          type: 'Feature',
          properties: {
            id: point.id,
            name: point.name,
            pointType: point.type,
            featureType: 'dummy_branch_waypoint',
            segmentType: point.segmentType || 'straight',
            width: point.width,
            isTiming: point.isTiming,
            isPassing: point.isPassing,
            triggerPointId: point.triggerPointId || undefined,
            branchSequence: point.branchSequence ?? index,
            sequence: routePoints.length + otherStandalonePoints.length + index,
          },
          geometry: {
            type: 'Point',
            coordinates: [point.lng, point.lat],
          },
        })),
        ...gates.map((gate) => ({
          type: 'Feature',
          properties: {
            id: gate.id,
            name: gate.name,
            gateType: gate.type,
            featureType: gate.type === 'landing' ? 'landing_gate' : 'takeoff_gate',
            width: gate.width,
          },
          geometry: {
            type: 'LineString',
            coordinates: [
              [gate.p1.lng, gate.p1.lat],
              [gate.p2.lng, gate.p2.lat],
            ],
          },
        })),
        ...observationMarkers.map((marker) => ({
          type: 'Feature',
          properties: {
            id: marker.id,
            name: marker.name,
            targetName: marker.targetName || undefined,
            featureType: 'observation_photo',
          },
          geometry: { type: 'Point', coordinates: [marker.lng, marker.lat] },
        })),
        ...polygons.map((polygon) => ({
          type: 'Feature',
          properties: {
            id: polygon.id,
            name: polygon.name,
            polygonType: polygon.type,
            featureType: 'zone',
          },
          geometry: {
            type: 'Polygon',
            coordinates: [
              [...polygon.points.map((point) => [point.lng, point.lat]), [polygon.points[0].lng, polygon.points[0].lat]],
            ],
          },
        })),
      ],
    },
    settings: {
      showCorridor,
      maxObsDist,
      hideLabels,
      selectedTaskTemplateId,
    },
    intended_task_types: intendedTaskTypes,
  };
}
