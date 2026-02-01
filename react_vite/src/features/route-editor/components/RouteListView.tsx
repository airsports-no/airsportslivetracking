import React from 'react';
import { AlertTriangle, CheckCircle, Camera, Hexagon } from 'lucide-react';
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
  return (
    <div className="space-y-6">
      {/* Validation Status */}
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

      {/* Route List */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-bold text-gray-500 uppercase">Route Sequence</h3>
        </div>
        {routePoints.length === 0 ? (
          <p className="text-sm text-gray-400 italic">No points added yet.</p>
        ) : (
          <ul className="space-y-1">
            {routePoints.map((p, i) => (
              <li 
                key={p.id} 
                className="flex items-center justify-between p-2 bg-base-100 border rounded hover:bg-base-200 cursor-pointer text-sm"
                onClick={() => onSelect(p.id, 'point')}
              >
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-xs w-5">{i+1}</span>
                  <span className="font-medium truncate max-w-[120px]">{p.name}</span>
                </div>
                <span className={`badge badge-sm ${
                  (p.type === 'sp') ? 'badge-success' :
                  (p.type === 'fp') ? 'badge-error' :
                  p.type === 'secret' ? 'badge-ghost' : 'badge-info'
                }`}>
                  {p.type}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Standalone CIMA Waypoints */}
      <div>
        <h3 className="text-xs font-bold text-gray-500 uppercase mb-2">Standalone CIMA Waypoints</h3>
        {standalonePoints.length === 0 ? (
          <p className="text-sm text-gray-400 italic">No free points or circles.</p>
        ) : (
          <ul className="space-y-1">
            {standalonePoints.map((p) => (
              <li 
                key={p.id} 
                className="flex items-center justify-between p-2 bg-base-100 border rounded hover:bg-base-200 cursor-pointer text-sm"
                onClick={() => onSelect(p.id, 'point')}
              >
                <span className="font-medium">{p.name}</span>
                <span className={`badge badge-sm ${
                  p.type === 'free_point' ? 'badge-info' : 'badge-secondary'
                }`}>
                  {p.type === 'free_point' ? 'Free Point' : 'Circle'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Gates List */}
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

      {/* Observation Markers List */}
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
                <span className="font-medium">{m.name}</span>
                <Camera size={14} className="text-yellow-600" />
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Polygons List */}
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
                  p.type === 'waypoint' ? 'badge-secondary' :
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