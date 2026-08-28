import L from 'leaflet';
import {
  getDistance,
  getBearing,
  getDestinationPoint,
  getDistanceFromLine,
} from '../../../../utils/geoUtils';
import { getQuadraticBezierPoints } from '../../../../utils/bezierPoints';
import { RoutePoint, Gate, Polygon, Mode, SelectionType } from '../../../../types';
import { UNKNOWN_LEG_TRIGGER_TYPE } from '../../unknownLegWizard';

// CIMA 2.A7 (Circle) default inner/outer radius bounds (metres), matching Scorecard's
// circle_radius_min_m/max_m field defaults - see models/scorecard_and_gate_score.py. The route
// editor has no scorecard context (a route can be authored before any task/scorecard exists), so
// it renders the CIMA default bounds rather than a contest-specific override.
const CIMA_CIRCLE_DEFAULT_MIN_RADIUS_M = 200;
const CIMA_CIRCLE_DEFAULT_MAX_RADIUS_M = 750;

type PointMarkerStyle = {
  color: string;
  radius: number;
  ring?: {
    color: string;
    className?: string;
    dashArray?: string;
    weight: number;
  };
};

export const getRoutePointMarkerStyle = (
  point: RoutePoint,
  options: { activeTriggerId?: string | null; emphasizeTriggers?: boolean } = {},
): PointMarkerStyle => {
  const { activeTriggerId = null, emphasizeTriggers = false } = options;

  let color = '#3b82f6';
  let radius = 6;

  if (point.type === 'sp') { color = '#22c55e'; radius = 8; }
  if (point.type === 'fp') { color = '#ef4444'; radius = 8; }
  if (point.type === 'secret') { color = '#64748b'; }
  if (point.type === 'catalogue_turnpoint') { color = '#8b5cf6'; radius = 7; }
  if (point.type === 'circle_center') { color = '#0f766e'; radius = 7; }
  if (point.type === 'circle_start') { color = '#2563eb'; radius = 7; }
  if (point.type === 'circle_entry') { color = '#d97706'; radius = 7; }
  if (point.type === 'circle_exit') { color = '#dc2626'; radius = 7; }
  if (point.featureType === 'dummy_branch_waypoint') { color = '#9ca3af'; }

  if (point.type === UNKNOWN_LEG_TRIGGER_TYPE) {
    color = '#f59e0b';
    radius = 9;
    const active = activeTriggerId === point.id;
    return {
      color,
      radius,
      ring: {
        color,
        className: !active && emphasizeTriggers ? 'animate-pulse' : undefined,
        dashArray: active ? undefined : '3 3',
        weight: active ? 3 : 2,
      },
    };
  }

  return { color, radius };
};

const getPointTooltipLabel = (point: RoutePoint, index: number) => {
  if (point.type === UNKNOWN_LEG_TRIGGER_TYPE) {
    return `${index + 1}. ⚑ UL ${point.name}`;
  }
  // point.name already carries the trigger name (see buildDummyBranchWaypoint's
  // `${trigger.name}-D<n>` naming), so no separate trigger lookup is needed here.
  return `${index + 1}. ${point.name}`;
};

export const clearLayers = (markersRef: React.MutableRefObject<{ [key: string]: L.Layer }>, polylinesRef: React.MutableRefObject<L.Layer[]>, routeLineRef: React.MutableRefObject<L.Polyline | null>, map: L.Map) => {
  Object.values(markersRef.current).forEach(layer => map.removeLayer(layer));
  polylinesRef.current.forEach(layer => map.removeLayer(layer));
  if (routeLineRef.current) map.removeLayer(routeLineRef.current);

  markersRef.current = {};
  polylinesRef.current = [];
  routeLineRef.current = null;
};

export const drawRouteLine = (
  map: L.Map,
  routePoints: RoutePoint[],
  standalonePoints: RoutePoint[],
  routeLineRef: React.MutableRefObject<L.Polyline | null>,
  polylinesRef: React.MutableRefObject<L.Layer[]>,
  mode: Mode,
  setRoutePoints: React.Dispatch<React.SetStateAction<RoutePoint[]>>,
  setSelectedId: (id: string | null) => void,
  setSelectionType: (type: SelectionType | null) => void,
  hideLabels: boolean,
  dragRef: React.MutableRefObject<any>,
  handleDragMove: (e: L.LeafletMouseEvent) => void,
  handleDragEnd: (e: L.LeafletMouseEvent) => void,
) => {
  if (routePoints.length <= 1) return;

  const latlngs: L.LatLng[] = [];
  const branchLineGroups: Array<{ triggerId: string; points: RoutePoint[] }> = [];
  const branchByTriggerId = new Map<string, RoutePoint[]>();
  standalonePoints
    .filter((point) => point.featureType === 'dummy_branch_waypoint' && point.triggerPointId)
    .sort((left, right) => {
      if (left.triggerPointId === right.triggerPointId) {
        return (left.branchSequence ?? 0) - (right.branchSequence ?? 0);
      }
      return String(left.triggerPointId).localeCompare(String(right.triggerPointId));
    })
    .forEach((point) => {
      const triggerId = point.triggerPointId as string;
      const existing = branchByTriggerId.get(triggerId) || [];
      existing.push(point);
      branchByTriggerId.set(triggerId, existing);
    });

  for (let index = 0; index < routePoints.length; index += 1) {
    const point = routePoints[index];
    if (index === 0) {
      latlngs.push(L.latLng(point.lat, point.lng));
      continue;
    }

    const previous = routePoints[index - 1];
    const previousTriggerBranch = previous.type === UNKNOWN_LEG_TRIGGER_TYPE ? branchByTriggerId.get(previous.id) || [] : [];
    if (previousTriggerBranch.length > 0) {
      branchLineGroups.push({ triggerId: previous.id, points: [previous, ...previousTriggerBranch] });
    }

    if (previous.type === UNKNOWN_LEG_TRIGGER_TYPE) {
      latlngs.push(L.latLng(point.lat, point.lng));
      continue;
    }

    if (point.segmentType === 'curved' && point.controlLat && point.controlLng) {
      const curvePoints = getQuadraticBezierPoints(previous, point, { lat: point.controlLat, lng: point.controlLng });
      latlngs.push(...curvePoints);
    } else {
      latlngs.push(L.latLng(point.lat, point.lng));
    }
  }

  const polyline = L.polyline(latlngs, {
    color: '#3b82f6',
    weight: 4,
    className: mode === 'view' ? 'cursor-crosshair' : '',
  }).addTo(map);

  polyline.on('click', (e: L.LeafletMouseEvent) => {
    if (mode !== 'view') return;
    L.DomEvent.stopPropagation(e.originalEvent);

    const clickPt = { lat: e.latlng.lat, lng: e.latlng.lng };
    let bestIndex = -1;
    let minDistance = Infinity;

    for (let i = 0; i < routePoints.length - 1; i++) {
      const p1 = routePoints[i];
      const p2 = routePoints[i + 1];
      let dist = Infinity;

      if (p2.segmentType === 'curved' && p2.controlLat && p2.controlLng) {
        const curvePoints = getQuadraticBezierPoints(p1, p2, { lat: p2.controlLat, lng: p2.controlLng });
        for (let j = 0; j < curvePoints.length - 1; j++) {
          const d = getDistanceFromLine(clickPt, curvePoints[j], curvePoints[j + 1]);
          if (d < dist) dist = d;
        }
      } else {
        dist = getDistanceFromLine(clickPt, p1, p2);
      }

      if (dist < minDistance) {
        minDistance = dist;
        bestIndex = i;
      }
    }

    if (bestIndex !== -1) {
      const p1 = routePoints[bestIndex];
      const p2 = routePoints[bestIndex + 1];

      if (p2.segmentType === 'curved') {
        setSelectedId(p2.id);
        setSelectionType('point');
        return;
      }

      const bearing = getBearing(p1, p2);
      const dist = getDistance(p1, clickPt);
      const newLoc = getDestinationPoint(p1, dist, bearing);

      const newPoint: RoutePoint = {
        id: crypto.randomUUID(),
        lat: newLoc.lat,
        lng: newLoc.lng,
        name: `Secret ${routePoints.length}`,
        type: 'secret',
        featureType: 'route_waypoint',
        width: 1000,
        isTiming: false,
        isPassing: true,
        segmentType: 'straight',
      };

      setRoutePoints(prev => {
        const next = [...prev];
        next.splice(bestIndex + 1, 0, newPoint);
        return next;
      });

      setSelectedId(newPoint.id);
      setSelectionType('point');
    }
  });

  if (mode === 'view') {
    for (let i = 0; i < routePoints.length - 1; i++) {
      const p1 = routePoints[i];
      const p2 = routePoints[i + 1];
      if (p2.segmentType === 'curved') continue;

      const mid = L.latLng((p1.lat + p2.lat) / 2, (p1.lng + p2.lng) / 2);
      const ghost = L.circleMarker(mid, {
        radius: 7,
        color: '#3b82f6',
        fillColor: '#3b82f6',
        opacity: 0.7,
        fillOpacity: 0.5,
        weight: 1,
        className: 'cursor-copy',
      }).addTo(map);

      ghost.on('mousedown', (e: L.LeafletMouseEvent) => {
        L.DomEvent.stopPropagation(e.originalEvent);

        const newPoint: RoutePoint = {
          id: crypto.randomUUID(),
          lat: mid.lat,
          lng: mid.lng,
          name: `Point ${routePoints.length + 1}`,
          type: 'tp',
          width: p1.width,
          isTiming: true,
          isPassing: true,
          segmentType: 'straight',
        };

        const nextPoints = [...routePoints];
        nextPoints.splice(i + 1, 0, newPoint);

        setRoutePoints(nextPoints);

        map.dragging.disable();
        dragRef.current = {
          type: 'point',
          id: newPoint.id,
          index: i + 1,
          startLatLng: e.latlng,
          initialPoints: nextPoints,
          hasMoved: true,
          selectionType: 'point',
        };
        map.on('mousemove', handleDragMove);
        map.on('mouseup', handleDragEnd);
      });

      polylinesRef.current.push(ghost);
    }
  }

  routeLineRef.current = polyline;
  polylinesRef.current.push(polyline);

  branchLineGroups.forEach((group) => {
    const branchLatLngs = group.points.map((point) => L.latLng(point.lat, point.lng));
    if (branchLatLngs.length < 2) return;
    const branchPolyline = L.polyline(branchLatLngs, {
      color: '#9ca3af',
      weight: 3,
      dashArray: '8 6',
    }).addTo(map);
    polylinesRef.current.push(branchPolyline);
  });

  if (!hideLabels) {
    for (let i = 0; i < routePoints.length - 1; i++) {
      const p1 = routePoints[i];
      const p2 = routePoints[i + 1];
      let dist = 0;
      let mid: L.LatLng | null = null;

      if (p2.segmentType === 'curved' && p2.controlLat && p2.controlLng) {
        const curvePoints = getQuadraticBezierPoints(p1, p2, { lat: p2.controlLat, lng: p2.controlLng });
        for (let j = 0; j < curvePoints.length - 1; j++) {
          dist += getDistance(curvePoints[j], curvePoints[j + 1]);
        }
        mid = curvePoints[Math.floor(curvePoints.length / 2)];
      } else {
        dist = getDistance(p1, p2);
        mid = L.latLng((p1.lat + p2.lat) / 2, (p1.lng + p2.lng) / 2);
      }

      const nm = (dist / 1852).toFixed(1);
      const labelMarker = L.marker([mid.lat, mid.lng], {
        icon: L.divIcon({
          className: 'bg-transparent',
          html: `<div class="transform -translate-x-1/2 -translate-y-[calc(50%+12px)] bg-white/75 backdrop-blur-[1px] px-1 rounded border border-slate-300 text-[10px] font-bold text-slate-600 shadow-sm whitespace-nowrap pointer-events-none w-max">${nm} NM</div>`,
        }),
        interactive: false,
      }).addTo(map);
      polylinesRef.current.push(labelMarker);
    }
  }
};

export const drawPoints = (
  map: L.Map,
  routePoints: RoutePoint[],
  mode: Mode,
  selectedId: string | null,
  markersRef: React.MutableRefObject<{ [key: string]: L.Layer }>,
  dragRef: React.MutableRefObject<any>,
  handleDragMove: (e: L.LeafletMouseEvent) => void,
  handleDragEnd: (e: L.LeafletMouseEvent) => void,
  hideLabels: boolean,
  setSelectedId?: (id: string | null) => void,
  setSelectionType?: (type: SelectionType | null) => void,
  setMode?: (mode: Mode) => void,
  pointSelectionType: SelectionType = 'point',
  options: { activeTriggerId?: string | null; emphasizeUnknownLegTriggers?: boolean } = {},
) => {
  routePoints.forEach((p, index) => {
    const style = getRoutePointMarkerStyle(p, {
      activeTriggerId: options.activeTriggerId,
      emphasizeTriggers: options.emphasizeUnknownLegTriggers,
    });

    const pointGroup = L.featureGroup().addTo(map);

    if (p.type === 'circle_center') {
      // CIMA 2.A7 requires the entry/exit crossing to fall between these two radii - show them
      // while authoring so the circle_start/entry/exit markers can be placed correctly.
      L.circle([p.lat, p.lng], {
        radius: CIMA_CIRCLE_DEFAULT_MIN_RADIUS_M,
        color: '#16a34a',
        weight: 2,
        dashArray: '6 6',
        fill: false,
        interactive: false,
      }).addTo(pointGroup);
      L.circle([p.lat, p.lng], {
        radius: CIMA_CIRCLE_DEFAULT_MAX_RADIUS_M,
        color: '#dc2626',
        weight: 2,
        dashArray: '10 6',
        fill: false,
        interactive: false,
      }).addTo(pointGroup);
    }

    if (p.width > 0) {
      L.circle([p.lat, p.lng], {
        radius: p.width / 2,
        color: style.color,
        weight: 1,
        fillColor: style.color,
        fillOpacity: 0.15,
        dashArray: '4, 4',
        interactive: false,
      }).addTo(pointGroup);
    }

    if (style.ring) {
      L.circleMarker([p.lat, p.lng], {
        radius: style.radius + 4,
        color: style.ring.color,
        weight: style.ring.weight,
        fill: false,
        opacity: 1,
        dashArray: style.ring.dashArray,
        className: style.ring.className,
        interactive: false,
      }).addTo(pointGroup);
    }

    const marker = L.circleMarker([p.lat, p.lng], {
      radius: style.radius,
      fillColor: style.color,
      color: '#fff',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.8,
      className: p.type === 'secret' ? '' : 'cursor-grab',
    }).addTo(pointGroup);

    marker.bindTooltip(getPointTooltipLabel(p, index), { permanent: !hideLabels, direction: 'right', offset: [10, 0] });

    marker.on('click', (e: L.LeafletMouseEvent) => {
      L.DomEvent.stopPropagation(e.originalEvent || e);
      if (setSelectedId) setSelectedId(p.id);
      if (setSelectionType) setSelectionType(pointSelectionType);
      if (setMode && !(options.emphasizeUnknownLegTriggers && p.type === UNKNOWN_LEG_TRIGGER_TYPE)) setMode('view');
    });
    marker.on('mouseover', () => { if (mode === 'view') map.dragging.disable(); });
    marker.on('mouseout', () => { if (mode === 'view' && !dragRef.current) map.dragging.enable(); });

    marker.on('mousedown', (e: L.LeafletMouseEvent) => {
      if (mode !== 'view') return;
      if (p.type === 'secret') return;

      L.DomEvent.stopPropagation(e.originalEvent);
      map.dragging.disable();
      dragRef.current = {
        type: 'point',
        id: p.id,
        index,
        startLatLng: e.latlng,
        initialPoints: routePoints,
        hasMoved: false,
        selectionType: pointSelectionType,
      };
      map.on('mousemove', handleDragMove);
      map.on('mouseup', handleDragEnd);
    });

    markersRef.current[`point-${p.id}`] = pointGroup;

    if (selectedId === p.id && p.segmentType === 'curved' && index > 0 && p.controlLat && p.controlLng) {
      const prev = routePoints[index - 1];
      const controlLatLng: L.LatLngTuple = [p.controlLat, p.controlLng];

      const dashLine = L.polyline([[prev.lat, prev.lng], controlLatLng, [p.lat, p.lng]], {
        color: '#64748b', weight: 1, dashArray: '4, 4',
      }).addTo(map);
      markersRef.current[`curve-dash-${p.id}`] = dashLine;

      const controlHandle = L.circleMarker(controlLatLng, {
        radius: 5, color: '#64748b', fillColor: '#fff', fillOpacity: 1, className: 'cursor-move',
      }).addTo(map);

      controlHandle.on('click', (e: L.LeafletMouseEvent) => L.DomEvent.stopPropagation(e.originalEvent || e));
      controlHandle.on('mousedown', (e: L.LeafletMouseEvent) => {
        if (mode !== 'view') return;
        L.DomEvent.stopPropagation(e.originalEvent);
        map.dragging.disable();
        dragRef.current = {
          type: 'curve_control',
          id: p.id,
          index,
          startLatLng: e.latlng,
          initialPoints: routePoints,
          hasMoved: false,
        };
        map.on('mousemove', handleDragMove);
        map.on('mouseup', handleDragEnd);
      });

      markersRef.current[`curve-handle-${p.id}`] = controlHandle;
    }
  });
};

export const drawGates = (map: L.Map, gates: Gate[], polylinesRef: React.MutableRefObject<L.Layer[]>, setSelectedId: (id: string | null) => void, setSelectionType: (type: SelectionType | null) => void, setMode: (mode: Mode) => void, hideLabels: boolean) => {
  gates.forEach(g => {
    const color = g.type === 'landing' ? '#8b5cf6' : '#f59e0b';
    const line = L.polyline([[g.p1.lat, g.p1.lng], [g.p2.lat, g.p2.lng]], {
      color: color,
      weight: 6,
      dashArray: '10, 10',
    }).addTo(map);

    line.bindTooltip(g.name, { permanent: !hideLabels, direction: 'center', className: 'bg-transparent border-0 shadow-none text-black font-bold' });

    line.on('click', (e) => {
      L.DomEvent.stopPropagation(e);
      setSelectedId(g.id);
      setSelectionType('gate');
      setMode('view');
    });

    polylinesRef.current.push(line);
  });
};

export const drawPolygons = (
  map: L.Map,
  polygons: Polygon[],
  mode: Mode,
  selectedId: string | null,
  selectionType: SelectionType | null,
  markersRef: React.MutableRefObject<{ [key: string]: L.Layer }>,
  dragRef: React.MutableRefObject<any>,
  handleDragMove: (e: L.LeafletMouseEvent) => void,
  handleDragEnd: (e: L.LeafletMouseEvent) => void,
  setSelectedId: (id: string | null) => void,
  setSelectionType: (type: SelectionType | null) => void,
  setMode: (mode: Mode) => void,
  hideLabels: boolean,
  setPolygons: React.Dispatch<React.SetStateAction<Polygon[]>>,
) => {
  polygons.forEach(poly => {
    let color = '#3b82f6';
    if (poly.type === 'prohibited') color = '#ef4444';
    if (poly.type === 'penalty') color = '#f97316';
    if (poly.type === 'duration_landing_area') color = '#22c55e';

    const polygonLayer = L.polygon(poly.points.map(p => [p.lat, p.lng]), {
      color: color,
      weight: 2,
      fillColor: color,
      fillOpacity: 0.2,
      className: mode === 'view' ? 'cursor-move' : '',
    }).addTo(map);

    polygonLayer.bindTooltip(poly.name, {
      permanent: !hideLabels,
      direction: 'center',
      className: 'bg-transparent border-0 shadow-none font-bold ',
    });

    polygonLayer.on('click', (e: L.LeafletMouseEvent) => {
      if (mode !== 'view') return;
      L.DomEvent.stopPropagation(e.originalEvent);

      if (selectedId === poly.id) {
        const clickPt = { lat: e.latlng.lat, lng: e.latlng.lng };
        let bestIndex = -1;
        let minDistance = Infinity;

        for (let i = 0; i < poly.points.length; i++) {
          const p1 = poly.points[i];
          const p2 = poly.points[(i + 1) % poly.points.length];
          const dist = getDistanceFromLine(clickPt, p1, p2);
          if (dist < minDistance) {
            minDistance = dist;
            bestIndex = i;
          }
        }

        if (bestIndex !== -1 && minDistance < 50) {
          const p1 = poly.points[bestIndex];
          const p2 = poly.points[(bestIndex + 1) % poly.points.length];

          const bearing = getBearing(p1, p2);
          const dist = getDistance(p1, clickPt);
          const newLoc = getDestinationPoint(p1, dist, bearing);

          setPolygons(prev => prev.map(p => {
            if (p.id !== poly.id) return p;
            const newPoints = [...p.points];
            newPoints.splice(bestIndex + 1, 0, { lat: newLoc.lat, lng: newLoc.lng } as any);
            return { ...p, points: newPoints };
          }));
          return;
        }
      }

      setSelectedId(poly.id);
      setSelectionType('polygon');
      setMode('view');
    });

    markersRef.current[`poly-${poly.id}`] = polygonLayer;
  });
};
