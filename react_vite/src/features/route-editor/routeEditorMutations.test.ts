import {
  updateItemById,
  reorderItemsById,
  deleteItemById,
  normalizeDeletedBackboneRoutePoints,
  renumberRoutePoints,
  reverseRoutePoints,
} from './routeEditorMutations';
import type { RoutePoint } from '../../types';

function makePoint(overrides: Partial<RoutePoint> & { id: string; type: RoutePoint['type'] }): RoutePoint {
  return {
    name: overrides.type.toUpperCase(),
    lat: 60,
    lng: 11,
    segmentType: 'straight',
    width: 100,
    isTiming: false,
    isPassing: true,
    featureType: 'route_waypoint',
    ...overrides,
  };
}

describe('updateItemById', () => {
  it('applies the updater only to the matching item', () => {
    const items = [{ id: 'a', value: 1 }, { id: 'b', value: 2 }];
    const result = updateItemById(items, 'b', (item) => ({ ...item, value: 99 }));
    expect(result).toEqual([{ id: 'a', value: 1 }, { id: 'b', value: 99 }]);
  });

  it('leaves the array unchanged when no item matches', () => {
    const items = [{ id: 'a', value: 1 }];
    const result = updateItemById(items, 'missing', (item) => ({ ...item, value: 99 }));
    expect(result).toEqual(items);
  });
});

describe('reorderItemsById', () => {
  const items = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];

  it('swaps with the previous item when moving up', () => {
    expect(reorderItemsById(items, 'b', 'up')).toEqual([{ id: 'b' }, { id: 'a' }, { id: 'c' }]);
  });

  it('is a no-op when moving the first item up', () => {
    expect(reorderItemsById(items, 'a', 'up')).toEqual(items);
  });

  it('swaps with the next item when moving down', () => {
    expect(reorderItemsById(items, 'b', 'down')).toEqual([{ id: 'a' }, { id: 'c' }, { id: 'b' }]);
  });

  it('is a no-op when moving the last item down', () => {
    expect(reorderItemsById(items, 'c', 'down')).toEqual(items);
  });

  it('returns the original array when the id is not found', () => {
    expect(reorderItemsById(items, 'missing', 'up')).toBe(items);
  });
});

describe('deleteItemById', () => {
  it('removes the matching item', () => {
    const items = [{ id: 'a' }, { id: 'b' }];
    expect(deleteItemById(items, 'a')).toEqual([{ id: 'b' }]);
  });

  it('leaves the array unchanged (by value) when the id is not found', () => {
    const items = [{ id: 'a' }];
    expect(deleteItemById(items, 'missing')).toEqual(items);
  });
});

describe('normalizeDeletedBackboneRoutePoints', () => {
  it('returns an empty array unchanged', () => {
    expect(normalizeDeletedBackboneRoutePoints([])).toEqual([]);
  });

  it('forces the first point to SP and the last to FP, leaving the middle alone', () => {
    const points = [makePoint({ id: '1', type: 'tp', name: 'WP 1' }), makePoint({ id: '2', type: 'tp', name: 'WP 2' }), makePoint({ id: '3', type: 'tp', name: 'WP 3' })];
    const result = normalizeDeletedBackboneRoutePoints(points);
    expect(result[0]).toMatchObject({ id: '1', type: 'sp', name: 'SP', featureType: 'route_waypoint' });
    expect(result[1]).toMatchObject({ id: '2', type: 'tp', name: 'WP 2' });
    expect(result[2]).toMatchObject({ id: '3', type: 'fp', name: 'FP', featureType: 'route_waypoint' });
  });
});

describe('renumberRoutePoints', () => {
  it('numbers SP, waypoints, and FP in order for a non-three-point-backbone task', () => {
    const points = [
      makePoint({ id: '1', type: 'sp' }),
      makePoint({ id: '2', type: 'tp' }),
      makePoint({ id: '3', type: 'tp' }),
      makePoint({ id: '4', type: 'fp' }),
    ];
    const result = renumberRoutePoints(points, false);
    expect(result.map((p) => p.name)).toEqual(['SP', 'WP 1', 'WP 2', 'FP']);
    expect(result.map((p) => p.type)).toEqual(['sp', 'tp', 'tp', 'fp']);
  });

  it('keeps index 1 as MP for a three-point-backbone task', () => {
    const points = [makePoint({ id: '1', type: 'sp' }), makePoint({ id: '2', type: 'tp' }), makePoint({ id: '3', type: 'fp' })];
    const result = renumberRoutePoints(points, true);
    expect(result.map((p) => p.name)).toEqual(['SP', 'MP', 'FP']);
  });

  it('numbers secret points with a per-leg counter that resets after each real waypoint', () => {
    const points = [
      makePoint({ id: '1', type: 'sp' }),
      makePoint({ id: '2', type: 'secret' }),
      makePoint({ id: '3', type: 'secret' }),
      makePoint({ id: '4', type: 'tp' }),
      makePoint({ id: '5', type: 'secret' }),
      makePoint({ id: '6', type: 'fp' }),
    ];
    const result = renumberRoutePoints(points, false);
    expect(result.map((p) => p.name)).toEqual(['SP', 'Secret 0.1', 'Secret 0.2', 'WP 1', 'Secret 1.1', 'FP']);
  });

  it('does not overwrite the type of non-route_waypoint (CIMA marker) points to tp', () => {
    const points = [
      makePoint({ id: '1', type: 'sp' }),
      makePoint({ id: '2', type: 'circle_center', featureType: 'circle_center_marker' }),
      makePoint({ id: '3', type: 'fp' }),
    ];
    const result = renumberRoutePoints(points, false);
    // Middle point keeps its CIMA marker type - only its display name changes.
    expect(result[1].type).toBe('circle_center');
    expect(result[1].name).toBe('WP 1');
  });
});

describe('reverseRoutePoints', () => {
  it('returns the input unchanged for fewer than two points', () => {
    const points = [makePoint({ id: '1', type: 'sp' })];
    expect(reverseRoutePoints(points, false)).toBe(points);
  });

  it('reverses point order and re-derives SP/FP/segment info', () => {
    const points = [
      makePoint({ id: '1', type: 'sp', lat: 60, lng: 11, segmentType: 'straight' }),
      makePoint({ id: '2', type: 'tp', lat: 60.1, lng: 11.1, segmentType: 'curved', controlLat: 60.05, controlLng: 11.05 }),
      makePoint({ id: '3', type: 'fp', lat: 60.2, lng: 11.2, segmentType: 'straight' }),
    ];
    const result = reverseRoutePoints(points, false);
    // Original order 1,2,3 -> reversed 3,2,1; ids track the point, names/types re-derived by renumberRoutePoints.
    expect(result.map((p) => p.id)).toEqual(['3', '2', '1']);
    expect(result.map((p) => p.name)).toEqual(['SP', 'WP 1', 'FP']);
    expect(result.map((p) => p.type)).toEqual(['sp', 'tp', 'fp']);
    // First point after reversal is always a fresh SP: straight, no control points.
    expect(result[0].segmentType).toBe('straight');
    expect(result[0].controlLat).toBeUndefined();
    // Segment info describes the leg ARRIVING at each point. Point 3's
    // (straight) incoming-leg info becomes point 2's incoming-leg info in
    // the reversed order (index 1); the curve that used to describe the
    // physical leg between points 1 and 2 (originally point 2's incoming
    // segment) now describes that same physical leg's arrival at point 1,
    // which is at the end of the reversed order (index 2, now FP).
    expect(result[1].segmentType).toBe('straight');
    expect(result[2].segmentType).toBe('curved');
    expect(result[2].controlLat).toBe(60.05);
  });

  it('keeps index 1 as MP after reversing a three-point-backbone task', () => {
    const points = [makePoint({ id: '1', type: 'sp' }), makePoint({ id: '2', type: 'tp' }), makePoint({ id: '3', type: 'fp' })];
    const result = reverseRoutePoints(points, true);
    expect(result.map((p) => p.name)).toEqual(['SP', 'MP', 'FP']);
  });
});
