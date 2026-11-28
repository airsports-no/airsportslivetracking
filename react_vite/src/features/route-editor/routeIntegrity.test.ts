import { describe, expect, it } from 'vitest';
import type { ObservationMarker, RoutePoint } from '../../types';
import { getMinimumObservationDistance } from './routeEditorMapClickHelpers';
import { reverseRoutePoints } from './routeEditorMutations';
import { removalNotice, removedByRouteChange, routeLegs, type RouteRemoval } from './routeIntegrity';

const point = (id: string, lat: number, lng: number, type: RoutePoint['type'] = 'tp', extra: Partial<RoutePoint> = {}): RoutePoint => ({
  id, name: id, lat, lng, type, width: 1852, isTiming: true, isPassing: true, segmentType: 'straight', ...extra,
});
const photo = (id: string, lat: number, lng: number): ObservationMarker => ({ id, name: id, lat, lng });
const MAX = 926;

// SP -(S1)- B -(S2)- C, 0.1 degrees of longitude (about 5.6 km) per leg
const route = (): RoutePoint[] => [
  point('SP', 60, 11, 'sp'),
  point('S1', 60, 11.05, 'secret'),
  point('B', 60, 11.1),
  point('S2', 60, 11.15, 'secret'),
  point('FP', 60, 11.2, 'fp'),
];
const removedIds = (before: RoutePoint[], after: RoutePoint[], photos: ObservationMarker[] = [], max = MAX) => {
  const removal = removedByRouteChange(before, after, photos, max);
  return { gates: removal.hiddenGates.map((gate) => gate.id), photos: removal.photos.map((item) => item.id) };
};
const move = (points: RoutePoint[], id: string, lat: number, lng: number) => points.map((item) => (item.id === id ? { ...item, lat, lng } : item));

describe('legs', () => {
  it('runs from one route point that is not a hidden gate to the next, with the hidden gates between them', () => {
    const legs = routeLegs(route());
    expect(legs.map((leg) => [leg.from.id, leg.to.id, leg.hiddenGates.map((gate) => gate.id)])).toEqual([
      ['SP', 'B', ['S1']],
      ['B', 'FP', ['S2']],
    ]);
  });
});

describe('what a change of the route removes: hidden gates', () => {
  it('removes nothing when nothing changed, or when only names and widths changed', () => {
    const before = route();
    expect(removedIds(before, before.map((item) => ({ ...item }))).gates).toEqual([]);
    expect(removedIds(before, before.map((item) => ({ ...item, name: `${item.name}!`, width: 500, isTiming: false }))).gates).toEqual([]);
  });

  it('removes the hidden gates of the legs of a moved end point, and only those', () => {
    expect(removedIds(route(), move(route(), 'FP', 60.01, 11.2)).gates).toEqual(['S2']);
    expect(removedIds(route(), move(route(), 'B', 60.01, 11.1)).gates).toEqual(['S1', 'S2']);
    expect(removedIds(route(), move(route(), 'SP', 60.01, 11)).gates).toEqual(['S1']);
  });

  it('removes the hidden gates of both legs of a deleted waypoint', () => {
    expect(removedIds(route(), route().filter((item) => item.id !== 'B')).gates).toEqual(['S1', 'S2']);
  });

  it('removes the hidden gates of a leg a waypoint is inserted into', () => {
    const after = route();
    after.splice(2, 0, point('NEW', 60, 11.08));
    expect(removedIds(route(), after).gates).toEqual(['S1']);
  });

  it('keeps the hidden gates when the route is extended past the last point', () => {
    const after = [...route().slice(0, -1), { ...route()[4], type: 'tp' as const }, point('FP2', 60, 11.3, 'fp')];
    expect(removedIds(route(), after).gates).toEqual([]);
  });

  it('does not count inserting or deleting a hidden gate as a change of the leg', () => {
    const inserted = route();
    inserted.splice(1, 0, point('S0', 60, 11.02, 'secret'));
    expect(removedIds(route(), inserted).gates).toEqual([]);
    expect(removedIds(route(), route().filter((item) => item.id !== 'S1')).gates).toEqual([]);
  });

  it('removes the hidden gates of a leg whose curve was reshaped', () => {
    const curved = (control: [number, number]) => route().map((item) => (
      item.id === 'B' ? { ...item, segmentType: 'curved' as const, controlLat: control[0], controlLng: control[1] } : item
    ));
    const before = curved([60.02, 11.05]);
    expect(removedIds(before, curved([60.03, 11.05])).gates).toEqual(['S1']);
    expect(removedIds(before, curved([60.02, 11.05])).gates).toEqual([]);
  });

  it('removes the hidden gates of a leg made curved', () => {
    const after = route().map((item) => (item.id === 'FP' ? { ...item, segmentType: 'curved' as const, controlLat: 60.02, controlLng: 11.15 } : item));
    expect(removedIds(route(), after).gates).toEqual(['S2']);
  });

  it('keeps the gates of a leg made straight again only when it is the same line (it is not)', () => {
    const curvedBefore = route().map((item) => (item.id === 'FP' ? { ...item, segmentType: 'curved' as const, controlLat: 60.02, controlLng: 11.15 } : item));
    expect(removedIds(curvedBefore, route()).gates).toEqual(['S2']);
  });

  it('removes the other hidden gates of the legs that join when a point becomes a hidden gate, but not that point', () => {
    const after = route().map((item) => (item.id === 'B' ? { ...item, type: 'secret' as const } : item));
    expect(removedIds(route(), after).gates).toEqual(['S1', 'S2']);
  });

  it('removes the hidden gate of the leg that is split when a hidden gate becomes a waypoint', () => {
    const before = [point('SP', 60, 11, 'sp'), point('S1', 60, 11.03, 'secret'), point('S2', 60, 11.06, 'secret'), point('FP', 60, 11.1, 'fp')];
    const after = before.map((item) => (item.id === 'S1' ? { ...item, type: 'tp' as const } : item));
    expect(removedIds(before, after).gates).toEqual(['S2']);
  });

  it('keeps everything when the route is reversed', () => {
    const before = route();
    expect(removedIds(before, reverseRoutePoints(before, false)).gates).toEqual([]);
    const curved = before.map((item) => (item.id === 'B' ? { ...item, segmentType: 'curved' as const, controlLat: 60.02, controlLng: 11.05 } : item));
    const reversed = reverseRoutePoints(curved, false);
    expect(reversed.filter((item) => item.type === 'secret').map((item) => item.id).sort()).toEqual(['S1', 'S2']);
    expect(removedIds(curved, reversed).gates).toEqual([]);
  });

  it('never touches standalone-type points that happen to be in the list', () => {
    const before = [...route(), point('TG', 60.5, 11.5, 'timed_turnpoint')];
    expect(removedIds(before, move(before, 'B', 60.01, 11.1)).gates).toEqual(['S1', 'S2']);
  });
});

describe('what a change of the route removes: photos', () => {
  const near = photo('P1', 59.995, 11.1); // about 556 m from the first leg
  const after = move(route(), 'B', 60.01, 11.1);

  it('removes a photo that is now farther than the limit', () => {
    const far = photo('P2', 59.995, 11.15);
    expect(removedIds(route(), move(route(), 'FP', 60.1, 11.2), [near, far]).photos).toEqual(['P2']);
  });

  it('keeps a photo exactly at the limit', () => {
    // The hidden gates of the moved point's legs are removed, so the route that is left has none
    const distance = getMinimumObservationDistance(near, after.filter((item) => item.type !== 'secret'));
    expect(distance).toBeGreaterThan(getMinimumObservationDistance(near, route()));
    expect(removedIds(route(), after, [near], distance).photos).toEqual([]);
    expect(removedIds(route(), after, [near], distance - 0.001).photos).toEqual(['P1']);
  });

  it('leaves a photo that was out of range already', () => {
    const outside = photo('P3', 59.95, 11.1);
    expect(removedIds(route(), after, [outside]).photos).toEqual([]);
  });

  it('keeps a photo that is still in range of a drawn curve', () => {
    const curved = route().map((item) => (item.id === 'B' ? { ...item, segmentType: 'curved' as const, controlLat: 60.004, controlLng: 11.05 } : item));
    const onCurve = photo('P4', 60.002, 11.05);
    expect(removedIds(route(), curved, [onCurve]).photos).toEqual([]);
  });

  it('keeps the photos when there is no route left to measure against', () => {
    expect(removedIds(route(), [route()[0]], [near]).photos).toEqual([]);
  });
});

describe('the notice', () => {
  const removal = (gates: string[], photos: string[], legCount = 1): RouteRemoval => ({
    hiddenGates: gates.map((name) => point(name, 60, 11, 'secret', { name })),
    photos: photos.map((name) => photo(name, 60, 11)),
    legCount,
  });

  it('is nothing when nothing was removed', () => {
    expect(removalNotice(removal([], []), MAX)).toBeNull();
  });

  it('names a hidden gate in the singular', () => {
    expect(removalNotice(removal(['Secret 3'], []), MAX)).toBe('Removed hidden gate Secret 3: the leg it was on has changed.');
  });

  it('names several hidden gates and a photo', () => {
    expect(removalNotice(removal(['Secret 3', 'Secret 4'], ['P2']), MAX))
      .toBe('Removed hidden gates Secret 3 and Secret 4 and photo P2: the leg they were on has changed and the photo is now too far from the route.');
  });

  it('says legs when the gates were on several legs', () => {
    expect(removalNotice(removal(['A', 'B', 'C'], [], 2), MAX)).toBe('Removed hidden gates A, B and C: the legs they were on have changed.');
  });

  it('says why a photo went, with the limit in nautical miles', () => {
    expect(removalNotice(removal([], ['P2']), MAX)).toBe('Removed photo P2: it is now more than 0.5 NM from the route.');
    expect(removalNotice(removal([], ['P1', 'P2']), 1852)).toBe('Removed photos P1 and P2: they are now more than 1 NM from the route.');
  });

  it('names at most five, then how many more', () => {
    const names = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
    expect(removalNotice(removal([], names), MAX)).toContain('photos A, B, C, D, E and 2 more:');
    expect(removalNotice(removal([], names.slice(0, 5)), MAX)).toContain('photos A, B, C, D and E:');
  });
});
