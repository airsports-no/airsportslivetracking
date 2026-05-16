import { useEffect, useRef } from 'react';
import L from 'leaflet';
import type { NavigationTask, Waypoint, Contestant, RouteData } from '../../types';
import './WaypointLabel.css';

function formatTime(dt: Date): string {
  const hh = String(dt.getHours()).padStart(2, '0');
  const mm = String(dt.getMinutes()).padStart(2, '0');
  const ss = String(dt.getSeconds()).padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

function renderWaypointLabels(
    map: L.Map,
    waypoints: Waypoint[],
    contestants: Record<number, Contestant>,
    selectedContestantId: number | null
): L.Layer[] {
    const layers: L.Layer[] = [];
    const emptyIcon = L.divIcon({
        className: 'leaflet-div-icon-empty',
        html: '',
        iconSize: [0, 0],
        iconAnchor: [0, 0],
    });

    waypoints.forEach((waypoint: Waypoint) => {
        let label = waypoint.name; // Initialize label with waypoint name

        // Logic to add expected gate time
        if (selectedContestantId !== null && contestants[selectedContestantId]?.gate_times && contestants[selectedContestantId].gate_times![waypoint.name]) {
            const expectedTime = new Date(contestants[selectedContestantId].gate_times![waypoint.name]);
            label = `${waypoint.name} ${formatTime(expectedTime)}`;
        }

        const anyWaypoint = waypoint as any;
        let position: L.LatLngExpression = [waypoint.latitude, waypoint.longitude]; // Fallback position
        let tooltipDirection: L.TooltipOptions['direction'] = 'top'; // Fallback direction
        let tooltipOffset: L.PointTuple = [0, -10]; // Fallback offset

        const X_OFFSET = 0;
        const Y_OFFSET = 10;

        if (anyWaypoint.outer_corner_position && anyWaypoint.outer_corner_position.length >= 3) {
            position = anyWaypoint.outer_corner_position[0];
            const horizontalMultiplier = anyWaypoint.outer_corner_position[1]; // e.g., +1 or -1
            const verticalMultiplier = anyWaypoint.outer_corner_position[2];   // e.g., +1 or -1

            if(horizontalMultiplier > 0) tooltipDirection = 'right';
            if(horizontalMultiplier < 0) tooltipDirection = 'left';

            const offsetX = horizontalMultiplier * X_OFFSET;
            const offsetY = verticalMultiplier * Y_OFFSET;

            tooltipOffset = [offsetX, offsetY];
        }

        const tooltipOptions: L.TooltipOptions = {
            permanent: true,
            direction: tooltipDirection,
            offset: tooltipOffset,
            className: 'waypoint-label'
        };

        const marker = L.marker(position, {
            icon: emptyIcon, // Use a completely transparent icon
        }).addTo(map);

        marker.bindTooltip(label, tooltipOptions);

        layers.push(marker);
    });
    return layers;
}

interface Props {
  map: L.Map | null;
  route: RouteData | null;
  taskType: string[] | null;
  navTaskDisplaySecrets: boolean;
  displaySecrets: boolean; // User preference
  contestants: Record<number, Contestant>; // Add this
  selectedContestantId: number | null; // Add this
  isInitialLoad: boolean; // New prop
  onMapFit: (fitted: boolean) => void; // New prop
}

// From precisionRenderer.js
function renderPrecisionRoute(map: L.Map, route: RouteData, navTaskDisplaySecrets: boolean, displaySecrets: boolean): L.Layer[] {
  const layers: L.Layer[] = [];

  route.waypoints.filter((waypoint: Waypoint) => {
    return waypoint.type === 'sp' && waypoint.gate_line_extended
  }).forEach((gate: Waypoint) => {
    layers.push(L.polyline(gate.gate_line_extended!, {
        color: "blue",
        dashArray: "4 8"
    }).addTo(map));
  });

  const filterWaypoints = () => route.waypoints.filter((waypoint: Waypoint) => {
    return ((waypoint.gate_check || waypoint.time_check) && ((navTaskDisplaySecrets && displaySecrets) || waypoint.type !== "secret") && waypoint.type!=="dummy")
  });

  filterWaypoints().forEach((gate: Waypoint) => {
    layers.push(L.polyline(gate.gate_line, {
        color: "blue"
    }).addTo(map));
  });

  const tracks: L.LatLngExpression[][] = [];
  let currentTrack: L.LatLngExpression[] = [];
  const typesToIgnore = ["to", "ldg", "ildg", "dummy"];
  
  route.waypoints.forEach((waypoint: Waypoint) => {
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
    const routePolyline = L.polyline(track, {
        color: "blue"
    }).addTo(map);
    layers.push(routePolyline);
  }

  return layers;
}

// From airsportsRenderer.js
function renderAirsportsRoute(map: L.Map, route: RouteData, isAnr: boolean, navTaskDisplaySecrets: boolean, displaySecrets: boolean): L.Layer[] {
    const layers: L.Layer[] = [];
    
    if (route.corridor_polygon) {
        const polygon = route.corridor_polygon.map((p: any) => [p.lat, p.lng] as [number, number]);
        // Use L.polygon instead of L.polyline to ensure the corridor is closed
        layers.push(L.polygon(polygon, { color: "blue", fill: false, weight: 2 }).addTo(map));
    }

    const filterWaypoints = () => {
        if (isAnr) {
            return route.waypoints.filter((w: Waypoint) => w.type === 'sp' || w.type === 'fp');
        }
        return route.waypoints.filter((w: Waypoint) => ((w.gate_check || w.time_check) && ((navTaskDisplaySecrets && displaySecrets) || w.type !== "secret") && w.type!=="dummy"));
    }

    filterWaypoints().forEach((gate: Waypoint) => {
        const isSpFp = isAnr && (gate.type === 'sp' || gate.type === 'fp');
        layers.push(L.polyline(gate.gate_line, { 
            color: isSpFp ? "red" : "blue",
            weight: isSpFp ? 5 : 3
        }).addTo(map));
    });

    return layers;
}

// From landingRenderer.js
function renderLandingRoute(map: L.Map, route: RouteData): L.Layer[] {
    const layers: L.Layer[] = [];
    for(const gate of route.landing_gates) {
        layers.push(L.polyline(gate.gate_line, {
            color: "blue"
        }).addTo(map));
    }
    return layers;
}


// From pokerRenderer.js
function renderPokerRoute(map: L.Map, route: RouteData): L.Layer[] {
    const layers: L.Layer[] = [];
    
    // 1. Draw circles for waypoints
    route.waypoints.forEach((waypoint: Waypoint) => {
        if (waypoint.type !== 'dummy') {
            // width is in NM, convert half-width to meters for Leaflet circle radius
            const radiusMeters = (waypoint.width / 2) * 1852;
            layers.push(L.circle([waypoint.latitude, waypoint.longitude], {
                radius: radiusMeters,
                color: "blue",
                weight: 2,
                fillOpacity: 0.1
            }).addTo(map));
        }
    });

    // 2. Draw the route line
    const path: L.LatLngExpression[] = route.waypoints
        .filter(wp => wp.type !== 'dummy')
        .map(wp => [wp.latitude, wp.longitude]);
    
    if (path.length > 1) {
        layers.push(L.polyline(path, { color: "blue", weight: 2, opacity: 0.5 }).addTo(map));
    }

    return layers;
}


export default function RouteRenderer({ map, route, taskType, navTaskDisplaySecrets, displaySecrets, contestants, selectedContestantId, isInitialLoad, onMapFit }: Props) {
  const layersRef = useRef<L.Layer[]>([]);

  useEffect(() => {
    if (!map || !route || !taskType) return;

    // Clear previous layers
    layersRef.current.forEach(layer => layer.remove());
    layersRef.current = [];

    let layers: L.Layer[] = [];

    if (taskType.includes("poker")) {
        layers = layers.concat(renderPokerRoute(map, route));
    } else if (taskType.includes("precision")) {
      layers = layers.concat(renderPrecisionRoute(map, route, navTaskDisplaySecrets, displaySecrets));
    }
    if (taskType.includes("airsports") || taskType.includes("airsportchallenge")) {
      layers = layers.concat(renderAirsportsRoute(map, route, false, navTaskDisplaySecrets, displaySecrets));
    }
    if (taskType.includes("anr_corridor")) {
      layers = layers.concat(renderAirsportsRoute(map, route, true, navTaskDisplaySecrets, displaySecrets));
    }
    if (taskType.includes("landing")) {
      layers = layers.concat(renderLandingRoute(map, route));
    }
    
    const waypointsToLabel = route.waypoints.filter((w: Waypoint) => 
        (w.gate_check || w.time_check) && 
        ((navTaskDisplaySecrets && displaySecrets) || w.type !== "secret") && 
        w.type !== "dummy"
    );
    layers = layers.concat(renderWaypointLabels(map, waypointsToLabel, contestants, selectedContestantId));

    layersRef.current = layers;

    const ZOOM_THRESHOLD = 9;
    const handleZoom = () => {
        if (map.getZoom() < ZOOM_THRESHOLD) {
            map.getContainer().classList.add('hide-waypoint-labels');
        } else {
            map.getContainer().classList.remove('hide-waypoint-labels');
        }
    };

    map.on('zoomend', handleZoom);
    handleZoom(); // Initial check

    if (layers.length > 0) {
        const bounds = new L.FeatureGroup(layers).getBounds();
        if (isInitialLoad && bounds.isValid()) { // Only fit bounds on initial load
            map.fitBounds(bounds, { padding: [50, 50] });
            onMapFit(true); // Signal that initial fit has occurred
        }
    }


    return () => {
      layersRef.current.forEach(layer => layer.remove());
      layersRef.current = [];
      map.off('zoomend', handleZoom);
      map.getContainer().classList.remove('hide-waypoint-labels');
    };
  }, [map, route, taskType, navTaskDisplaySecrets, displaySecrets, contestants, selectedContestantId, isInitialLoad, onMapFit]);

  return null;
}
