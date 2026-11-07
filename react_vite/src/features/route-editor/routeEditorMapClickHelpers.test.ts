import { createInsertedRoutePoint, createObservationMarker, nextObservationName } from './routeEditorMapClickHelpers';

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
