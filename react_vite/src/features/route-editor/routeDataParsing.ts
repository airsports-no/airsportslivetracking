import { Gate, ObservationMarker, Polygon, RoutePoint } from '../../types';

const POINT_FEATURE_TYPES = new Set([
  'route_waypoint',
  'catalogue_turnpoint',
  'circle_center_marker',
  'circle_start_marker',
  'circle_entry_marker',
  'circle_exit_marker',
  'known_time_gate',
  'dummy_branch_waypoint',
]);

const CIRCLE_STANDALONE_TYPES = new Set<RoutePoint['type']>([
  'circle_center',
  'circle_start',
  'circle_entry',
  'circle_exit',
]);

export type ParsedRouteEditorData = {
  routePoints: RoutePoint[];
  standalonePoints: RoutePoint[];
  gates: Gate[];
  observationMarkers: ObservationMarker[];
  polygons: Polygon[];
  bounds: [[number, number], [number, number]] | null;
};

export function createStandalonePointTypeSet(_isCircleStandaloneTask: boolean): Set<RoutePoint['type']> {
  // 'timed_turnpoint' is the free-map (standalone) flavor of a timed point,
  // distinct from 'known_time_gate' which is inserted directly on a route
  // backbone (2.A1). Both share featureType 'known_time_gate' for backend
  // compilation, but need different pointType values here so parsing can
  // tell them apart and bucket each into the right lane.
  const types = new Set<RoutePoint['type']>(['catalogue_turnpoint', 'dummy', 'timed_turnpoint']);
  CIRCLE_STANDALONE_TYPES.forEach((type) => types.add(type));
  return types;
}

export function parseRouteEditorFeatureCollection(
  json: any,
  standalonePointTypes: Set<RoutePoint['type']>,
): ParsedRouteEditorData {
  const emptyResult: ParsedRouteEditorData = {
    routePoints: [],
    standalonePoints: [],
    gates: [],
    observationMarkers: [],
    polygons: [],
    bounds: null,
  };

  if (json?.type !== 'FeatureCollection') {
    return emptyResult;
  }

  const features = Array.isArray(json.features) ? json.features : [];
  const routePoints: RoutePoint[] = [];
  const standalonePoints: RoutePoint[] = [];
  const gates: Gate[] = [];
  const observationMarkers: ObservationMarker[] = [];
  const polygons: Polygon[] = [];

  // Backend/frontend authored-route contract:
  // - featureType identifies the authored primitive lane
  // - route_waypoint primitives belong to the ordered backbone polyline
  // - catalogue/circle primitives stay in the standalone lane even though they
  //   are also Point features in the same GeoJSON payload
  const pointFeatures = features
    .filter((feature: any) => (
      feature?.geometry?.type === 'Point'
      && POINT_FEATURE_TYPES.has(feature?.properties?.featureType)
    ))
    .sort((a: any, b: any) => (a.properties?.sequence ?? 999999) - (b.properties?.sequence ?? 999999));

  pointFeatures.forEach((feature: any) => {
    const parsedPoint = {
      id: feature.properties?.id || crypto.randomUUID(),
      lat: feature.geometry.coordinates[1],
      lng: feature.geometry.coordinates[0],
      name: feature.properties?.name || 'Unnamed',
      type: feature.properties?.pointType || 'tp',
      featureType: feature.properties?.featureType || 'route_waypoint',
      segmentType: feature.properties?.segmentType || 'straight',
      controlLat: feature.properties?.controlLat,
      controlLng: feature.properties?.controlLng,
      width: feature.properties?.width || 1852,
      isTiming: typeof feature.properties?.isTiming === 'boolean' ? feature.properties.isTiming : true,
      isPassing: typeof feature.properties?.isPassing === 'boolean' ? feature.properties.isPassing : true,
      scoreValue: feature.properties?.scoreValue ?? null,
      unknownLegHeading: feature.properties?.unknownLegHeading,
      triggerPointId: feature.properties?.triggerPointId ?? null,
      branchSequence: feature.properties?.branchSequence ?? null,
    } as RoutePoint;

    if (standalonePointTypes.has(parsedPoint.type)) {
      standalonePoints.push(parsedPoint);
    } else {
      routePoints.push(parsedPoint);
    }
  });

  features
    .filter((feature: any) => feature?.geometry?.type === 'LineString' && feature?.properties?.gateType)
    .forEach((feature: any) => {
      gates.push({
        id: feature.properties?.id || crypto.randomUUID(),
        name: feature.properties?.name || 'Gate',
        type: feature.properties?.gateType,
        p1: { lng: feature.geometry.coordinates[0][0], lat: feature.geometry.coordinates[0][1] },
        p2: { lng: feature.geometry.coordinates[1][0], lat: feature.geometry.coordinates[1][1] },
        width: feature.properties?.width || 50,
      });
    });

  features
    .filter((feature: any) => feature?.geometry?.type === 'Point' && feature?.properties?.featureType === 'observation_photo')
    .forEach((feature: any) => {
      observationMarkers.push({
        id: feature.properties?.id || crypto.randomUUID(),
        lat: feature.geometry.coordinates[1],
        lng: feature.geometry.coordinates[0],
        name: feature.properties?.name || 'Obs',
        targetName: feature.properties?.targetName || '',
      });
    });

  features
    .filter((feature: any) => feature?.geometry?.type === 'Polygon' && (
      feature?.properties?.featureType === 'zone' || feature?.properties?.featureType === 'waypoint_polygon'
    ))
    .forEach((feature: any) => {
      const coords = [...(feature.geometry.coordinates?.[0] || [])];
      if (coords.length > 0 && coords[0][0] === coords[coords.length - 1][0] && coords[0][1] === coords[coords.length - 1][1]) {
        coords.pop();
      }
      const polygonType = feature.properties?.polygonType || 'prohibited';
      if (polygonType !== 'waypoint') {
        polygons.push({
          id: feature.properties?.id || crypto.randomUUID(),
          name: feature.properties?.name || 'Zone',
          type: polygonType as Polygon['type'],
          points: coords.map((coord: any) => ({ lng: coord[0], lat: coord[1] })),
        });
      }
    });

  const bounds = calculateFeatureBounds(routePoints, standalonePoints, gates, observationMarkers, polygons);

  return {
    routePoints,
    standalonePoints,
    gates,
    observationMarkers,
    polygons,
    bounds,
  };
}

function calculateFeatureBounds(
  routePoints: RoutePoint[],
  standalonePoints: RoutePoint[],
  gates: Gate[],
  observationMarkers: ObservationMarker[],
  polygons: Polygon[],
): [[number, number], [number, number]] | null {
  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLng = Infinity;
  let maxLng = -Infinity;
  let hasPoints = false;

  const extend = (lat: number, lng: number) => {
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
    if (lng < minLng) minLng = lng;
    if (lng > maxLng) maxLng = lng;
    hasPoints = true;
  };

  routePoints.forEach((point) => extend(point.lat, point.lng));
  standalonePoints.forEach((point) => extend(point.lat, point.lng));
  gates.forEach((gate) => {
    extend(gate.p1.lat, gate.p1.lng);
    extend(gate.p2.lat, gate.p2.lng);
  });
  observationMarkers.forEach((marker) => extend(marker.lat, marker.lng));
  polygons.forEach((polygon) => polygon.points.forEach((point) => extend(point.lat, point.lng)));

  return hasPoints ? [[minLat, minLng], [maxLat, maxLng]] : null;
}
