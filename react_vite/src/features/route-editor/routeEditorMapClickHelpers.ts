import { getDistanceFromLine } from '../../utils/geoUtils';
import { Gate, LatLng, ObservationMarker, RoutePoint } from '../../types';

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
    isSecret: false,
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
    isSecret: false,
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
    isTiming: pointType === 'known_time_gate' || pointType === 'tp',
    isPassing: true,
    isSecret: false,
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
    isSecret: false,
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

export function createObservationMarker(latlng: LatLng, markerCount: number): ObservationMarker {
  return {
    id: crypto.randomUUID(),
    lat: latlng.lat,
    lng: latlng.lng,
    name: `Obs ${markerCount}`,
    targetName: '',
  };
}
