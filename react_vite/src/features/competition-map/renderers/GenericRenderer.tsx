import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import type { NavigationTask, Waypoint } from '../types';

function formatTime(dt: Date): string {
  const hh = String(dt.getHours()).padStart(2, '0');
  const mm = String(dt.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

export interface GenericRendererProps {
  map: L.Map | null;
  navigationTask: NavigationTask;
  contestants?: Record<string, any>;
  currentHighlightedContestant?: number | null;
  displaySecretGates?: boolean;
}

export default function GenericRenderer({ map, navigationTask, contestants, currentHighlightedContestant, displaySecretGates }: GenericRendererProps) {
  const markersRef = useRef<L.Marker[]>([]);
  const linesRef = useRef<L.Polyline[]>([]);
  const routeLineRef = useRef<L.Polyline | null>(null);

  useEffect(() => {
    if (!map || !navigationTask?.route) return;
    // Cleanup previous
    markersRef.current.forEach(m => m.remove());
    markersRef.current = [];
    linesRef.current.forEach(l => l.remove());
    linesRef.current = [];
    if (routeLineRef.current) { routeLineRef.current.remove(); routeLineRef.current = null; }

    // Render gates
    const filtered = filterWaypoints(navigationTask, displaySecretGates);
    filtered.forEach(gate => {
      const l = L.polyline(
        [[gate.gate_line[0][0], gate.gate_line[0][1]], [gate.gate_line[1][0], gate.gate_line[1][1]]],
        { color: 'blue' }
      ).addTo(map);
      linesRef.current.push(l);
    });

    // Render corridor polygon
    const polygonPoints = navigationTask.route.corridor_polygon.map(p => [p.lat, p.lng] as [number, number]);
    const corridor = L.polyline([polygonPoints, polygonPoints], { color: 'blue' }).addTo(map);
    routeLineRef.current = corridor;
    try { map.fitBounds(corridor.getBounds(), { padding: [50, 50] }); } catch {}

    // Render waypoint labels
    const currentContestant = currentHighlightedContestant && contestants ? contestants[currentHighlightedContestant] : undefined;
    filtered.forEach(waypoint => {
      let label = waypoint.name;
      if (currentContestant && currentContestant.gate_times && currentContestant.gate_times[waypoint.name]) {
        const t = new Date(currentContestant.gate_times[waypoint.name]);
        label = `${waypoint.name} ${formatTime(t)}`;
      }
      const m = L.marker(waypoint.outer_corner_position[0] as any, {
        icon: L.divIcon({
          html: `<div class="px-2 py-1 rounded bg-base-200 border border-base-300 text-xs">${label}</div>`,
          className: 'myGateLink',
          iconSize: [100, 20],
          iconAnchor: [50, 10]
        })
      }).addTo(map);
      markersRef.current.push(m);
    });

    return () => {
      markersRef.current.forEach(m => m.remove());
      linesRef.current.forEach(l => l.remove());
      if (routeLineRef.current) routeLineRef.current.remove();
      markersRef.current = [];
      linesRef.current = [];
      routeLineRef.current = null;
    };
  }, [map, navigationTask, contestants, currentHighlightedContestant, displaySecretGates]);

  return null;
}

export function filterWaypoints(navigationTask: NavigationTask, displaySecretGates?: boolean): Waypoint[] {
  return navigationTask.route.waypoints.filter(wp => {
    const checks = wp.gate_check || wp.time_check;
    const secretOk = (navigationTask.display_secrets && displaySecretGates) || wp.type !== 'secret';
    return checks && secretOk && (wp.type as string) !== 'dummy';
  });
}
