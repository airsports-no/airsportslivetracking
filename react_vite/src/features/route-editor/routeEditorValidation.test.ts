import { validateRouteEditorState, buildRouteEditorSavePayload } from './routeEditorValidation';
import type { RoutePoint, Gate, ObservationMarker, Polygon } from '../../types';

function makePoint(overrides: Partial<RoutePoint> & { id: string; type: RoutePoint['type'] }): RoutePoint {
  return {
    name: overrides.type.toUpperCase(),
    lat: 60,
    lng: 11,
    segmentType: 'straight',
    width: 1852,
    isTiming: false,
    isPassing: true,
    featureType: 'route_waypoint',
    ...overrides,
  };
}

const sp = makePoint({ id: '1', type: 'sp', name: 'SP', lat: 60, lng: 11 });
const tp = makePoint({ id: '2', type: 'tp', name: 'TP', lat: 60.1, lng: 11.1 });
const fp = makePoint({ id: '3', type: 'fp', name: 'FP', lat: 60.2, lng: 11.2 });

describe('validateRouteEditorState', () => {
  it('accepts a normal three-point backbone route with no errors', () => {
    expect(validateRouteEditorState([sp, tp, fp], false, false)).toEqual([]);
  });

  it('requires at least 2 backbone points for a non-standalone task', () => {
    expect(validateRouteEditorState([sp], false, false)).toContain('Route must have at least 2 backbone points.');
  });

  it('requires the first point to be sp and the last to be fp', () => {
    const errors = validateRouteEditorState([tp, tp, sp], false, false);
    expect(errors).toContain("First route backbone point must be type 'Start'.");
    expect(errors).toContain("Last route backbone point must be type 'Finish'.");
  });

  it('rejects sp/fp appearing in the middle of the route', () => {
    const errors = validateRouteEditorState([sp, sp, fp], false, false);
    expect(errors.some((e) => e.includes('cannot be Start (middle of route)'))).toBe(true);
  });

  it('requires exactly three points for a three-point-backbone task', () => {
    expect(validateRouteEditorState([sp, tp, tp, fp], true, false)).toContain(
      'This task requires exactly three route backbone points: SP, MP, and FP.',
    );
  });

  it('requires at least one curved leg for a curve-required task', () => {
    const errors = validateRouteEditorState([sp, tp, fp], false, false, false, true);
    expect(errors).toContain(
      '2.A1 requires at least one curved leg. Use the curve tool to add a curved segment between two route points.',
    );
  });

  it('does not require a curved leg when one is present', () => {
    const curvedTp = makePoint({ id: '2', type: 'tp', segmentType: 'curved' });
    const errors = validateRouteEditorState([sp, curvedTp, fp], false, false, false, true);
    expect(errors.some((e) => e.includes('curved leg'))).toBe(false);
  });

  it('rejects any route backbone points for a circle standalone task', () => {
    const errors = validateRouteEditorState([sp, fp], false, true);
    expect(errors).toContain('Circle tasks should not use a route backbone. Place all circle markers as standalone points.');
  });

  it('rejects any route backbone points for a timed-turnpoint standalone task', () => {
    const errors = validateRouteEditorState([sp, fp], false, false, true);
    expect(errors).toContain('This task requires no route backbone. Place the timed and catalogue turnpoints as standalone points.');
  });

  it('does not require sp/fp backbone shape at all for a standalone-only task with no points', () => {
    expect(validateRouteEditorState([], false, true)).toEqual([]);
  });

  it('rejects a secret point placed at the start or end', () => {
    const secretAtStart = makePoint({ id: '1', type: 'secret' });
    const errors = validateRouteEditorState([secretAtStart, tp, fp], false, false);
    expect(errors.some((e) => e.includes('cannot be Start or Finish'))).toBe(true);
  });

  it('rejects a secret point that is not collinear with its neighbors', () => {
    const offPathSecret = makePoint({ id: '2', type: 'secret', lat: 65, lng: 11.5 });
    const errors = validateRouteEditorState([sp, offPathSecret, fp], false, false);
    expect(errors.some((e) => e.includes('not on a straight line'))).toBe(true);
  });

  it('accepts a secret point that is collinear with its neighbors', () => {
    const collinearSecret = makePoint({ id: '2', type: 'secret', lat: 60.1, lng: 11.1 });
    const start = makePoint({ id: '1', type: 'sp', lat: 60, lng: 11 });
    const end = makePoint({ id: '3', type: 'fp', lat: 60.2, lng: 11.2 });
    const errors = validateRouteEditorState([start, collinearSecret, end], false, false);
    expect(errors.some((e) => e.includes('not on a straight line'))).toBe(false);
  });

  it('does not flag a secret point on a curved leg for collinearity', () => {
    const curvedSecret = makePoint({ id: '2', type: 'secret', lat: 65, lng: 11.5, segmentType: 'curved' });
    const errors = validateRouteEditorState([sp, curvedSecret, fp], false, false);
    expect(errors.some((e) => e.includes('not on a straight line'))).toBe(false);
  });

  it('applies the same collinearity/start-finish validation to a legacy hidden_gate point as a secret point', () => {
    const offPathHiddenGate = makePoint({ id: '2', type: 'hidden_gate', lat: 65, lng: 11.5 });
    const errors = validateRouteEditorState([sp, offPathHiddenGate, fp], false, false);
    expect(errors.some((e) => e.includes('not on a straight line'))).toBe(true);

    const hiddenGateAtStart = makePoint({ id: '1', type: 'hidden_gate' });
    const startErrors = validateRouteEditorState([hiddenGateAtStart, tp, fp], false, false);
    expect(startErrors.some((e) => e.includes('cannot be Start or Finish'))).toBe(true);
  });

  it('flags a turn too sharp for the corridor width relative to the previous leg', () => {
    // A very wide gate with a very short, sharply-angled leg forces the
    // computed miter length past the previous leg's own length.
    const start = makePoint({ id: '1', type: 'sp', lat: 60, lng: 11 });
    const sharpTurn = makePoint({ id: '2', type: 'tp', lat: 60.0001, lng: 11.0001, width: 50000 });
    const end = makePoint({ id: '3', type: 'fp', lat: 60.0002, lng: 11 });
    const errors = validateRouteEditorState([start, sharpTurn, end], false, false);
    expect(errors.some((e) => e.includes('turn is too sharp'))).toBe(true);
  });

  it('does not flag a gentle turn on generously-spaced legs', () => {
    const start = makePoint({ id: '1', type: 'sp', lat: 60, lng: 11, width: 100 });
    const turn = makePoint({ id: '2', type: 'tp', lat: 60.5, lng: 11.5, width: 100 });
    const end = makePoint({ id: '3', type: 'fp', lat: 61, lng: 11, width: 100 });
    const errors = validateRouteEditorState([start, turn, end], false, false);
    expect(errors.some((e) => e.includes('turn is'))).toBe(false);
  });

  it('skips sharp-turn checks for points whose name starts with "Curve"', () => {
    const start = makePoint({ id: '1', type: 'sp', lat: 60, lng: 11 });
    const sharpButCurve = makePoint({ id: '2', type: 'tp', name: 'Curve point', lat: 60.0001, lng: 11.0001, width: 50000 });
    const end = makePoint({ id: '3', type: 'fp', lat: 60.0002, lng: 11 });
    const errors = validateRouteEditorState([start, sharpButCurve, end], false, false);
    expect(errors.some((e) => e.includes('turn is'))).toBe(false);
  });
});

describe('buildRouteEditorSavePayload', () => {
  const gate: Gate = { id: 'g1', name: 'Takeoff 1', type: 'takeoff', p1: { lat: 60, lng: 11 }, p2: { lat: 60.001, lng: 11 }, width: 100 };
  const landingGate: Gate = { id: 'g2', name: 'Landing 1', type: 'landing', p1: { lat: 60, lng: 11.1 }, p2: { lat: 60.001, lng: 11.1 }, width: 100 };
  const observation: ObservationMarker = { id: 'o1', name: 'Obs 1', lat: 60.05, lng: 11.05, targetName: 'Target A' };
  const polygon: Polygon = { id: 'z1', name: 'Zone A', type: 'prohibited', points: [{ lat: 60, lng: 11 }, { lat: 60.1, lng: 11 }, { lat: 60.1, lng: 11.1 }] };
  const dummyBranch = makePoint({ id: '4', type: 'dummy', featureType: 'dummy_branch_waypoint', triggerPointId: '2', branchSequence: 0 });
  const catalogueTurnpoint = makePoint({ id: '5', type: 'catalogue_turnpoint', featureType: 'catalogue_turnpoint' });

  const basePayload = () =>
    buildRouteEditorSavePayload({
      routeName: 'Test route',
      routePoints: [sp, tp, fp],
      standalonePoints: [dummyBranch, catalogueTurnpoint],
      gates: [gate, landingGate],
      observationMarkers: [observation],
      polygons: [polygon],
      showCorridor: true,
      maxObsDist: 500,
      hideLabels: false,
      selectedTaskTemplateId: 'cima_a5',
    });

  it('sets the route name and settings verbatim', () => {
    const payload = basePayload();
    expect(payload.name).toBe('Test route');
    expect(payload.settings).toEqual({
      showCorridor: true,
      maxObsDist: 500,
      hideLabels: false,
      selectedTaskTemplateId: 'cima_a5',
    });
  });

  it('builds the route_path LineString from route points only, in order', () => {
    const payload = basePayload();
    const routePath = payload.route.features.find((f: any) => f.properties.featureType === 'route_path');
    expect(routePath.geometry.coordinates).toEqual([
      [11, 60],
      [11.1, 60.1],
      [11.2, 60.2],
    ]);
  });

  it('emits one route_waypoint feature per route point with a sequence index', () => {
    const payload = basePayload();
    const waypointFeatures = payload.route.features.filter((f: any) => f.properties.featureType === 'route_waypoint');
    expect(waypointFeatures.map((f: any) => f.properties.name)).toEqual(['SP', 'TP', 'FP']);
    expect(waypointFeatures.map((f: any) => f.properties.sequence)).toEqual([0, 1, 2]);
  });

  it('separates dummy-branch standalone points from other standalone points', () => {
    const payload = basePayload();
    const dummyFeature = payload.route.features.find((f: any) => f.properties.featureType === 'dummy_branch_waypoint');
    const catalogueFeature = payload.route.features.find((f: any) => f.properties.featureType === 'catalogue_turnpoint');
    expect(dummyFeature.properties.triggerPointId).toBe('2');
    expect(dummyFeature.properties.branchSequence).toBe(0);
    expect(catalogueFeature).toBeTruthy();
    expect(catalogueFeature.properties.triggerPointId).toBeUndefined();
  });

  it('maps gate type "landing" to featureType landing_gate and anything else to takeoff_gate', () => {
    const payload = basePayload();
    const gateFeatures = payload.route.features.filter((f: any) => f.geometry.type === 'LineString' && f.properties.gateType);
    const byName = Object.fromEntries(gateFeatures.map((f: any) => [f.properties.name, f.properties.featureType]));
    expect(byName['Takeoff 1']).toBe('takeoff_gate');
    expect(byName['Landing 1']).toBe('landing_gate');
  });

  it('emits observation_photo features with lng/lat coordinate order', () => {
    const payload = basePayload();
    const observationFeature = payload.route.features.find((f: any) => f.properties.featureType === 'observation_photo');
    expect(observationFeature.geometry.coordinates).toEqual([11.05, 60.05]);
    expect(observationFeature.properties.targetName).toBe('Target A');
  });

  it('closes the polygon ring by repeating the first point at the end', () => {
    const payload = basePayload();
    const zoneFeature = payload.route.features.find((f: any) => f.properties.featureType === 'zone');
    const coordinates = zoneFeature.geometry.coordinates[0];
    expect(coordinates[0]).toEqual(coordinates[coordinates.length - 1]);
    expect(coordinates).toHaveLength(polygon.points.length + 1);
  });
});
