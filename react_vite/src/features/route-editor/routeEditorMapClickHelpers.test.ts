import { createInsertedRoutePoint } from './routeEditorMapClickHelpers';

describe('createInsertedRoutePoint', () => {
  it('defaults isTiming to true for a tp point (the known_time_gate collapse target)', () => {
    const point = createInsertedRoutePoint({ lat: 60, lng: 11 }, 'tp', 'route_waypoint', null, 1);
    expect(point.isTiming).toBe(true);
  });

  it('defaults isTiming to false for other route-insert pointTypes, e.g. secret', () => {
    const point = createInsertedRoutePoint({ lat: 60, lng: 11 }, 'secret', 'route_waypoint', null, 1);
    expect(point.isTiming).toBe(false);
  });
});
