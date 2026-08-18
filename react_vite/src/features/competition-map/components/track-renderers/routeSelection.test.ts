import { getUnknownLegHiddenStretchNames, buildUnknownLegRouteDataFromTargets, getRenderedRoute, getRenderedCatalogueTargets } from './routeSelection';
import type { Contestant, NavigationTaskCatalogueTarget, RouteData, Waypoint } from '../../types';

// This file locks in the decision logic behind "the live map always shows
// the contestant's declared route when a contestant is selected" (and the
// generic base route otherwise) - see the route-flow review that motivated
// extracting this module. Every expected value below is derived from
// reading the implementation, not from running it and copying the output.

function makeWaypoint(overrides: Partial<Waypoint> & { name: string; type: string }): Waypoint {
  return {
    latitude: 60,
    longitude: 11,
    elevation: 0,
    width: 0,
    gate_line: [],
    gate_line_extended: [],
    time_check: false,
    gate_check: false,
    end_curved: false,
    distance_next: 0,
    distance_previous: 0,
    bearing_next: 0,
    bearing_from_previous: 0,
    is_procedure_turn: false,
    ...overrides,
  };
}

function makeRoute(waypoints: Waypoint[]): RouteData {
  return {
    id: 1,
    name: 'Base task route',
    use_procedure_turns: false,
    rounded_corners: false,
    corridor_width: 0,
    waypoints,
    takeoff_gates: [],
    landing_gates: [],
    prohibited_set: [],
    photo_set: [],
  };
}

function makeContestant(id: number, compiled_effective_route_payload?: Record<string, any>): Contestant {
  return {
    id,
    contest_id: 1,
    compiled_effective_route_payload,
    team: {} as Contestant['team'],
    contestanttrack: {} as Contestant['contestanttrack'],
    contestant_number: id,
    track_version: 1,
    score_version: 1,
    air_speed: 100,
    wind_speed: 0,
    wind_direction: 0,
    navigation_task: {} as Contestant['navigation_task'],
    takeoff_time: '',
    tracker_start_time: '',
    finished_by_time: '',
    has_crossed_starting_line: false,
  };
}

describe('getUnknownLegHiddenStretchNames', () => {
  it('returns an empty set when the route has no unknown-leg waypoint', () => {
    const route = makeRoute([makeWaypoint({ name: 'SP', type: 'sp' }), makeWaypoint({ name: 'FP', type: 'fp' })]);
    expect(getUnknownLegHiddenStretchNames(route)).toEqual(new Set());
  });

  it('returns an empty set when a ul waypoint is immediately followed by a closing type', () => {
    const route = makeRoute([
      makeWaypoint({ name: 'SP', type: 'sp' }),
      makeWaypoint({ name: 'TRG1', type: 'ul' }),
      makeWaypoint({ name: 'FP', type: 'fp' }),
    ]);
    expect(getUnknownLegHiddenStretchNames(route)).toEqual(new Set());
  });

  it('collects every hidden_gate/secret waypoint between a ul and the next closing waypoint', () => {
    const route = makeRoute([
      makeWaypoint({ name: 'SP', type: 'sp' }),
      makeWaypoint({ name: 'TRG1', type: 'ul' }),
      makeWaypoint({ name: 'HG1', type: 'hidden_gate' }),
      makeWaypoint({ name: 'SEC1', type: 'secret' }),
      makeWaypoint({ name: 'FP', type: 'fp' }),
    ]);
    expect(getUnknownLegHiddenStretchNames(route)).toEqual(new Set(['HG1', 'SEC1']));
  });

  it('closes the hidden stretch on isp/ifp/tp too, not just sp/fp', () => {
    const route = makeRoute([
      makeWaypoint({ name: 'TRG1', type: 'ul' }),
      makeWaypoint({ name: 'HG1', type: 'hidden_gate' }),
      makeWaypoint({ name: 'TP1', type: 'tp' }),
      makeWaypoint({ name: 'HG2', type: 'hidden_gate' }), // outside any open stretch, must be ignored
    ]);
    expect(getUnknownLegHiddenStretchNames(route)).toEqual(new Set(['HG1']));
  });
});

describe('getRenderedRoute', () => {
  const baseRoute = makeRoute([makeWaypoint({ name: 'SP', type: 'sp' }), makeWaypoint({ name: 'MP', type: 'tp' }), makeWaypoint({ name: 'FP', type: 'fp' })]);

  it('returns the base route unchanged when no contestant is selected', () => {
    const result = getRenderedRoute(baseRoute, [], {}, null, false, false);
    expect(result).toBe(baseRoute);
  });

  it('substitutes actual_route.waypoints when present, even if effective_waypoints also exist', () => {
    const actualWaypoints = [makeWaypoint({ name: 'SP', type: 'sp' }), makeWaypoint({ name: 'TP1', type: 'tp' }), makeWaypoint({ name: 'FP', type: 'fp' })];
    const effectiveWaypoints = [makeWaypoint({ name: 'SP', type: 'sp' })];
    const contestant = makeContestant(1, { actual_route: { waypoints: actualWaypoints }, effective_waypoints: effectiveWaypoints });
    const result = getRenderedRoute(baseRoute, [], { 1: contestant }, 1, false, false);
    expect(result.waypoints).toBe(actualWaypoints);
    expect(result.waypoints.map((w) => w.name)).toEqual(['SP', 'TP1', 'FP']);
  });

  it('substitutes effective_waypoints when actual_route is absent', () => {
    const effectiveWaypoints = [
      makeWaypoint({ name: 'SP', type: 'sp' }),
      makeWaypoint({ name: 'TP1', type: 'tp' }),
      makeWaypoint({ name: 'TP2', type: 'tp' }),
      makeWaypoint({ name: 'FP', type: 'fp' }),
    ];
    const contestant = makeContestant(1, { effective_waypoints: effectiveWaypoints });
    const result = getRenderedRoute(baseRoute, [], { 1: contestant }, 1, false, false);
    expect(result.waypoints).toBe(effectiveWaypoints);
  });

  it('falls back to the base route when the contestant has an empty/missing declaration payload', () => {
    const contestant = makeContestant(1, {});
    const result = getRenderedRoute(baseRoute, [], { 1: contestant }, 1, false, false);
    expect(result).toBe(baseRoute);
  });

  it('falls back to the base route when the selected contestant is not in the contestants map', () => {
    const result = getRenderedRoute(baseRoute, [], {}, 999, false, false);
    expect(result).toBe(baseRoute);
  });

  it('uses the catalogue-derived visible route for an unknown-legs task with secrets hidden', () => {
    const unknownLegsRoute = makeRoute([makeWaypoint({ name: 'SP', type: 'sp' }), makeWaypoint({ name: 'TRG1', type: 'ul' }), makeWaypoint({ name: 'FP', type: 'fp' })]);
    const targets: NavigationTaskCatalogueTarget[] = [
      { name: 'SP', coordinates: [11, 60], kind: 'catalogue_turnpoint', segment_name: 'segment_1' },
      { name: 'B', coordinates: [11.5, 60.5], kind: 'catalogue_turnpoint', segment_name: 'segment_2' },
    ];
    // navTaskDisplaySecrets=true but displaySecrets=false -> canSeeSecrets is false, so the
    // catalogue-built visible route (not the raw declared/base route) must be used.
    const result = getRenderedRoute(unknownLegsRoute, targets, {}, null, true, false);
    expect(result.name).toBe('Unknown legs visible route');
    expect(result.waypoints.map((w) => w.name)).toEqual(['SP', 'B']);
  });

  it('does NOT use the catalogue-derived route for an unknown-legs task when secrets are visible', () => {
    const unknownLegsRoute = makeRoute([makeWaypoint({ name: 'SP', type: 'sp' }), makeWaypoint({ name: 'TRG1', type: 'ul' }), makeWaypoint({ name: 'FP', type: 'fp' })]);
    const targets: NavigationTaskCatalogueTarget[] = [{ name: 'SP', coordinates: [11, 60], kind: 'catalogue_turnpoint', segment_name: 'segment_1' }];
    const result = getRenderedRoute(unknownLegsRoute, targets, {}, null, true, true);
    expect(result).toBe(unknownLegsRoute);
  });
});

describe('buildUnknownLegRouteDataFromTargets', () => {
  it('returns null when there are no segment-tagged catalogue_turnpoint targets', () => {
    expect(buildUnknownLegRouteDataFromTargets([])).toBeNull();
    expect(buildUnknownLegRouteDataFromTargets([{ name: 'A', coordinates: [11, 60], kind: 'hidden_gate' }])).toBeNull();
  });

  it('excludes hidden-gate and hidden-stretch names, orders segments alphabetically', () => {
    const targets: NavigationTaskCatalogueTarget[] = [
      { name: 'B1', coordinates: [11.1, 60.1], kind: 'catalogue_turnpoint', segment_name: 'segment_2' },
      { name: 'A1', coordinates: [11.0, 60.0], kind: 'catalogue_turnpoint', segment_name: 'segment_1' },
      { name: 'HIDDEN', coordinates: [11.2, 60.2], kind: 'catalogue_turnpoint', segment_name: 'segment_1' },
      { name: 'HIDDEN', coordinates: [11.2, 60.2], kind: 'hidden_gate' },
    ];
    const result = buildUnknownLegRouteDataFromTargets(targets);
    expect(result).not.toBeNull();
    expect(result!.waypoints.map((w) => w.name)).toEqual(['A1', 'B1']);
  });
});

describe('getRenderedCatalogueTargets', () => {
  const baseRoute = makeRoute([makeWaypoint({ name: 'SP', type: 'sp' })]);
  const targets: NavigationTaskCatalogueTarget[] = [{ name: 'TP1', coordinates: [11, 60], kind: 'catalogue_turnpoint' }];

  it('returns an empty array with no contestant selected on a contract-navigation task (2.A3 general view)', () => {
    const result = getRenderedCatalogueTargets(targets, baseRoute, {}, null, false, false, 'contract_navigation_time_controls');
    expect(result).toEqual([]);
  });

  it('passes targets through unchanged with no contestant selected on other subtypes', () => {
    const result = getRenderedCatalogueTargets(targets, baseRoute, {}, null, false, false, 'turnpoint_hunt');
    expect(result).toBe(targets);
  });

  it('passes targets through unchanged with no contestant selected and no subtype given', () => {
    const result = getRenderedCatalogueTargets(targets, baseRoute, {}, null, false, false);
    expect(result).toBe(targets);
  });

  it('passes targets through when the contestant payload is unknown_legs_split', () => {
    const contestant = makeContestant(1, { map_rendering_mode: 'unknown_legs_split', effective_waypoints: [makeWaypoint({ name: 'X', type: 'tp' })] });
    const result = getRenderedCatalogueTargets(targets, baseRoute, { 1: contestant }, 1, false, false);
    expect(result).toBe(targets);
  });

  it('hides the catalogue overlay when the contestant has a non-empty declared effective route', () => {
    const contestant = makeContestant(1, { effective_waypoints: [makeWaypoint({ name: 'SP', type: 'sp' }), makeWaypoint({ name: 'FP', type: 'fp' })] });
    const result = getRenderedCatalogueTargets(targets, baseRoute, { 1: contestant }, 1, false, false);
    expect(result).toEqual([]);
  });

  it('falls back to showing the catalogue targets when the contestant has no declared effective route', () => {
    const contestant = makeContestant(1, {});
    const result = getRenderedCatalogueTargets(targets, baseRoute, { 1: contestant }, 1, false, false);
    expect(result).toBe(targets);
  });

  // Documents current behavior rather than asserting it's correct - see
  // routeSelection.ts's comment above `shape`. The isUnknownLegsSplit early
  // return above guarantees payload.map_rendering_mode is never
  // 'unknown_legs_split' by the time `shape` is computed here, so `shape`
  // is always null and this branch never actually returns via the `shape`
  // check - reaching this test point means the flow fell through to the
  // effective_waypoints/fallback checks instead, not the `shape` branch.
  it('never actually uses the actualRouteWaypoints+shape branch (dead code)', () => {
    const contestant = makeContestant(1, {
      actual_route: { waypoints: [] }, // present but empty, so actualRouteWaypoints.length is 0 - shape is null either way
      map_rendering_mode: 'not_unknown_legs_split',
    });
    const result = getRenderedCatalogueTargets(targets, baseRoute, { 1: contestant }, 1, false, false);
    // Falls through to the final "no declared effective route" case, not the dead shape branch.
    expect(result).toBe(targets);
  });
});
