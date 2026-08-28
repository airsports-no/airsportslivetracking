import type { RoutePoint } from '../../../../types';
import { getRoutePointMarkerStyle } from './renderers';

const asRoutePoint = (point: RoutePoint) => point;

const makePoint = (overrides: Partial<RoutePoint> = {}): RoutePoint => asRoutePoint({
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

describe('getRoutePointMarkerStyle', () => {
  it('keeps the existing start, finish, and secret colours', () => {
    expect(getRoutePointMarkerStyle(makePoint({ type: 'sp' as RoutePoint['type'] }))).toMatchObject({ color: '#22c55e', radius: 8 });
    expect(getRoutePointMarkerStyle(makePoint({ type: 'fp' as RoutePoint['type'] }))).toMatchObject({ color: '#ef4444', radius: 8 });
    expect(getRoutePointMarkerStyle(makePoint({ type: 'secret' as RoutePoint['type'] }))).toMatchObject({ color: '#64748b', radius: 6 });
  });

  it('styles unknown-leg triggers in amber with a dashed ring by default', () => {
    expect(getRoutePointMarkerStyle(makePoint({ id: 'trigger-1', type: 'ul' as RoutePoint['type'] }))).toEqual({
      color: '#f59e0b',
      radius: 9,
      ring: {
        color: '#f59e0b',
        className: undefined,
        dashArray: '3 3',
        weight: 2,
      },
    });
  });

  it('styles dummy-branch waypoints in grey', () => {
    expect(getRoutePointMarkerStyle(makePoint({ type: 'dummy' as RoutePoint['type'], featureType: 'dummy_branch_waypoint' }))).toMatchObject({
      color: '#9ca3af',
      radius: 6,
    });
  });

  it('pulses every trigger ring while awaiting a trigger selection', () => {
    expect(getRoutePointMarkerStyle(makePoint({ id: 'trigger-1', type: 'ul' as RoutePoint['type'] }), {
      emphasizeTriggers: true,
    }).ring).toEqual({
      color: '#f59e0b',
      className: 'animate-pulse',
      dashArray: '3 3',
      weight: 2,
    });
  });

  it('draws the active trigger ring solid even when all triggers are emphasised', () => {
    expect(getRoutePointMarkerStyle(makePoint({ id: 'trigger-1', type: 'ul' as RoutePoint['type'] }), {
      activeTriggerId: 'trigger-1',
      emphasizeTriggers: true,
    }).ring).toEqual({
      color: '#f59e0b',
      className: undefined,
      dashArray: undefined,
      weight: 3,
    });
  });
});
