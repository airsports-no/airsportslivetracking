import React from 'react';
import { AlertTriangle, CheckCircle, Camera, Hexagon } from 'lucide-react';

const RouteListView = ({ 
  routePoints, 
  gates, 
  observationMarkers, 
  polygons,
  validationErrors, 
  onSelect 
}) => {
  return (
    <div className="space-y-6">
      {/* Validation Status */}
      <div className={`p-3 rounded-lg border ${validationErrors.length > 0 ? 'bg-amber-50 border-amber-200' : 'bg-green-50 border-green-200'}`}>
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
                className="flex items-center justify-between p-2 bg-white border rounded hover:bg-gray-50 cursor-pointer text-sm"
                onClick={() => onSelect(p.id, 'point')}
              >
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-xs w-5">{i+1}</span>
                  <span className="font-medium truncate max-w-[120px]">{p.name}</span>
                </div>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                  (p.type === 'sp') ? 'bg-green-100 text-green-700' :
                  (p.type === 'fp') ? 'bg-red-100 text-red-700' :
                  p.type === 'secret' ? 'bg-gray-100 text-gray-700' : 'bg-blue-100 text-blue-700'
                }`}>
                  {p.type}
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
                className="flex items-center justify-between p-2 bg-white border rounded hover:bg-gray-50 cursor-pointer text-sm"
                onClick={() => onSelect(g.id, 'gate')}
              >
                <span className="font-medium">{g.name}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                  g.type === 'landing' ? 'bg-purple-100 text-purple-700' : 'bg-orange-100 text-orange-700'
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
                className="flex items-center justify-between p-2 bg-white border rounded hover:bg-gray-50 cursor-pointer text-sm"
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
                className="flex items-center justify-between p-2 bg-white border rounded hover:bg-gray-50 cursor-pointer text-sm"
                onClick={() => onSelect(p.id, 'polygon')}
              >
                <span className="font-medium">{p.name}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                  p.type === 'prohibited' ? 'bg-red-100 text-red-700' :
                  p.type === 'penalty' ? 'bg-orange-100 text-orange-700' :
                  p.type === 'waypoint' ? 'bg-purple-100 text-purple-700' :
                  'bg-blue-100 text-blue-700'
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