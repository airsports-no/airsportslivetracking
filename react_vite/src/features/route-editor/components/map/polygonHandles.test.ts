// @vitest-environment jsdom
import L from 'leaflet';
import type { Mode, Polygon } from '../../../../types';
import { drawPolygons } from './renderers';

const polygon: Polygon = {
  id: 'zone-1',
  name: 'Zone',
  type: 'prohibited',
  points: [
    { lat: 60, lng: 11 },
    { lat: 60, lng: 11.1 },
    { lat: 60.1, lng: 11.1 },
    { lat: 60.1, lng: 11 },
  ],
};

function draw(selectedId: string | null, mode: Mode = 'view') {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const map = L.map(container).setView([60.05, 11.05], 10);
  const markersRef = { current: {} as { [key: string]: L.Layer } };
  const dragRef = { current: null as any };
  let polygons = [polygon];
  const setPolygons = (update: any) => {
    polygons = typeof update === 'function' ? update(polygons) : update;
  };
  drawPolygons(
    map,
    polygons,
    mode,
    selectedId,
    selectedId ? 'polygon' : null,
    markersRef,
    dragRef,
    () => {},
    () => {},
    () => {},
    () => {},
    () => {},
    true,
    setPolygons,
  );
  return { map, markersRef, dragRef, polygons: () => polygons };
}

const keys = (markersRef: { current: { [key: string]: L.Layer } }, prefix: string) =>
  Object.keys(markersRef.current).filter((key) => key.startsWith(prefix));

const mousedown = (layer: L.Layer, latlng: L.LatLng) =>
  layer.fire('mousedown', { latlng, originalEvent: new MouseEvent('mousedown') });

describe('the route editor zone handles', () => {
  it('gives a selected zone a handle on every corner and a dot on every edge', () => {
    const { markersRef } = draw('zone-1');
    expect(keys(markersRef, 'poly-handle-zone-1-')).toHaveLength(4);
    expect(keys(markersRef, 'poly-ghost-zone-1-')).toHaveLength(4);
  });

  it('gives a zone that is not selected none', () => {
    const { markersRef } = draw(null);
    expect(keys(markersRef, 'poly-handle-')).toHaveLength(0);
    expect(keys(markersRef, 'poly-ghost-')).toHaveLength(0);
    expect(keys(markersRef, 'poly-')).toEqual(['poly-zone-1']);
  });

  it('has no edge dots while a zone is being drawn, but keeps the corners', () => {
    const { markersRef } = draw('zone-1', 'add_point');
    expect(keys(markersRef, 'poly-handle-zone-1-')).toHaveLength(4);
    expect(keys(markersRef, 'poly-ghost-')).toHaveLength(0);
  });

  it('starts dragging a corner when it is grabbed', () => {
    const { markersRef, dragRef } = draw('zone-1');
    mousedown(markersRef.current['poly-handle-zone-1-2'], L.latLng(60.1, 11.1));
    expect(dragRef.current).toMatchObject({ type: 'poly_vertex', polyId: 'zone-1', vertexIndex: 2, hasMoved: false });
  });

  it('adds a corner halfway along an edge when its dot is grabbed, and drags it on', () => {
    const { markersRef, dragRef, polygons } = draw('zone-1');
    mousedown(markersRef.current['poly-ghost-zone-1-1'], L.latLng(60.05, 11.1));
    const points = polygons()[0].points;
    expect(points).toHaveLength(5);
    expect(points[2]).toEqual({ lat: 60.05, lng: 11.1 });
    expect(dragRef.current).toMatchObject({ type: 'poly_vertex', vertexIndex: 2, hasMoved: true });
  });

  it('closes the last edge back to the first corner', () => {
    const { markersRef, polygons } = draw('zone-1');
    mousedown(markersRef.current['poly-ghost-zone-1-3'], L.latLng(60.05, 11));
    const points = polygons()[0].points;
    expect(points).toHaveLength(5);
    expect(points[4]).toEqual({ lat: 60.05, lng: 11 });
  });

  it('moves the whole zone when it is dragged', () => {
    const { markersRef, dragRef } = draw('zone-1');
    mousedown(markersRef.current['poly-zone-1'], L.latLng(60.05, 11.05));
    expect(dragRef.current).toMatchObject({ type: 'poly_body', polyId: 'zone-1', initialPoints: polygon.points });
  });
});
