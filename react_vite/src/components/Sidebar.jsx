import React from 'react';
import {
  Save,
  Settings,
  HelpCircle,
  X,
} from 'lucide-react';
import EditPointView from './EditPointView';
import EditGateView from './EditGateView';
import logo from '../assets/logo.png';
import EditObservationView from './EditObservationView';
import EditPolygonView from './EditPolygonView';
import RouteListView from './RouteListView';
import HelpView from './HelpView';

const Sidebar = ({
  routePoints,
  gates,
  observationMarkers,
  polygons,
  selectedId,
  selectionType,
  validationErrors,
  showCorridor,
  setShowCorridor,
  setSelectedId,
  setSelectionType,
  updateSelectedPoint,
  updateSelectedGate,
  updateSelectedObservation,
  updateSelectedPolygon,
  deleteSelected,
  movePointOrder,
  handleSave,
  maxObsDist,
  setMaxObsDist,
  routeName,
  setRouteName
}) => {

  const renderContent = () => {
    const selectedPoint = routePoints.find(p => p.id === selectedId);
    const selectedGate = gates.find(g => g.id === selectedId);
    const selectedObs = observationMarkers.find(m => m.id === selectedId);
    const selectedPolygon = polygons?.find(p => p.id === selectedId);

    if (selectionType === 'point' && selectedPoint) {
      return <EditPointView
        point={selectedPoint}
        updatePoint={updateSelectedPoint}
        deletePoint={deleteSelected}
        moveOrder={movePointOrder}
        onClose={() => { setSelectedId(null); setSelectionType(null); }}
      />;
    }

    if (selectionType === 'gate' && selectedGate) {
      return <EditGateView
        gate={selectedGate}
        updateGate={updateSelectedGate}
        deleteGate={deleteSelected}
        onClose={() => { setSelectedId(null); setSelectionType(null); }}
      />;
    }

    if (selectionType === 'observation' && selectedObs) {
      return <EditObservationView
        observation={selectedObs}
        updateObservation={updateSelectedObservation}
        deleteObservation={deleteSelected}
        onClose={() => { setSelectedId(null); setSelectionType(null); }}
      />;
    }

    if (selectionType === 'polygon' && selectedPolygon) {
      return <EditPolygonView
        polygon={selectedPolygon}
        updatePolygon={updateSelectedPolygon}
        deletePolygon={deleteSelected}
        onClose={() => { setSelectedId(null); setSelectionType(null); }}
      />;
    }

    if (selectionType === 'settings') {
      return (
        <div className="p-4 space-y-4">
          <div className="flex items-center justify-between border-b pb-2">
            <h2 className="text-lg font-bold">Settings</h2>
            <button onClick={() => setSelectionType(null)} className="btn btn-ghost btn-sm btn-square">
              <X size={20} />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="showCorridor"
              checked={showCorridor}
              onChange={(e) => setShowCorridor(e.target.checked)}
              className="checkbox checkbox-sm checkbox-primary"
            />
            <label htmlFor="showCorridor" className="text-sm font-medium text-gray-700">Show Corridor</label>
          </div>
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              Max Observation Distance
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                step="0.1"
                value={parseFloat((maxObsDist / 1852).toFixed(2))}
                onChange={(e) => setMaxObsDist(Number(e.target.value) * 1852)}
                className="input input-bordered input-sm w-full"
              />
              <span className="text-sm text-gray-500">NM</span>
            </div>
            <p className="text-xs text-gray-500">
              Default: 0.5 NM. Maximum distance a photo point can be from the route.
            </p>
          </div>
        </div>
      );
    }

    if (selectionType === 'help') {
      return <HelpView onClose={() => { setSelectedId(null); setSelectionType(null); }} />;
    }

    // Default View (List)
    return <RouteListView
      routePoints={routePoints}
      gates={gates}
      observationMarkers={observationMarkers}
      polygons={polygons}
      validationErrors={validationErrors}
      onSelect={(id, type) => { setSelectedId(id); setSelectionType(type); }}
    />;
  };

  return (
    <div className="w-80 flex flex-col bg-base-100 border-r shadow-xl z-20">
      <div className="p-6 bg-neutral text-neutral-content flex flex-col items-center gap-3 shadow-sm">
        <h1 className="text-xl font-bold tracking-tight">Route Editor</h1>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <input
          type="text"
          value={routeName}
          onChange={(e) => setRouteName(e.target.value)}
          placeholder="Route Name"
          className="input input-bordered w-full mb-4 text-lg font-bold"
        />

        {renderContent()}
      </div>

      {/* Import/Export Footer */}
      <div className="p-4 border-t bg-base-200 space-y-2">
        <div className="flex space-x-2">
          <button
            onClick={handleSave}
            className="btn btn-primary btn-sm flex-1 gap-2"
          >
            <Save size={14} /> <span>Save Route</span>
          </button>
          <button
            onClick={() => { setSelectedId(null); setSelectionType('settings'); }}
            className="btn btn-outline btn-sm btn-square"
            title="Settings"
          >
            <Settings size={14} />
          </button>
          <button
            onClick={() => { setSelectedId(null); setSelectionType('help'); }}
            className="btn btn-outline btn-sm btn-square"
            title="Help"
          >
            <HelpCircle size={14} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;