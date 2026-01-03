import { useEffect, useRef } from 'react';
import L from 'leaflet';
import type { NavigationTask, Waypoint } from '../types';

interface Props {
  map: L.Map | null;
  navTask: NavigationTask | null;
}

// From precisionRenderer.js
function renderPrecisionRoute(map: L.Map, navTask: NavigationTask): L.Layer[] {
  const layers: L.Layer[] = [];

  navTask.route.waypoints.filter((waypoint) => {
    return waypoint.type === 'sp' && waypoint.gate_line_extended
  }).forEach((gate) => {
    layers.push(L.polyline(gate.gate_line_extended, {
        color: "blue",
        dashArray: "4 8"
    }).addTo(map));
  });

  const filterWaypoints = () => navTask.route.waypoints.filter((waypoint) => {
    return ((waypoint.gate_check || waypoint.time_check) && (navTask.display_secrets || waypoint.type !== "secret") && waypoint.type!=="dummy")
  });

  filterWaypoints().forEach((gate) => {
    layers.push(L.polyline(gate.gate_line, {
        color: "blue"
    }).addTo(map));
  });

  const tracks: L.LatLngExpression[][] = [];
  let currentTrack: L.LatLngExpression[] = [];
  const typesToIgnore = ["to", "ldg", "ildg", "dummy"];
  
  navTask.route.waypoints.forEach(waypoint => {
    if (waypoint.type === 'isp') { // This type is not in the Waypoint type, assuming it's a string from old code.
        tracks.push(currentTrack);
        currentTrack = [];
    }
    if (!typesToIgnore.includes(waypoint.type)) {
        if (waypoint.is_procedure_turn) {
            // procedure_turn_points is not on waypoint type. Assume it exists from old code.
            // @ts-ignore
            currentTrack.push(...waypoint.procedure_turn_points);
        } else {
            currentTrack.push([waypoint.latitude, waypoint.longitude]);
        }
    }
  });
  tracks.push(currentTrack);

  for (const track of tracks) {
    const route = L.polyline(track, {
        color: "blue"
    }).addTo(map);
    layers.push(route);
  }

  return layers;
}

// From airsportsRenderer.js
function renderAirsportsRoute(map: L.Map, navTask: NavigationTask, isAnr: boolean): L.Layer[] {
    const layers: L.Layer[] = [];
    
    if (navTask.route.corridor_polygon) {
        const polygon = navTask.route.corridor_polygon.map(p => [p.lat, p.lng] as [number, number]);
        // The polygon is not closed in the new API response, so we don't need to close it manually.
        layers.push(L.polyline(polygon, { color: "blue" }).addTo(map));
    }

    const filterWaypoints = () => {
        if (isAnr) {
            return navTask.route.waypoints.filter(w => w.type === 'sp' || w.type === 'fp');
        }
        return navTask.route.waypoints.filter(w => ((w.gate_check || w.time_check) && (navTask.display_secrets || w.type !== "secret") && w.type!=="dummy"));
    }

    filterWaypoints().forEach(gate => {
        layers.push(L.polyline(gate.gate_line, { color: "blue" }).addTo(map));
    });

    return layers;
}

// From landingRenderer.js
function renderLandingRoute(map: L.Map, navTask: NavigationTask): L.Layer[] {
    const layers: L.Layer[] = [];
    for(const gate of navTask.route.landing_gates) {
        layers.push(L.polyline(gate.gate_line, {
            color: "blue"
        }).addTo(map));
    }
    return layers;
}


export default function RouteRenderer({ map, navTask }: Props) {
  const layersRef = useRef<L.Layer[]>([]);

  useEffect(() => {
    if (!map || !navTask) return;

    // Clear previous layers
    layersRef.current.forEach(layer => layer.remove());
    layersRef.current = [];

    const taskType = navTask.scorecard.task_type;
    let layers: L.Layer[] = [];

    if (taskType.includes("precision") || taskType.includes("poker")) {
      layers = layers.concat(renderPrecisionRoute(map, navTask));
    }
    if (taskType.includes("airsports") || taskType.includes("airsportchallenge")) {
      layers = layers.concat(renderAirsportsRoute(map, navTask, false));
    }
    if (taskType.includes("anr_corridor")) {
      layers = layers.concat(renderAirsportsRoute(map, navTask, true));
    }
    if (taskType.includes("landing")) {
      layers = layers.concat(renderLandingRoute(map, navTask));
    }
    
    layersRef.current = layers;

    if (layers.length > 0) {
        const bounds = new L.FeatureGroup(layers).getBounds();
        if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [50, 50] });
        }
    }


    return () => {
      layersRef.current.forEach(layer => layer.remove());
      layersRef.current = [];
    };
  }, [map, navTask]);

  return null;
}
