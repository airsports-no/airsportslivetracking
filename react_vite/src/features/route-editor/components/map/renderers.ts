import L from 'leaflet';
import {
  getDistance,
  getBearing,
  getDestinationPoint,
  getDistanceFromLine,
  isPointInPolygon,
  getQuadraticBezierPoints
} from '../../../../utils/geoUtils';
import { RoutePoint, Gate, Polygon, Mode, SelectionType } from '../../../../types';

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
  routeLineRef: React.MutableRefObject<L.Polyline | null>, 
  polylinesRef: React.MutableRefObject<L.Layer[]>, 
  mode: Mode, 
  setRoutePoints: React.Dispatch<React.SetStateAction<RoutePoint[]>>, 
  setSelectedId: (id: string | null) => void, 
  setSelectionType: (type: SelectionType | null) => void, 
  hideLabels: boolean,
  dragRef: React.MutableRefObject<any>,
  handleDragMove: (e: L.LeafletMouseEvent) => void,
  handleDragEnd: (e: L.LeafletMouseEvent) => void
) => {
  if (routePoints.length <= 1) return;

  const latlngs: L.LatLng[] = [];
  routePoints.forEach((p, i) => {
    if (i === 0) {
      latlngs.push(L.latLng(p.lat, p.lng));
    } else {
      if (p.segmentType === 'curved' && p.controlLat && p.controlLng) {
        const prev = routePoints[i - 1];
        const curvePoints = getQuadraticBezierPoints(prev, p, { lat: p.controlLat, lng: p.controlLng });
        latlngs.push(...curvePoints);
      } else {
        latlngs.push(L.latLng(p.lat, p.lng));
      }
    }
  });

  const polyline = L.polyline(latlngs, { 
    color: '#3b82f6', 
    weight: 4,
    className: mode === 'view' ? 'cursor-crosshair' : '' 
  }).addTo(map);

  // Handle clicks on the line (to add Secret Points)
  polyline.on('click', (e: L.LeafletMouseEvent) => {
    if (mode !== 'view') return;
    L.DomEvent.stopPropagation(e.originalEvent);

    const clickPt = { lat: e.latlng.lat, lng: e.latlng.lng };
    let bestIndex = -1;
    let minDistance = Infinity;

    // Find closest segment
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

      // Project point to line
      const bearing = getBearing(p1, p2);
      const dist = getDistance(p1, clickPt);
      const newLoc = getDestinationPoint(p1, dist, bearing);

      const newPoint: RoutePoint = {
        id: crypto.randomUUID(),
        lat: newLoc.lat,
        lng: newLoc.lng,
        name: `Secret ${routePoints.length}`,
        type: 'secret',
        width: 1000,
        isTiming: false,
        isPassing: true,
        segmentType: 'straight'
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

  // Draw Ghost Points
  if (mode === 'view') {
    for (let i = 0; i < routePoints.length - 1; i++) {
      const p1 = routePoints[i];
      const p2 = routePoints[i + 1];
      if (p2.segmentType === 'curved') continue; // Skip curved segments for now to keep it simple

      const mid = L.latLng((p1.lat + p2.lat) / 2, (p1.lng + p2.lng) / 2);
      const ghost = L.circleMarker(mid, {
        radius: 7,
        color: '#3b82f6',
        fillColor: '#3b82f6',
        opacity: 0.7,
        fillOpacity: 0.5,
        weight: 1,
        className: 'cursor-copy'
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
          segmentType: 'straight'
        };

        const nextPoints = [...routePoints];
        nextPoints.splice(i + 1, 0, newPoint);

        setRoutePoints(nextPoints);
        
        // Start dragging immediately
        map.dragging.disable();
        dragRef.current = {
          type: 'point',
          id: newPoint.id,
          index: i + 1,
          startLatLng: e.latlng,
          initialPoints: nextPoints,
          hasMoved: true
        };
        map.on('mousemove', handleDragMove);
        map.on('mouseup', handleDragEnd);
      });

      polylinesRef.current.push(ghost);
    }
  }

  routeLineRef.current = polyline;
  polylinesRef.current.push(polyline);

  // Draw Segment Lengths
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
          html: `<div class="transform -translate-x-1/2 -translate-y-[calc(50%+12px)] bg-white/75 backdrop-blur-[1px] px-1 rounded border border-slate-300 text-[10px] font-bold text-slate-600 shadow-sm whitespace-nowrap pointer-events-none w-max">${nm} NM</div>`
        }),
        interactive: false
      }).addTo(map);
      polylinesRef.current.push(labelMarker);
    }
  }
};

export const drawPoints = (map: L.Map, routePoints: RoutePoint[], mode: Mode, selectedId: string | null, markersRef: React.MutableRefObject<{ [key: string]: L.Layer }>, dragRef: React.MutableRefObject<any>, handleDragMove: (e: L.LeafletMouseEvent) => void, handleDragEnd: (e: L.LeafletMouseEvent) => void, hideLabels: boolean) => {
  routePoints.forEach((p, index) => {
    let color = '#3b82f6'; // Default Blue
    let radius = 6;

    if (p.type === 'sp') { color = '#22c55e'; radius = 8; }
    if (p.type === 'fp') { color = '#ef4444'; radius = 8; }
    if (p.type === 'secret') { color = '#64748b'; }

    const pointGroup = L.featureGroup().addTo(map);

    // Width Circle
    if (p.width > 0) {
      L.circle([p.lat, p.lng], {
        radius: p.width / 2,
        color: color,
        weight: 1,
        fillColor: color,
        fillOpacity: 0.15,
        dashArray: '4, 4',
        interactive: false
      }).addTo(pointGroup);
    }

    // The Marker
    const marker = L.circleMarker([p.lat, p.lng], {
      radius: radius,
      fillColor: color,
      color: '#fff',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.8,
      className: p.type === 'secret' ? '' : 'cursor-grab'
    }).addTo(pointGroup);

    marker.bindTooltip(`${index + 1}. ${p.name}`, { permanent: !hideLabels, direction: 'right', offset: [10, 0] });

    marker.on('click', (e: L.LeafletMouseEvent) => L.DomEvent.stopPropagation(e.originalEvent || e));
    marker.on('mouseover', () => { if (mode === 'view') map.dragging.disable(); });
    marker.on('mouseout', () => { if (mode === 'view' && !dragRef.current) map.dragging.enable(); });

    marker.on('mousedown', (e: L.LeafletMouseEvent) => {
      if (mode !== 'view') return;
      if (p.type === 'secret') return;

      L.DomEvent.stopPropagation(e.originalEvent);
      map.dragging.disable();
      dragRef.current = { type: 'point', id: p.id, index, startLatLng: e.latlng, initialPoints: routePoints, hasMoved: false };
      map.on('mousemove', handleDragMove);
      map.on('mouseup', handleDragEnd);
    });

    markersRef.current[`point-${p.id}`] = pointGroup;

    // Curve Controls
    if (selectedId === p.id && p.segmentType === 'curved' && index > 0 && p.controlLat && p.controlLng) {
      const prev = routePoints[index - 1];
      const controlLatLng: L.LatLngTuple = [p.controlLat, p.controlLng];

      const dashLine = L.polyline([[prev.lat, prev.lng], controlLatLng, [p.lat, p.lng]], {
        color: '#64748b', weight: 1, dashArray: '4, 4'
      }).addTo(map);
      markersRef.current[`curve-dash-${p.id}`] = dashLine;

      const controlHandle = L.circleMarker(controlLatLng, {
        radius: 5, color: '#64748b', fillColor: '#fff', fillOpacity: 1, className: 'cursor-move'
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
          hasMoved: false
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
      dashArray: '10, 10'
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
  setPolygons: React.Dispatch<React.SetStateAction<Polygon[]>>
) => {
  polygons.forEach(poly => {
    let color = '#3b82f6';
    if (poly.type === 'prohibited') color = '#ef4444';
    if (poly.type === 'penalty') color = '#f97316';
    if (poly.type === 'waypoint') color = '#a855f7';

    const polygonLayer = L.polygon(poly.points.map(p => [p.lat, p.lng]), {
      color: color,
      weight: 2,
      fillColor: color,
      fillOpacity: 0.2,
      className: mode === 'view' ? 'cursor-move' : ''
    }).addTo(map);

    polygonLayer.bindTooltip(poly.name, {
      permanent: !hideLabels,
      direction: 'center',
      className: `bg-transparent border-0 shadow-none font-bold `
    });

    polygonLayer.on('click', (e: L.LeafletMouseEvent) => {
      if (mode !== 'view') return;
      L.DomEvent.stopPropagation(e.originalEvent);

      // If not already selected, select it
      if (selectedId !== poly.id) {
        setSelectedId(poly.id);
        setSelectionType('polygon');
        return;
      }

      // If already selected, check if we clicked near an edge to add a vertex
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

      if (bestIndex !== -1 && minDistance < 50) { // 50 meters tolerance
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
      }
    });

    // Body Drag
    polygonLayer.on('mousedown', (e: L.LeafletMouseEvent) => {
      if (mode !== 'view') return;
      L.DomEvent.stopPropagation(e.originalEvent);
      map.dragging.disable();
      dragRef.current = {
        type: 'poly_body',
        polyId: poly.id,
        startLatLng: e.latlng,
        initialPoints: poly.points,
        hasMoved: false
      };
      map.on('mousemove', handleDragMove);
      map.on('mouseup', handleDragEnd);
    });

    markersRef.current[`poly-${poly.id}`] = polygonLayer;

    // Vertex Handles
    if (selectedId === poly.id && selectionType === 'polygon') {
      poly.points.forEach((pt, idx) => {
        const handle = L.circleMarker([pt.lat, pt.lng], {
          radius: 5, color: 'white', fillColor: color, fillOpacity: 1, weight: 2, className: 'cursor-grab'
        }).addTo(map);

        markersRef.current[`poly-handle-${poly.id}-${idx}`] = handle;

        handle.on('mousedown', (e: L.LeafletMouseEvent) => {
          if (mode !== 'view') return;
          L.DomEvent.stopPropagation(e.originalEvent);
          map.dragging.disable();
          dragRef.current = {
            type: 'poly_vertex',
            polyId: poly.id,
            vertexIndex: idx,
            startLatLng: e.latlng,
            hasMoved: false
          };
          map.on('mousemove', handleDragMove);
          map.on('mouseup', handleDragEnd);
        });
      });

      // Ghost Points for Polygon Segments
      if (mode === 'view') {
        poly.points.forEach((pt, idx) => {
          const nextPt = poly.points[(idx + 1) % poly.points.length];
          const mid = L.latLng((pt.lat + nextPt.lat) / 2, (pt.lng + nextPt.lng) / 2);

          const ghost = L.circleMarker(mid, {
            radius: 4,
            color: 'white',
            fillColor: color,
            opacity: 0.6,
            fillOpacity: 0.4,
            weight: 1,
            className: 'cursor-copy'
          }).addTo(map);

          ghost.on('mousedown', (e: L.LeafletMouseEvent) => {
            L.DomEvent.stopPropagation(e.originalEvent);

            const nextPoints = [...poly.points];
            nextPoints.splice(idx + 1, 0, { lat: mid.lat, lng: mid.lng } as any);

            setPolygons(prev => prev.map(p => {
              if (p.id !== poly.id) return p;
              return { ...p, points: nextPoints };
            }));

            // Start dragging immediately
            map.dragging.disable();
            dragRef.current = {
              type: 'poly_vertex',
              polyId: poly.id,
              vertexIndex: idx + 1,
              startLatLng: e.latlng,
              initialPoints: nextPoints,
              hasMoved: true
            };
            map.on('mousemove', handleDragMove);
            map.on('mouseup', handleDragEnd);
          });

          markersRef.current[`poly-ghost-${poly.id}-${idx}`] = ghost;
        });
      }
    }
  });
};