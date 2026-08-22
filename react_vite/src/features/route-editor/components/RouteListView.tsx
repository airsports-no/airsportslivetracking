import React from 'react';
import { AlertTriangle, CheckCircle, Camera, Hexagon, Clock, Crosshair, Ruler } from 'lucide-react';
import { RoutePoint, Gate, ObservationMarker, Polygon, SelectionType } from '../../../types';

interface RouteListViewProps {
    routePoints: RoutePoint[];
    standalonePoints: RoutePoint[];
    gates: Gate[];
    observationMarkers: ObservationMarker[];
    polygons: Polygon[];
    validationErrors: string[];
    onSelect: (id: string, type: SelectionType) => void;
}

const RouteListView: React.FC<RouteListViewProps> = ({ 
  routePoints, 
  standalonePoints,
  gates, 
  observationMarkers, 
  polygons,
  validationErrors, 
  onSelect 
}) => {
  const orderedRoutePoints = routePoints.filter((p) => (p.featureType || 'route_waypoint') === 'route_waypoint');
  const unknownLegTriggerOptions = orderedRoutePoints.filter((p) => p.type === 'ul');
  const dummyBranchPoints = standalonePoints.filter((p) => p.featureType === 'dummy_branch_waypoint');
  const catalogueTurnpoints = standalonePoints.filter((p) => p.featureType === 'catalogue_turnpoint');
  const timedTurnpoints = standalonePoints.filter((p) => p.type === 'timed_turnpoint');
  const circleMarkers = standalonePoints.filter((p) => (
    p.featureType === 'circle_center_marker'
    || p.featureType === 'circle_start_marker'
    || p.featureType === 'circle_entry_marker'
    || p.featureType === 'circle_exit_marker'
  ));

  const getStandaloneBadge = (point: RoutePoint) => {
    switch (point.featureType) {
      case 'circle_center_marker':
        return 'center';
      case 'circle_start_marker':
        return 'start';
      case 'circle_entry_marker':
        return 'entry';
      case 'circle_exit_marker':
        return 'exit';
      default:
        return point.type;
    }
  };

  return (
    <div className="space-y-6">
      <div className={`alert ${validationErrors.length > 0 ? 'alert-warning' : 'alert-success'} shadow-sm text-sm py-2`}>
        <div className="flex items-center space-x-2 mb-2">
          {validationErrors.length > 0 ? (
            <AlertTriangle className="text-amber-500" size={20} />
          ) : (
            <CheckCircle className="text-green-500" size={20} />
          )}
          <h3 className={`font-semibold ${validationErrors.length > 0 ? 'text-amber-800' : 'text-green-800'}`}>
            {validationErrors.length > 0 ? "Route Issues" : "Route Valid"}
          </h3>
        </div>
        {validationErrors.length > 0 && (
          <ul className="list-disc pl-5 text-xs text-amber-800 space-y-1">
            {validationErrors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-bold text-gray-500 uppercase">Route Backbone</h3>
        </div>
        {orderedRoutePoints.length === 0 ? (
          <p className="text-sm text-gray-400 italic">No route backbone points added yet.</p>
        ) : (
          <ul className="space-y-1">
            {orderedRoutePoints.map((p, i) => (
              <li 
                key={p.id} 
                className="flex items-center justify-between p-2 bg-base-100 border rounded hover:bg-base-200 cursor-pointer text-sm gap-2"
                onClick={() => onSelect(p.id, 'point')}
              >
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <span className="font-mono text-[10px] w-4 opacity-50 flex-shrink-0 text-right">{i + 1}</span>
                  <span className="font-medium truncate" title={p.name}>{p.name}</span>
                  <div className="flex items-center gap-1 flex-shrink-0 opacity-70 border-l pl-1 border-base-300 ml-1">
                    {p.isTiming && <Clock size={11} className="text-primary" />}
                    {p.isPassing && <Crosshair size={11} className="text-secondary" />}
                    <Ruler size={11} />
                    <span className="text-[9px] font-bold">{(p.width / 1852).toFixed(1)}NM</span>
                  </div>
                </div>
                <span className={`badge badge-sm flex-shrink-0 uppercase text-[9px] h-4 leading-none font-bold ${
                  (p.type === 'sp') ? 'badge-success' :
                  (p.type === 'fp') ? 'badge-error' :
                  p.type === 'secret' ? 'badge-ghost' :
                  p.type === 'hidden_gate' ? 'badge-warning' :
                  p.type === 'ul' ? 'badge-accent' :
                  p.type === 'known_time_gate' ? 'badge-primary' :
                  'badge-info'
                }`}>
                  {p.type}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h3 className="text-xs font-bold text-gray-500 uppercase mb-2">Dummy Branches</h3>
        {dummyBranchPoints.length === 0 ? (
          <p className="text-sm text-gray-400 italic">No dummy-branch waypoints.</p>
        ) : (
          <ul className="space-y-1">
            {dummyBranchPoints.map((p) => (
              <li
                key={p.id}
                className="p-2 bg-base-100 border rounded hover:bg-base-200 cursor-pointer text-sm space-y-1"
                onClick={() => onSelect(p.id, 'standalone_point')}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium truncate" title={p.name}>{p.name}</span>
                  <span className="badge badge-sm badge-neutral uppercase text-[9px] h-4 leading-none font-bold">dummy</span>
                </div>
                <div className="text-[11px] text-gray-500">
                  Trigger {(unknownLegTriggerOptions.find((trigger) => trigger.id === p.triggerPointId)?.name) || p.triggerPointId || 'unassigned'} · branch step {(p.branchSequence ?? 0) + 1}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h3 className="text-xs font-bold text-gray-500 uppercase mb-2">Timed Turnpoints</h3>
        {timedTurnpoints.length === 0 ? (
          <p className="text-sm text-gray-400 italic">No timed turnpoints.</p>
        ) : (
          <ul className="space-y-1">
            {timedTurnpoints.map((p) => (
              <li
                key={p.id}
                className="p-2 bg-base-100 border rounded hover:bg-base-200 cursor-pointer text-sm space-y-1"
                onClick={() => onSelect(p.id, 'standalone_point')}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium truncate" title={p.name}>{p.name}</span>
                  <span className="badge badge-sm badge-primary uppercase text-[9px] h-4 leading-none font-bold">timed</span>
                </div>
                <div className="text-[11px] text-gray-500">Crossing time declared per contestant</div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h3 className="text-xs font-bold text-gray-500 uppercase mb-2">Catalogue Turnpoints</h3>
        {catalogueTurnpoints.length === 0 ? (
          <p className="text-sm text-gray-400 italic">No catalogue turnpoints.</p>
        ) : (
          <ul className="space-y-1">
            {catalogueTurnpoints.map((p) => (
              <li 
                key={p.id}
                className="p-2 bg-base-100 border rounded hover:bg-base-200 cursor-pointer text-sm space-y-1"
                onClick={() => onSelect(p.id, 'standalone_point')}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium truncate" title={p.name}>{p.name}</span>
                  <span className="badge badge-sm badge-secondary uppercase text-[9px] h-4 leading-none font-bold">catalogue</span>
                </div>
                <div className="text-[11px] text-gray-500">
                  {p.scoreValue != null ? `Score ${p.scoreValue}` : 'No score value'}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h3 className="text-xs font-bold text-gray-500 uppercase mb-2">Circle Markers</h3>
        {circleMarkers.length === 0 ? (
          <p className="text-sm text-gray-400 italic">No circle markers.</p>
        ) : (
          <ul className="space-y-1">
            {circleMarkers.map((p) => (
              <li
                key={p.id}
                className="p-2 bg-base-100 border rounded hover:bg-base-200 cursor-pointer text-sm space-y-1"
                onClick={() => onSelect(p.id, 'standalone_point')}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium truncate" title={p.name}>{p.name}</span>
                  <span className="badge badge-sm badge-accent uppercase text-[9px] h-4 leading-none font-bold">{getStandaloneBadge(p)}</span>
                </div>
                <div className="text-[11px] text-gray-500">{p.featureType?.replace('_marker', '').replaceAll('_', ' ')}</div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h3 className="text-xs font-bold text-gray-500 uppercase mb-2">Auxiliary Gates</h3>
        {gates.length === 0 ? (
          <p className="text-sm text-gray-400 italic">No landing/takeoff gates.</p>
        ) : (
          <ul className="space-y-1">
            {gates.map((g) => (
              <li 
                key={g.id} 
                className="flex items-center justify-between p-2 bg-base-100 border rounded hover:bg-base-200 cursor-pointer text-sm"
                onClick={() => onSelect(g.id, 'gate')}
              >
                <span className="font-medium">{g.name}</span>
                <span className={`badge badge-sm ${
                  g.type === 'landing' ? 'badge-primary' : 'badge-warning'
                }`}>
                  {g.type}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h3 className="text-xs font-bold text-gray-500 uppercase mb-2">Observation Photos</h3>
        {observationMarkers.length === 0 ? (
          <p className="text-sm text-gray-400 italic">No observation markers.</p>
        ) : (
          <ul className="space-y-1">
            {observationMarkers.map((m) => (
              <li 
                key={m.id} 
                className="flex items-center justify-between p-2 bg-base-100 border rounded hover:bg-base-200 cursor-pointer text-sm"
                onClick={() => onSelect(m.id, 'observation')}
              >
                <div className="min-w-0">
                  <div className="font-medium truncate">{m.name}</div>
                  {m.targetName && <div className="text-[11px] text-gray-500 truncate">Target: {m.targetName}</div>}
                </div>
                <Camera size={14} className="text-yellow-600 flex-shrink-0" />
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h3 className="text-xs font-bold text-gray-500 uppercase mb-2">Zones</h3>
        {(!polygons || polygons.length === 0) ? (
          <p className="text-sm text-gray-400 italic">No zones defined.</p>
        ) : (
          <ul className="space-y-1">
            {polygons.map((p) => (
              <li 
                key={p.id} 
                className="flex items-center justify-between p-2 bg-base-100 border rounded hover:bg-base-200 cursor-pointer text-sm"
                onClick={() => onSelect(p.id, 'polygon')}
              >
                <span className="font-medium">{p.name}</span>
                <span className={`badge badge-sm ${
                  p.type === 'prohibited' ? 'badge-error' :
                  p.type === 'penalty' ? 'badge-warning' :
                  p.type === 'duration_landing_area' ? 'badge-success' :
                  'badge-info'
                }`}>
                  {p.type}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default RouteListView;
