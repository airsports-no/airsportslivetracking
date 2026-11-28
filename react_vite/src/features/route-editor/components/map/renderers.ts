import L from 'leaflet';
import { hasControl } from '../../curveControl';
import {
  getDistance,
  getBearing,
  getDestinationPoint,
  getDistanceFromLine,
  getGreatCirclePoints,
  getIntermediatePoint,
} from '../../../../utils/geoUtils';
import { getQuadraticBezierPoints } from '../../../../utils/bezierPoints';
import { RoutePoint, Gate, LatLng, Polygon, Mode, SelectionType } from '../../../../types';
import { hasDraggedPastThreshold, MID_LEG_DOT_HINT } from '../../midLegDrag';
import { UNKNOWN_LEG_TRIGGER_TYPE } from '../../unknownLegWizard';
import { applyLegInsert, findNearestHit, HIT_RADIUS_PX, legClickAction, type HitKind } from '../../routeEditorMapClickHelpers';

// CIMA 2.A7 (Circle) default inner/outer radius bounds (metres), matching Scorecard's
// circle_radius_min_m/max_m field defaults - see models/scorecard_and_gate_score.py. The route
// editor has no scorecard context (a route can be authored before any task/scorecard exists), so
// it renders the CIMA default bounds rather than a contest-specific override.
const CIMA_CIRCLE_DEFAULT_MIN_RADIUS_M = 200;
const CIMA_CIRCLE_DEFAULT_MAX_RADIUS_M = 750;

// The hidden gate just placed pulses for a second (a CSS class on its mark, see .hidden-gate-pulse). The mark is drawn
// again after the insert, so the id is remembered here and the class added when that mark is created.
const HIDDEN_GATE_PULSE_MS = 1200;
let pulsingGate: { id: string; until: number } | null = null;
const pulseClassFor = (id: string): string | undefined => (
  pulsingGate && pulsingGate.id === id && Date.now() < pulsingGate.until ? 'hidden-gate-pulse' : undefined
);

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
  if (point.featureType === 'dummy_branch_waypoint') {
    return `${index + 1}. ${point.name} (extension)`;
  }
  return `${index + 1}. ${point.name}`;
};

/**
 * A straight leg of the route as the points to draw it through: along the great circle between its gates, which is where
 * it is scored (and where a gate placed on it goes), instead of the straight line on the flat map that would bend at
 * such a gate (see getGreatCirclePoints).
 */
export const greatCircleLatLngs = (from: LatLng, to: LatLng): L.LatLng[] =>
  getGreatCirclePoints(from, to).map((point) => L.latLng(point.lat, point.lng));

// --- Hit areas ---
// What a click on an existing point, gate end, photo or polygon handle selects. Each of them has an invisible circle of
// HIT_RADIUS_PX around it that takes the clicks and drags, so a click meant for it does not fall through to the map.
// Where hit areas overlap the nearest centre to the click wins; the registry holds them all to decide that, and MapCanvas
// uses it to select the nearest one when a click in a placing mode lands within the same radius.

export interface HitTarget {
  key: string;
  kind: HitKind;
  latlng: L.LatLng;
  select: () => void;
  // Starts dragging the thing (a point, a polygon corner); not every kind can be dragged.
  startDrag?: (e: L.LeafletMouseEvent) => void;
}

export interface HitRegistry {
  map: L.Map;
  targets: HitTarget[];
}

export const createHitRegistry = (map: L.Map): HitRegistry => ({ map, targets: [] });

// The target a mouse event on [own]'s hit area is for: the nearest of all of them to the pointer.
export const resolveHitTarget = (registry: HitRegistry, e: L.LeafletMouseEvent, own: HitTarget): HitTarget => {
  if (!e.containerPoint) return own;
  const candidates = registry.targets.map((target) => {
    const point = registry.map.latLngToContainerPoint(target.latlng);
    return { x: point.x, y: point.y, target };
  });
  return findNearestHit({ x: e.containerPoint.x, y: e.containerPoint.y }, candidates)?.target ?? own;
};

interface HitAreaOptions {
  tooltip?: { text: string; options: L.TooltipOptions };
  // Hovering the area keeps the map from panning in select mode, so that a drag of the thing is not a drag of the map.
  lockMapWhileHovered?: { mode: Mode; dragRef: React.MutableRefObject<any> };
}

// Stops a mouse event on a layer from going on to the map (whose click clears the selection). Leaflet decides that from
// the flag it sets on the original event, which stopping the DOM event alone does not set.
export const stopMapEvent = (e: L.LeafletMouseEvent): void => {
  L.DomEvent.stopPropagation(e);
  e.originalEvent?.stopPropagation?.();
};

// Adds the invisible hit area for [target] to [parent] and returns it. The visible mark is not interactive itself.
export const addHitArea = (
  registry: HitRegistry,
  parent: L.Map | L.LayerGroup,
  target: HitTarget,
  options: HitAreaOptions = {},
): L.CircleMarker => {
  registry.targets.push(target);
  const area = L.circleMarker(target.latlng, {
    radius: HIT_RADIUS_PX,
    stroke: false,
    fill: true,
    fillOpacity: 0,
    className: 'route-hit',
    bubblingMouseEvents: false,
  }).addTo(parent as L.Map);

  if (options.tooltip) area.bindTooltip(options.tooltip.text, options.tooltip.options);

  area.on('click', (e: L.LeafletMouseEvent) => {
    stopMapEvent(e);
    resolveHitTarget(registry, e, target).select();
  });
  area.on('mousedown', (e: L.LeafletMouseEvent) => {
    const resolved = resolveHitTarget(registry, e, target);
    if (!resolved.startDrag) return;
    stopMapEvent(e);
    resolved.startDrag(e);
  });
  const lock = options.lockMapWhileHovered;
  if (lock) {
    area.on('mouseover', () => { if (lock.mode === 'view') registry.map.dragging.disable(); });
    area.on('mouseout', () => { if (lock.mode === 'view' && !lock.dragRef.current) registry.map.dragging.enable(); });
  }
  return area;
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
  // The type of point a click on a leg inserts: a secret gate, unless a wizard step asks for another (a known time gate)
  legInsertType: RoutePoint['type'] | null = null,
  // Dragging the dot of a leg inserts a point and then moves it: one gesture, one undo step
  onGestureStart?: () => void,
  // A click that cannot place the point it was meant for: the editor says why
  onNotice?: (message: string) => void,
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
      latlngs.push(...greatCircleLatLngs(previous, point));
      continue;
    }

    if (point.segmentType === 'curved' && hasControl(point)) {
      const curvePoints = getQuadraticBezierPoints(previous, point, { lat: point.controlLat, lng: point.controlLng });
      latlngs.push(...curvePoints);
    } else {
      latlngs.push(...greatCircleLatLngs(previous, point));
    }
  }

  const polyline = L.polyline(latlngs, {
    color: '#3b82f6',
    weight: 4,
  }).addTo(map);

  polyline.on('click', (e: L.LeafletMouseEvent) => {
    // A click on a leg places a point only when the hidden gate tool (or a guide step) says so; otherwise it is a click
    // on the map
    const action = legClickAction(routePoints, { lat: e.latlng.lat, lng: e.latlng.lng }, legInsertType);
    if (action.kind === 'none') return;
    stopMapEvent(e);
    if (action.kind === 'notice') {
      onNotice?.(action.message);
      return;
    }
    // The tool stays active for the next one: the new gate is not selected (that would replace the guide's panel)
    if (action.point.type === 'secret') pulsingGate = { id: action.point.id, until: Date.now() + HIDDEN_GATE_PULSE_MS };
    setRoutePoints(prev => applyLegInsert(prev, action));
  });

  // The dots are for dragging a new waypoint out of a leg; not while a click on a leg places a hidden gate
  if (mode === 'view' && !legInsertType) {
    for (let i = 0; i < routePoints.length - 1; i++) {
      const p1 = routePoints[i];
      const p2 = routePoints[i + 1];
      if (p2.segmentType === 'curved') continue;

      // Halfway along the leg as drawn: on the great circle, not at the average of the coordinates
      const middle = getIntermediatePoint(p1, p2, 0.5);
      const mid = L.latLng(middle.lat, middle.lng);
      const ghost = L.circleMarker(mid, {
        radius: 7,
        color: '#3b82f6',
        fillColor: '#3b82f6',
        opacity: 0.7,
        fillOpacity: 0.5,
        weight: 1,
        className: 'cursor-copy',
      }).addTo(map);

      ghost.bindTooltip('Drag to add a waypoint here', { direction: 'top' });
      ghost.on('mousedown', (e: L.LeafletMouseEvent) => {
        stopMapEvent(e);
        const pressed = e.containerPoint;

        // Nothing is inserted until the pointer has moved past the threshold: a press and release does nothing but hint.
        // The release is watched on the document (it can come outside the map), and the wait ends with the dot: any change
        // of the route redraws it, so what is inserted into is always the route as the dot was drawn for.
        const stopWaiting = () => {
          map.off('mousemove', onMoveOrRelease);
          document.removeEventListener('mouseup', onRelease, true);
          ghost.off('remove', stopWaiting);
        };
        const onRelease = () => {
          stopWaiting();
          onNotice?.(MID_LEG_DOT_HINT);
        };
        const onMoveOrRelease = (move: L.LeafletMouseEvent) => {
          const buttons = (move.originalEvent as MouseEvent | undefined)?.buttons;
          if (buttons !== undefined && (buttons & 1) === 0) {
            // The button was let go without us seeing it
            stopWaiting();
            return;
          }
          if (!hasDraggedPastThreshold(pressed, move.containerPoint)) return;
          stopWaiting();
          onGestureStart?.();

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
        };
        map.on('mousemove', onMoveOrRelease);
        document.addEventListener('mouseup', onRelease, true);
        ghost.on('remove', stopWaiting);
      });

      polylinesRef.current.push(ghost);
    }
  }

  routeLineRef.current = polyline;
  polylinesRef.current.push(polyline);

  branchLineGroups.forEach((group) => {
    // A curved extension leg (segmentType curved on its end point) follows its curve, like a curved route leg
    const branchLatLngs: L.LatLng[] = [];
    group.points.forEach((point, index) => {
      const previous = group.points[index - 1];
      if (previous && point.segmentType === 'curved' && hasControl(point)) {
        branchLatLngs.push(...getQuadraticBezierPoints(previous, point, { lat: point.controlLat, lng: point.controlLng }));
      } else {
        branchLatLngs.push(L.latLng(point.lat, point.lng));
      }
    });
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

      if (p2.segmentType === 'curved' && hasControl(p2)) {
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
  options: {
    activeTriggerId?: string | null;
    emphasizeUnknownLegTriggers?: boolean;
    // Where a point's leg starts (for the curve handle), when that is not the point before it in the list: a
    // dummy-branch waypoint's leg starts at the previous waypoint on its branch
    previousOf?: (point: RoutePoint, index: number) => RoutePoint | undefined;
    // Where the points' hit areas are registered (see HitRegistry)
    hits?: HitRegistry;
  } = {},
) => {
  const hits = options.hits ?? createHitRegistry(map);
  const previousOf = options.previousOf ?? ((_point: RoutePoint, index: number) => routePoints[index - 1]);
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

    // The mark is drawn here; the clicks and drags go to the larger invisible hit area over it.
    L.circleMarker([p.lat, p.lng], {
      radius: style.radius,
      fillColor: style.color,
      color: '#fff',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.8,
      interactive: false,
      className: pulseClassFor(p.id),
    }).addTo(pointGroup);

    addHitArea(hits, pointGroup, {
      key: `point-${p.id}`,
      kind: pointSelectionType === 'standalone_point' ? 'standalone_point' : 'point',
      latlng: L.latLng(p.lat, p.lng),
      select: () => {
        if (setSelectedId) setSelectedId(p.id);
        if (setSelectionType) setSelectionType(pointSelectionType);
        if (setMode && !(options.emphasizeUnknownLegTriggers && p.type === UNKNOWN_LEG_TRIGGER_TYPE)) setMode('view');
      },
      // A secret gate is not dragged: it sits on its leg
      startDrag: p.type === 'secret'
        ? undefined
        : (e: L.LeafletMouseEvent) => {
          if (mode !== 'view') return;
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
        },
    }, {
      tooltip: { text: getPointTooltipLabel(p, index), options: { permanent: !hideLabels, direction: 'right', offset: [10, 0] } },
      lockMapWhileHovered: { mode, dragRef },
    });

    markersRef.current[`point-${p.id}`] = pointGroup;

    const prev = previousOf(p, index);
    if (selectedId === p.id && p.segmentType === 'curved' && prev && hasControl(p)) {
      const controlLatLng: L.LatLngTuple = [p.controlLat, p.controlLng];

      const dashLine = L.polyline([[prev.lat, prev.lng], controlLatLng, [p.lat, p.lng]], {
        color: '#64748b', weight: 1, dashArray: '4, 4',
      }).addTo(map);
      markersRef.current[`curve-dash-${p.id}`] = dashLine;

      const controlHandle = L.circleMarker(controlLatLng, {
        radius: 5, color: '#64748b', fillColor: '#fff', fillOpacity: 1, className: 'cursor-move',
      }).addTo(map);

      controlHandle.on('click', (e: L.LeafletMouseEvent) => stopMapEvent(e));
      controlHandle.on('mousedown', (e: L.LeafletMouseEvent) => {
        if (mode !== 'view') return;
        stopMapEvent(e);
        map.dragging.disable();
        dragRef.current = {
          type: 'curve_control',
          id: p.id,
          index,
          startLatLng: e.latlng,
          initialPoints: routePoints,
          hasMoved: false,
          selectionType: pointSelectionType,
          previous: prev,
        };
        map.on('mousemove', handleDragMove);
        map.on('mouseup', handleDragEnd);
      });

      markersRef.current[`curve-handle-${p.id}`] = controlHandle;
    }
  });
};

export const drawGates = (map: L.Map, gates: Gate[], polylinesRef: React.MutableRefObject<L.Layer[]>, setSelectedId: (id: string | null) => void, setSelectionType: (type: SelectionType | null) => void, setMode: (mode: Mode) => void, hideLabels: boolean, hits: HitRegistry = createHitRegistry(map)) => {
  gates.forEach(g => {
    const color = g.type === 'landing' ? '#8b5cf6' : '#f59e0b';
    const line = L.polyline([[g.p1.lat, g.p1.lng], [g.p2.lat, g.p2.lng]], {
      color: color,
      weight: 6,
      dashArray: '10, 10',
    }).addTo(map);

    line.bindTooltip(g.name, { permanent: !hideLabels, direction: 'center', className: 'bg-transparent border-0 shadow-none text-black font-bold' });

    line.on('click', (e) => {
      stopMapEvent(e);
      setSelectedId(g.id);
      setSelectionType('gate');
      setMode('view');
    });

    polylinesRef.current.push(line);

    // The end points of the line have a hit area too, so a click near one selects the gate
    [g.p1, g.p2].forEach((end, endIndex) => {
      const area = addHitArea(hits, map, {
        key: `gate-${g.id}-${endIndex}`,
        kind: 'gate',
        latlng: L.latLng(end.lat, end.lng),
        select: () => {
          setSelectedId(g.id);
          setSelectionType('gate');
          setMode('view');
        },
      });
      polylinesRef.current.push(area);
    });
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
  hits: HitRegistry = createHitRegistry(map),
  onGestureStart?: () => void,
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
      stopMapEvent(e);
      // The click that ends a drag of the zone is not a click on it
      if (dragRef.current?.hasMoved) return;

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

    // Dragging the zone moves all of it
    polygonLayer.on('mousedown', (e: L.LeafletMouseEvent) => {
      if (mode !== 'view') return;
      stopMapEvent(e);
      map.dragging.disable();
      dragRef.current = {
        type: 'poly_body',
        polyId: poly.id,
        startLatLng: e.latlng,
        initialPoints: poly.points,
        hasMoved: false,
      };
      map.on('mousemove', handleDragMove);
      map.on('mouseup', handleDragEnd);
    });

    markersRef.current[`poly-${poly.id}`] = polygonLayer;

    if (selectedId === poly.id && selectionType === 'polygon') {
      drawPolygonHandles(map, poly, color, mode, markersRef, dragRef, handleDragMove, handleDragEnd, setPolygons, {
        hits,
        onGestureStart,
        select: () => {
          setSelectedId(poly.id);
          setSelectionType('polygon');
          setMode('view');
        },
      });
    }
  });
};

/**
 * The selected zone's editing handles, like the route's: a handle on each corner to drag, and (in view mode) a fainter
 * dot halfway along each edge that adds a corner there when grabbed and drags it straight away.
 */
export const drawPolygonHandles = (
  map: L.Map,
  poly: Polygon,
  color: string,
  mode: Mode,
  markersRef: React.MutableRefObject<{ [key: string]: L.Layer }>,
  dragRef: React.MutableRefObject<any>,
  handleDragMove: (e: L.LeafletMouseEvent) => void,
  handleDragEnd: (e: L.LeafletMouseEvent) => void,
  setPolygons: React.Dispatch<React.SetStateAction<Polygon[]>>,
  options: {
    hits?: HitRegistry;
    // Dragging a new corner out of an edge dot is one gesture (inserted, then moved)
    onGestureStart?: () => void;
    // What a click on a corner does (the zone is selected already; this keeps the click off the map)
    select?: () => void;
  } = {},
) => {
  const hits = options.hits ?? createHitRegistry(map);
  poly.points.forEach((pt, idx) => {
    // The mark is drawn here; the grab goes to the larger invisible hit area over it (the one in markersRef, which the
    // drag handlers find by key; the mark follows it under its own key).
    const mark = L.circleMarker([pt.lat, pt.lng], {
      radius: 6,
      color: 'white',
      fillColor: color,
      fillOpacity: 1,
      weight: 2,
      interactive: false,
    }).addTo(map);
    markersRef.current[`poly-mark-${poly.id}-${idx}`] = mark;

    const area = addHitArea(hits, map, {
      key: `poly-handle-${poly.id}-${idx}`,
      kind: 'polygon_vertex',
      latlng: L.latLng(pt.lat, pt.lng),
      select: () => options.select?.(),
      startDrag: (e: L.LeafletMouseEvent) => {
        if (mode !== 'view') return;
        map.dragging.disable();
        dragRef.current = {
          type: 'poly_vertex',
          polyId: poly.id,
          vertexIndex: idx,
          startLatLng: e.latlng,
          hasMoved: false,
        };
        map.on('mousemove', handleDragMove);
        map.on('mouseup', handleDragEnd);
      },
    });
    markersRef.current[`poly-handle-${poly.id}-${idx}`] = area;
  });

  if (mode !== 'view') return;
  poly.points.forEach((pt, idx) => {
    const nextPt = poly.points[(idx + 1) % poly.points.length];
    const mid = L.latLng((pt.lat + nextPt.lat) / 2, (pt.lng + nextPt.lng) / 2);

    const ghost = L.circleMarker(mid, {
      radius: 6,
      color: 'white',
      fillColor: color,
      opacity: 0.7,
      fillOpacity: 0.5,
      weight: 1,
      className: 'cursor-copy',
    }).addTo(map);

    ghost.on('mousedown', (e: L.LeafletMouseEvent) => {
      stopMapEvent(e);
      options.onGestureStart?.();

      const nextPoints = [...poly.points];
      nextPoints.splice(idx + 1, 0, { lat: mid.lat, lng: mid.lng });
      setPolygons((prev) => prev.map((p) => (p.id === poly.id ? { ...p, points: nextPoints } : p)));

      // Start dragging the new corner immediately
      map.dragging.disable();
      dragRef.current = {
        type: 'poly_vertex',
        polyId: poly.id,
        vertexIndex: idx + 1,
        startLatLng: e.latlng,
        initialPoints: nextPoints,
        hasMoved: true,
      };
      map.on('mousemove', handleDragMove);
      map.on('mouseup', handleDragEnd);
    });

    markersRef.current[`poly-ghost-${poly.id}-${idx}`] = ghost;
  });
};
