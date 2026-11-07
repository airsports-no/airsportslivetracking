// @vitest-environment jsdom
import L from 'leaflet';
import type { RoutePoint } from '../../../../types';
import { drawRouteLine } from './renderers';

const point = (id: string, type: RoutePoint['type'], lat: number, lng: number): RoutePoint => ({
  id,
  name: type.toUpperCase(),
  type,
  lat,
  lng,
  segmentType: 'straight',
  width: 926,
  isTiming: true,
  isPassing: true,
  featureType: 'route_waypoint',
});

/** Draws a two-point route and clicks its leg halfway, as a user placing a gate there; returns the route afterwards. */
function clickTheLeg(legInsertType: RoutePoint['type'] | null): RoutePoint[] {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const map = L.map(container).setView([60.05, 11.05], 10);
  const routePoints = [point('sp', 'sp', 60, 11), point('fp', 'fp', 60.1, 11.1)];
  let current = routePoints;
  const routeLineRef = { current: null as L.Polyline | null };
  drawRouteLine(
    map,
    routePoints,
    [],
    routeLineRef,
    { current: [] },
    'view',
    (update: any) => {
      current = typeof update === 'function' ? update(current) : update;
    },
    () => {},
    () => {},
    true,
    { current: null },
    () => {},
    () => {},
    legInsertType,
  );
  routeLineRef.current!.fire('click', {
    latlng: L.latLng(60.05, 11.05),
    originalEvent: new MouseEvent('click'),
  });
  return current;
}

describe('a gate placed by clicking a leg', () => {
  it('is a secret gate that is checked and timed from the start', () => {
    const route = clickTheLeg(null);
    expect(route).toHaveLength(3);
    expect(route[1]).toMatchObject({ type: 'secret', isTiming: true, isPassing: true });
  });

  it('is checked and timed when a wizard step places a known time gate on the leg', () => {
    expect(clickTheLeg('tp')[1]).toMatchObject({ type: 'tp', isTiming: true, isPassing: true });
  });
});
