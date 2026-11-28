import type { RoutePoint } from '../../types';
import {
  createInsertedRoutePoint,
  createObservationMarker,
  findNearestHit,
  findPlacingModeHit,
  HIT_RADIUS_PX,
  hitKindsForMode,
  insertOnCurvedLeg,
  legClickAction,
  legInsertTypeFor,
  CURVED_LEG_HIDDEN_GATE_NOTICE,
  nextObservationName,
  type HitCandidate,
} from './routeEditorMapClickHelpers';

describe('createInsertedRoutePoint', () => {
  it('defaults isTiming to true for a tp point (the known_time_gate collapse target)', () => {
    const point = createInsertedRoutePoint({ lat: 60, lng: 11 }, 'tp', 'route_waypoint', null, 1);
    expect(point.isTiming).toBe(true);
  });

  it('defaults isTiming to true for a secret gate: it is checked and timed like any other', () => {
    const point = createInsertedRoutePoint({ lat: 60, lng: 11 }, 'secret', 'route_waypoint', null, 1);
    expect([point.isTiming, point.isPassing]).toEqual([true, true]);
  });

  it('defaults isTiming to false for other route-insert pointTypes, e.g. a dummy point', () => {
    const point = createInsertedRoutePoint({ lat: 60, lng: 11 }, 'dummy', 'route_waypoint', null, 1);
    expect(point.isTiming).toBe(false);
  });
});

describe('nextObservationName', () => {
  it('starts at Obs 1 and counts on', () => {
    expect(nextObservationName([])).toBe('Obs 1');
    expect(nextObservationName(['Obs 1', 'Obs 2'])).toBe('Obs 3');
  });

  it('takes the first name that is free after a marker was deleted, instead of one that is in use', () => {
    // Obs 2 was deleted from Obs 1 to Obs 3: the old "number of markers + 1" would have given a second Obs 3
    expect(nextObservationName(['Obs 1', 'Obs 3'])).toBe('Obs 2');
    expect(nextObservationName(['Obs 2', 'Obs 3'])).toBe('Obs 1');
  });
});

describe('createObservationMarker', () => {
  it('is named by the names in use', () => {
    const marker = createObservationMarker({ lat: 60, lng: 11 }, ['Obs 1', 'Obs 3']);
    expect(marker.name).toBe('Obs 2');
    expect([marker.lat, marker.lng]).toEqual([60, 11]);
  });
});

describe('which existing thing a click hits', () => {
  const point = (key: string, x: number, y: number, kind: HitCandidate['kind'] = 'point'): HitCandidate => ({ key, kind, x, y });

  it('has a hit radius of at least 14 pixels', () => {
    expect(HIT_RADIUS_PX).toBeGreaterThanOrEqual(14);
  });

  it('hits a candidate within the radius and not one outside it', () => {
    const candidates = [point('a', 100, 100)];
    expect(findNearestHit({ x: 100 + HIT_RADIUS_PX, y: 100 }, candidates)?.key).toBe('a');
    expect(findNearestHit({ x: 100 + HIT_RADIUS_PX + 1, y: 100 }, candidates)).toBeNull();
    expect(findNearestHit({ x: 0, y: 0 }, [])).toBeNull();
  });

  it('lets the nearest of overlapping hit areas win', () => {
    const candidates = [point('far', 100, 100), point('near', 112, 100)];
    expect(findNearestHit({ x: 108, y: 100 }, candidates)?.key).toBe('near');
    expect(findNearestHit({ x: 104, y: 100 }, candidates)?.key).toBe('far');
  });

  it('picks the first on an exact tie', () => {
    expect(findNearestHit({ x: 106, y: 100 }, [point('a', 100, 100), point('b', 112, 100)])?.key).toBe('a');
  });

  it('selects an existing point instead of placing one only for the kind the mode places', () => {
    const candidates = [
      point('route', 100, 100, 'point'),
      point('standalone', 200, 100, 'standalone_point'),
      point('photo', 300, 100, 'observation'),
      point('gate', 400, 100, 'gate'),
      point('first', 500, 100, 'temp_polygon_start'),
    ];
    expect(findPlacingModeHit({ x: 105, y: 100 }, candidates, 'add_point')?.key).toBe('route');
    expect(findPlacingModeHit({ x: 205, y: 100 }, candidates, 'add_point')?.key).toBe('standalone');
    expect(findPlacingModeHit({ x: 105, y: 100 }, candidates, 'add_observation')).toBeNull();
    expect(findPlacingModeHit({ x: 205, y: 100 }, candidates, 'add_catalogue_turnpoint')?.key).toBe('standalone');
    expect(findPlacingModeHit({ x: 305, y: 100 }, candidates, 'add_observation')?.key).toBe('photo');
    expect(findPlacingModeHit({ x: 405, y: 100 }, candidates, 'add_landing')?.key).toBe('gate');
    expect(findPlacingModeHit({ x: 405, y: 100 }, candidates, 'add_takeoff')?.key).toBe('gate');
    expect(findPlacingModeHit({ x: 505, y: 100 }, candidates, 'add_polygon')?.key).toBe('first');
  });

  it('never hits in select mode: the marks do that themselves', () => {
    expect(hitKindsForMode('view')).toEqual([]);
    expect(findPlacingModeHit({ x: 100, y: 100 }, [point('a', 100, 100)], 'view')).toBeNull();
  });
});

describe('a click on a leg', () => {
  const route = (curved = false) => [
    { id: 'a', name: 'SP', lat: 60, lng: 11, type: 'sp', segmentType: 'straight', width: 1852, isTiming: true, isPassing: true },
    { id: 'b', name: 'FP', lat: 60, lng: 11.2, type: 'fp', segmentType: curved ? 'curved' : 'straight', controlLat: 60.05, controlLng: 11.1, width: 1852, isTiming: true, isPassing: true },
  ] as RoutePoint[];
  const click = { lat: 60.0001, lng: 11.1 };

  it('inserts nothing in select mode', () => {
    expect(legClickAction(route(), click, legInsertTypeFor('view', null))).toEqual({ kind: 'none' });
  });

  it('inserts a hidden gate on the leg with the hidden gate tool, or a guide step that asks for one', () => {
    for (const type of [legInsertTypeFor('add_hidden_gate', null), legInsertTypeFor('view', 'secret')]) {
      const action = legClickAction(route(), click, type);
      expect(action.kind).toBe('insert');
      if (action.kind !== 'insert') continue;
      expect(action.index).toBe(1);
      expect(action.point.type).toBe('secret');
      expect(action.point.lng).toBeCloseTo(11.1, 3);
      expect(action.point.lat).toBeCloseTo(60, 3);
    }
  });

  it('tells a curved leg is not supported yet instead of inserting', () => {
    const action = legClickAction(route(true), { lat: 60.025, lng: 11.1 }, 'secret');
    expect(action).toEqual(insertOnCurvedLeg());
    expect(action).toEqual({ kind: 'unsupported', message: CURVED_LEG_HIDDEN_GATE_NOTICE });
    expect(CURVED_LEG_HIDDEN_GATE_NOTICE).toBe('Hidden gates on curved legs are not supported yet');
  });
});
