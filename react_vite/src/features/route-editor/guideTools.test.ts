import { ROUTE_REQUIREMENT_TOOLS, type RouteRequirementTool } from './api';
import { countForTool, countTimedTurnPoints, getToolAction, getToolWizardStep, TOOL_ACTIONS, type RouteContent } from './guideTools';
import { getWizardTransition } from './routeEditorWizardTransitions';
import type { RoutePoint } from '../../types';

const point = (id: string, type: RoutePoint['type'], overrides: Partial<RoutePoint> = {}): RoutePoint => ({
  id,
  name: id,
  type,
  lat: 60,
  lng: 11,
  width: 1852,
  isTiming: false,
  isPassing: true,
  segmentType: 'straight',
  featureType: 'route_waypoint',
  ...overrides,
});

const EMPTY: RouteContent = { routePoints: [], standalonePoints: [], gates: [], observationMarkers: [], polygons: [] };

const transitionOf = (tool: RouteRequirementTool) => {
  const step = getToolWizardStep(tool, 'Label', 'Help');
  return step ? getWizardTransition(step, () => 'prompt') : null;
};

describe('tool actions', () => {
  it('handle every tool name the API can return', () => {
    expect(Object.keys(TOOL_ACTIONS).sort()).toEqual([...ROUTE_REQUIREMENT_TOOLS].sort());
    for (const tool of ROUTE_REQUIREMENT_TOOLS) {
      const action = getToolAction(tool);
      expect(action.buttonLabel, tool).toBeTruthy();
      expect(action.shortLabel, tool).toBeTruthy();
      expect(action.prompt, tool).toBeTruthy();
    }
  });

  it.each([
    ['route_waypoint', 'add_point'],
    ['hidden_gate', 'view'],
    ['known_time_gate', 'add_point'],
    ['catalogue_turnpoint', 'add_catalogue_turnpoint'],
    ['circle_start', 'add_point'],
    ['circle_center', 'add_point'],
    ['circle_entry', 'add_point'],
    ['circle_exit', 'add_point'],
    ['photo', 'add_observation'],
    ['landing_area', 'add_polygon'],
    ['takeoff_gate', 'add_takeoff'],
    ['landing_gate', 'add_landing'],
    ['unknown_leg_point', 'view'],
    ['extension_waypoint', 'add_point'],
  ] as const)('starts %s in the editor mode %s', (tool, mode) => {
    expect(transitionOf(tool)?.mode).toBe(mode);
  });

  it('inserts hidden gates on the clicked leg as secret points, as the leg-insert type', () => {
    const transition = transitionOf('hidden_gate')!;
    expect(transition.wizardRouteInsertType).toBe('secret');
    expect(transition.routeInsertPrompt).toBe('prompt');
  });

  it('places a known time gate as a free-map timed turn point', () => {
    const transition = transitionOf('known_time_gate')!;
    expect(transition.wizardRouteInsertType).toBe('timed_turnpoint');
    expect(transition.wizardRouteInsertFeatureType).toBe('known_time_gate');
  });

  it('places the circle markers as free-map points of their own type', () => {
    expect(transitionOf('circle_exit')).toMatchObject({ wizardRouteInsertType: 'circle_exit', wizardRouteInsertFeatureType: 'circle_exit_marker' });
  });

  it('makes the unknown-leg point a selection of an existing route point', () => {
    expect(transitionOf('unknown_leg_point')).toMatchObject({ selectExistingRouteType: 'ul', nextSelectionType: 'point' });
  });

  it('draws the landing area as the duration landing area polygon', () => {
    expect(transitionOf('landing_area')?.wizardPolygonType).toBe('duration_landing_area');
  });

  it('has no placing tool for the curved leg: nothing to start, the help is shown instead', () => {
    expect(getToolWizardStep('curved_leg', 'Curved legs', 'Help')).toBeNull();
    expect(getToolAction('curved_leg').buttonLabel).toBe('How');
    const others = ROUTE_REQUIREMENT_TOOLS.filter((tool) => tool !== 'curved_leg');
    expect(others.every((tool) => getToolWizardStep(tool, 'L', 'H') !== null)).toBe(true);
  });

  it('ends a polygon or a gate by itself, nothing else', () => {
    const singleShot = ROUTE_REQUIREMENT_TOOLS.filter((tool) => TOOL_ACTIONS[tool].singleShot);
    expect(singleShot.sort()).toEqual(['landing_area', 'landing_gate', 'takeoff_gate']);
  });
});

describe('countForTool', () => {
  const content: RouteContent = {
    ...EMPTY,
    routePoints: [
      point('sp', 'sp'),
      point('ul1', 'ul', { segmentType: 'curved', controlLat: 60.1, controlLng: 11.1 }),
      point('ul2', 'ul'),
      point('hg', 'secret'),
      point('fp', 'fp'),
    ],
    standalonePoints: [
      point('cp1', 'timed_turnpoint', { featureType: 'known_time_gate' }),
      point('cat', 'catalogue_turnpoint', { featureType: 'catalogue_turnpoint' }),
      point('d1', 'dummy', { featureType: 'dummy_branch_waypoint', triggerPointId: 'ul1' }),
      point('cs', 'circle_start', { featureType: 'circle_start_marker' }),
    ],
    gates: [{ id: 'g', name: 'g', type: 'takeoff', p1: { lat: 0, lng: 0 }, p2: { lat: 0, lng: 0 }, width: 1 }],
    observationMarkers: [{ id: 'o' } as never],
    polygons: [{ id: 'p', name: 'p', type: 'duration_landing_area', points: [] }],
  };

  it('counts only timed turn points as the known time gates of a known circuit', () => {
    expect(countTimedTurnPoints({ ...EMPTY, routePoints: [
      point('sp', 'sp'), point('t1', 'tp', { isTiming: true }), point('t2', 'tp', { isTiming: false }), point('hg', 'secret'), point('fp', 'fp'),
    ] })).toBe(1);
  });

  it('counts what each tool places', () => {
    expect(countForTool('route_waypoint', content)).toBe(5);
    expect(countForTool('hidden_gate', content)).toBe(1);
    expect(countForTool('known_time_gate', content)).toBe(1);
    expect(countForTool('catalogue_turnpoint', content)).toBe(1);
    expect(countForTool('circle_start', content)).toBe(1);
    expect(countForTool('circle_center', content)).toBe(0);
    expect(countForTool('photo', content)).toBe(1);
    expect(countForTool('landing_area', content)).toBe(1);
    expect(countForTool('takeoff_gate', content)).toBe(1);
    expect(countForTool('landing_gate', content)).toBe(0);
    expect(countForTool('unknown_leg_point', content)).toBe(2);
    expect(countForTool('curved_leg', content)).toBe(1);
  });

  it('counts a curve split by a hidden gate as one curved leg', () => {
    const curved = (id: string, type: RoutePoint['type'], lat: number): RoutePoint => (
      point(id, type, { lat, lng: 11, segmentType: 'curved', controlLat: lat + 0.01, controlLng: 11.05 })
    );
    const split: RouteContent = {
      ...EMPTY,
      routePoints: [point('sp', 'sp'), curved('hg', 'secret', 60.1), curved('fp', 'fp', 60.2)],
    };
    expect(countForTool('curved_leg', split)).toBe(1);
    expect(countForTool('hidden_gate', split)).toBe(1);
  });

  it('counts the unknown-leg points that still lack an extension waypoint for the extension step', () => {
    expect(countForTool('extension_waypoint', content)).toBe(1);
    expect(countForTool('extension_waypoint', EMPTY)).toBe(0);
  });

  it('counts every tool as zero for an empty route', () => {
    for (const tool of ROUTE_REQUIREMENT_TOOLS) expect(countForTool(tool, EMPTY), tool).toBe(0);
  });
});
