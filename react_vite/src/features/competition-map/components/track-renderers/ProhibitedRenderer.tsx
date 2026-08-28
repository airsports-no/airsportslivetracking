import { useEffect, useRef } from 'react';
import L from 'leaflet';
import type { NavigationTask, ProhibitedZone } from '../../types';

interface Props {
  map: L.Map | null;
  navTask: NavigationTask | null;
}

function drawProhibitedZone(map: L.Map, zone: ProhibitedZone): L.Polygon {
  let color = 'red';
  if (zone.type === 'penalty') color = 'orange';
  else if (zone.type === 'info') color = 'lightblue';
  else if (zone.type === 'gate') color = 'blue';
  // Matches the route editor's duration_landing_area colour (#22c55e) - this
  // is an allowed landing area, not a prohibited/penalty zone, so it should
  // not default to the alarming red used for unrecognised zone types.
  else if (zone.type === 'duration_landing_area') color = '#22c55e';

  const p = L.polygon(zone.path.map((c: [number, number]) => [c[1], c[0]]), { color, weight: 1 }).addTo(map);

  const options: L.TooltipOptions = {
    permanent: true,
    direction: 'center',
    className: 'prohibitedTooltip',
  };
  if (zone.tooltip_position) {
    options.offset = [zone.tooltip_position[0], zone.tooltip_position[1]];
  }
  if (zone.type === 'gate') {
    options.permanent = false;
  }

  p.bindTooltip(zone.name, options);
  if (options.permanent) {
    p.openTooltip();
  }

  return p;
}


export default function ProhibitedRenderer({ map, navTask }: Props) {
  const layersRef = useRef<L.Layer[]>([]);

  useEffect(() => {
    if (!map || !navTask) return;

    // Clear previous layers
    layersRef.current.forEach(layer => layer.remove());
    layersRef.current = [];

    const layers: L.Layer[] = [];
    for (const zone of navTask.route.prohibited_set) {
      layers.push(drawProhibitedZone(map, zone));
    }
    layersRef.current = layers;

    return () => {
      layersRef.current.forEach(layer => layer.remove());
      layersRef.current = [];
    };
  }, [map, navTask]);

  return null;
}
