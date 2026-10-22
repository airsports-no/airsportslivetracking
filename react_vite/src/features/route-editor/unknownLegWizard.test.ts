import type { RoutePoint } from '../../types';
import {
  buildDummyBranchWaypoint,
  getDummyBranchPhase,
  getWizardBannerText,
  nameUnknownLegsRoutePoints,
  previousOnDummyBranch,
} from './unknownLegWizard';

const makeRoutePoint = (overrides: Partial<RoutePoint> = {}): RoutePoint => ({
  id: 'point-1',
  name: 'WP1',
  type: 'tp' as RoutePoint['type'],
  featureType: 'route_waypoint' as NonNullable<RoutePoint['featureType']>,
  lat: 60,
  lng: 11,
  width: 1852,
  isTiming: false,
  isPassing: true,
  segmentType: 'straight' as RoutePoint['segmentType'],
  ...overrides,
});

describe('getDummyBranchPhase', () => {
  it('returns idle when the step is not active', () => {
    expect(getDummyBranchPhase(false, null, [])).toBe('idle');
  });

  it('returns awaiting_trigger when the step is active without a selected trigger', () => {
    expect(getDummyBranchPhase(true, null, [makeRoutePoint({ type: 'ul' as RoutePoint['type'] })])).toBe('awaiting_trigger');
  });

  it('returns placing when the active trigger resolves to an unknown-leg trigger point', () => {
    const trigger = makeRoutePoint({ id: 'trigger-1', type: 'ul' as RoutePoint['type'], name: 'WP3' });
    expect(getDummyBranchPhase(true, trigger.id, [trigger])).toBe('placing');
  });

  it('returns awaiting_trigger when the trigger id no longer resolves to an unknown-leg trigger', () => {
    const nonTrigger = makeRoutePoint({ id: 'point-2', type: 'tp' as RoutePoint['type'] });
    expect(getDummyBranchPhase(true, nonTrigger.id, [nonTrigger])).toBe('awaiting_trigger');
    expect(getDummyBranchPhase(true, 'missing', [nonTrigger])).toBe('awaiting_trigger');
  });
});

describe('getWizardBannerText', () => {
  it('returns awaiting-trigger copy', () => {
    expect(getWizardBannerText('awaiting_trigger')).toEqual({
      title: 'Select an unknown-leg trigger',
      instruction: 'Click an unknown-leg trigger on the map (amber) to start placing dummy waypoints.',
    });
  });

  it('returns placing copy with the trigger name', () => {
    expect(getWizardBannerText('placing', 'WP3')).toEqual({
      title: 'Placing dummy waypoints for WP3',
      instruction: 'Click the map for each dummy waypoint on this branch.',
    });
  });

  it('returns idle copy when no step is active', () => {
    expect(getWizardBannerText('idle')).toEqual({
      title: 'No active unknown-leg step',
      instruction: 'Start the unknown-leg wizard step to select a trigger and place dummy waypoints.',
    });
  });
});

describe('buildDummyBranchWaypoint', () => {
  const trigger = makeRoutePoint({ id: 'trigger-1', type: 'ul' as RoutePoint['type'], name: 'WP3' });

  it('builds the first dummy waypoint with the expected defaults', () => {
    const point = buildDummyBranchWaypoint({ lat: 60.1, lng: 11.1 }, trigger, []);
    expect(point.name).toBe('WP3-D1');
    expect(point.branchSequence).toBe(0);
    expect(point.triggerPointId).toBe('trigger-1');
    expect(point.isTiming).toBe(false);
    expect(point.isPassing).toBe(true);
  });

  it('increments the name and sequence for the second dummy waypoint', () => {
    const existing = [
      makeRoutePoint({ id: 'dummy-1', type: 'dummy' as RoutePoint['type'], featureType: 'dummy_branch_waypoint', triggerPointId: 'trigger-1', branchSequence: 0 }),
    ];
    const point = buildDummyBranchWaypoint({ lat: 60.2, lng: 11.2 }, trigger, existing);
    expect(point.name).toBe('WP3-D2');
    expect(point.branchSequence).toBe(1);
  });

  it('keeps counting for later dummy waypoints', () => {
    const existing = Array.from({ length: 4 }, (_, index) => makeRoutePoint({
      id: `dummy-${index + 1}`,
      type: 'dummy' as RoutePoint['type'],
      name: `WP3-D${index + 1}`,
      featureType: 'dummy_branch_waypoint',
      triggerPointId: 'trigger-1',
      branchSequence: index,
    }));
    const point = buildDummyBranchWaypoint({ lat: 60.3, lng: 11.3 }, trigger, existing);
    expect(point.name).toBe('WP3-D5');
    expect(point.branchSequence).toBe(4);
  });
});

describe('nameUnknownLegsRoutePoints', () => {
  const backbone = () => [
    makeRoutePoint({ id: 'sp', name: 'SP', type: 'sp' }),
    makeRoutePoint({ id: 'ul-a', name: 'WP 2', type: 'ul' }),
    makeRoutePoint({ id: 'secret-a', name: 'Secret 6', type: 'secret' }),
    makeRoutePoint({ id: 'tp-a', name: 'WP 3' }),
    makeRoutePoint({ id: 'ul-b', name: 'WP 4', type: 'ul' }),
    makeRoutePoint({ id: 'tp-b', name: 'WP 5' }),
    makeRoutePoint({ id: 'fp', name: 'FP', type: 'fp' }),
  ];
  const dummy = (id: string, triggerPointId: string, branchSequence: number, name: string) =>
    makeRoutePoint({ id, name, type: 'dummy', featureType: 'dummy_branch_waypoint', triggerPointId, branchSequence });

  it('numbers the shown points in map order, with each trigger\'s dummies right after it', () => {
    const named = nameUnknownLegsRoutePoints(backbone(), [
      dummy('d-b1', 'ul-b', 0, 'WP 4-D1'),
      dummy('d-a2', 'ul-a', 1, 'WP 2-D2'),
      dummy('d-a1', 'ul-a', 0, 'WP 2-D1'),
    ]);

    expect(named.routePoints.map((point) => point.name)).toEqual([
      'SP',
      'Unknown leg 1',
      'Secret 6',
      'TP 3',
      'Unknown leg 2',
      'TP 5',
      'FP',
    ]);
    expect(Object.fromEntries(named.standalonePoints.map((point) => [point.id, point.name]))).toEqual({
      'd-a1': 'TP 1',
      'd-a2': 'TP 2',
      'd-b1': 'TP 4',
    });
  });

  it('keeps the trigger types and returns the same arrays when the names are already right', () => {
    const first = nameUnknownLegsRoutePoints(backbone(), [dummy('d-a1', 'ul-a', 0, 'WP 2-D1')]);
    expect(first.routePoints[1].type).toBe('ul');

    const second = nameUnknownLegsRoutePoints(first.routePoints, first.standalonePoints);
    expect(second.routePoints).toBe(first.routePoints);
    expect(second.standalonePoints).toBe(first.standalonePoints);
  });
});

describe('previousOnDummyBranch', () => {
  const trigger = makeRoutePoint({ id: 'ul-1', name: 'UL1', type: 'ul' as RoutePoint['type'] });
  const dummy = (id: string, branchSequence: number) => makeRoutePoint({
    id,
    type: 'dummy' as RoutePoint['type'],
    featureType: 'dummy_branch_waypoint',
    triggerPointId: 'ul-1',
    branchSequence,
  });

  it('starts the first dummy leg at the trigger and later ones at the previous branch point', () => {
    const first = dummy('d-1', 0);
    const second = dummy('d-2', 1);
    const routePoints = [makeRoutePoint({ id: 'sp' }), trigger];
    const standalonePoints = [second, first];
    expect(previousOnDummyBranch(first, routePoints, standalonePoints)?.id).toBe('ul-1');
    expect(previousOnDummyBranch(second, routePoints, standalonePoints)?.id).toBe('d-1');
  });

  it('has nothing for a point that is not on a dummy branch', () => {
    expect(previousOnDummyBranch(trigger, [trigger], [])).toBeUndefined();
  });
});
