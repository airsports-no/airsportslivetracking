// @vitest-environment jsdom
import { vi } from 'vitest';
import L from 'leaflet';
import type { Mode, RoutePoint } from '../../../../types';
import { HIT_RADIUS_PX } from '../../routeEditorMapClickHelpers';
import { createHitRegistry, drawGates, drawPoints, drawRouteLine } from './renderers';

const point = (id: string, lat: number, lng: number): RoutePoint => ({
  id, name: id, lat, lng, type: 'tp', width: 0, isTiming: true, isPassing: true, segmentType: 'straight',
} as RoutePoint);

function draw(points: RoutePoint[], mode: Mode = 'view') {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const map = L.map(container).setView([60, 11], 10);
  const markersRef = { current: {} as { [key: string]: L.Layer } };
  const dragRef = { current: null as any };
  const selected: string[] = [];
  const hits = createHitRegistry(map);
  drawPoints(map, points, mode, null, markersRef, dragRef, () => {}, () => {}, true, (id) => { if (id) selected.push(id); }, () => {}, () => {}, 'point', { hits });
  const areaOf = (id: string) => {
    let area: L.CircleMarker | null = null;
    (markersRef.current[`point-${id}`] as L.FeatureGroup).eachLayer((layer) => {
      if (layer instanceof L.CircleMarker && (layer.options as any).className === 'route-hit') area = layer;
    });
    return area as unknown as L.CircleMarker;
  };
  const click = (area: L.CircleMarker, latlng: L.LatLng) => {
    // 100 pixels per 0.001 degrees of latitude is not what this map has: use its own projection
    area.fire('click', { latlng, containerPoint: map.latLngToContainerPoint(latlng), originalEvent: new MouseEvent('click') });
  };
  return { map, markersRef, selected, hits, areaOf, click };
}

describe('the hit areas of the route editor points', () => {
  it('has an invisible, interactive area of at least 14 pixels around each point and a mark that is not interactive', () => {
    const { areaOf, markersRef } = draw([point('a', 60, 11)]);
    const area = areaOf('a');
    expect(area.options.radius).toBeGreaterThanOrEqual(14);
    expect(area.options.radius).toBe(HIT_RADIUS_PX);
    expect(area.options.fillOpacity).toBe(0);
    expect(area.options.stroke).toBe(false);
    expect(area.options.interactive).not.toBe(false);
    const marks: L.CircleMarker[] = [];
    (markersRef.current['point-a'] as L.FeatureGroup).eachLayer((layer) => {
      if (layer instanceof L.CircleMarker && layer !== area) marks.push(layer);
    });
    expect(marks.length).toBeGreaterThan(0);
    expect(marks.every((mark) => mark.options.interactive === false)).toBe(true);
  });

  it('selects the point when its area is clicked', () => {
    const { areaOf, click, selected } = draw([point('a', 60, 11)]);
    click(areaOf('a'), L.latLng(60, 11));
    expect(selected).toEqual(['a']);
  });

  it('selects the nearest of two points whose areas overlap, whichever area took the click', () => {
    const { map, areaOf, click, selected } = draw([point('a', 60, 11), point('b', 60, 11.02)]);
    const a = map.latLngToContainerPoint(L.latLng(60, 11));
    const b = map.latLngToContainerPoint(L.latLng(60, 11.02));
    expect(Math.abs(b.x - a.x)).toBeLessThan(HIT_RADIUS_PX * 2);
    // The click is next to b, and the area of a (the one underneath) is what Leaflet hands it to
    const nearB = map.containerPointToLatLng(L.point(b.x - 2, b.y));
    click(areaOf('a'), nearB);
    expect(selected).toEqual(['b']);
  });

  it('gives a gate a hit area at each end', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const map = L.map(container).setView([60, 11], 10);
    const polylinesRef = { current: [] as L.Layer[] };
    const selected: string[] = [];
    drawGates(
      map,
      [{ id: 'g', name: 'Gate', type: 'takeoff', p1: { lat: 60, lng: 11 }, p2: { lat: 60.01, lng: 11 }, width: 50 } as any],
      polylinesRef,
      (id) => { if (id) selected.push(id); },
      () => {},
      () => {},
      true,
    );
    const areas = polylinesRef.current.filter((layer) => (layer as any).options?.className === 'route-hit') as L.CircleMarker[];
    expect(areas).toHaveLength(2);
    areas[1].fire('click', { latlng: L.latLng(60.01, 11), containerPoint: map.latLngToContainerPoint(L.latLng(60.01, 11)), originalEvent: new MouseEvent('click') });
    expect(selected).toEqual(['g']);
  });
});

describe('a click on a hit area', () => {
  it('does not go on to the map, whose click would clear the selection', () => {
    const { map, areaOf, selected } = draw([point('a', 60, 11)]);
    const onMapClick = vi.fn();
    map.on('click', onMapClick);
    const element = areaOf('a').getElement() as Element;
    element.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: 0, clientY: 0 }));
    expect(selected).toEqual(['a']);
    expect(onMapClick).not.toHaveBeenCalled();
  });
});

describe('the dot in the middle of a leg', () => {
  const setup = () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const map = L.map(container).setView([60, 11], 10);
    const polylinesRef = { current: [] as L.Layer[] };
    const routeLineRef = { current: null as L.Polyline | null };
    const setRoutePoints = vi.fn();
    const onNotice = vi.fn();
    drawRouteLine(
      map, [point('a', 60, 11), point('b', 60, 11.1)], [], routeLineRef, polylinesRef, 'view', setRoutePoints, () => {}, () => {}, true,
      { current: null }, () => {}, () => {}, null, undefined, onNotice,
    );
    const ghost = polylinesRef.current.find((layer) => (layer as any).options?.className === 'cursor-copy') as L.CircleMarker;
    const press = () => ghost.fire('mousedown', { latlng: ghost.getLatLng(), containerPoint: L.point(100, 100), originalEvent: new MouseEvent('mousedown') });
    const move = (buttons: number, dx = 20) => map.fire('mousemove', { latlng: ghost.getLatLng(), containerPoint: L.point(100 + dx, 100), originalEvent: new MouseEvent('mousemove', { buttons }) });
    return { map, ghost, setRoutePoints, onNotice, press, move };
  };

  it('inserts a point when it is dragged with the button held', () => {
    const { press, move, setRoutePoints } = setup();
    press();
    move(1);
    expect(setRoutePoints).toHaveBeenCalledTimes(1);
  });

  it('notices a release outside the map, and then inserts nothing when the pointer comes back', () => {
    const { press, move, setRoutePoints, onNotice } = setup();
    press();
    document.body.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    expect(onNotice).toHaveBeenCalledTimes(1);
    move(0);
    expect(setRoutePoints).not.toHaveBeenCalled();
  });

  it('inserts nothing when the pointer comes back without the button held', () => {
    const { press, move, setRoutePoints } = setup();
    press();
    move(0);
    move(1);
    expect(setRoutePoints).not.toHaveBeenCalled();
  });

  it('stops waiting when the dot is removed by a redraw', () => {
    const { map, ghost, press, move, setRoutePoints } = setup();
    press();
    map.removeLayer(ghost);
    move(1);
    expect(setRoutePoints).not.toHaveBeenCalled();
  });
});
