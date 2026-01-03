import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import type { NavigationTask } from '../types';

export default function ProhibitedRenderer({ map, navigationTask }: { map: L.Map | null; navigationTask: NavigationTask }) {
  const polysRef = useRef<L.Polygon[]>([]);

  useEffect(() => {
    const m = map;
    if (!m) return;

    // Cleanup any existing layers
    polysRef.current.forEach(p => p.remove());
    polysRef.current = [];

    for (const def of navigationTask.route.prohibited_set) {
      const latlngs = def.path.map(([lng, lat]) => [lat, lng] as [number, number]);
      const weight = 1;
      const color = def.type === 'prohibited' ? 'red' : def.type === 'penalty' ? 'orange' : def.type === 'info' ? 'lightblue' : 'blue';
      const poly = L.polygon(latlngs, { color, weight }).addTo(m);
      const options: L.TooltipOptions = {
        permanent: true,
        direction: 'center',
        className: 'prohibitedTooltip'
      };
      if (def.tooltip_position) {
        options.offset = def.tooltip_position as any;
      }
      poly.bindTooltip(def.name, options).openTooltip();
      polysRef.current.push(poly);
    }

    return () => {
      polysRef.current.forEach(p => p.remove());
      polysRef.current = [];
    };
  }, [map, navigationTask]);

  return null;
}
