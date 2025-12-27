import React from 'react';
import { 
  Save, 
  Upload, 
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
  handleExport,
  handleImport,
  maxObsDist,
  setMaxObsDist
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
            <button onClick={() => setSelectionType(null)} className="text-gray-500 hover:text-gray-700">
              <X size={20} />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <input 
              type="checkbox" 
              id="showCorridor"
              checked={showCorridor}
              onChange={(e) => setShowCorridor(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500"
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
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border p-2"
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
    <div className="w-80 flex flex-col bg-white border-r shadow-xl z-20">
      <div className="p-6 bg-slate-900 text-white flex flex-col items-center gap-3 shadow-sm">
        <img src={logo} alt="Logo" className="h-12 w-auto object-contain" />
        <h1 className="text-xl font-bold tracking-tight">Route Editor</h1>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {renderContent()}
      </div>

      {/* Import/Export Footer */}
      <div className="p-4 border-t bg-gray-50 space-y-2">
        <div className="flex space-x-2">
          <button 
            onClick={handleExport}
            className="flex-1 bg-slate-800 text-white p-2 rounded text-sm hover:bg-slate-700 flex items-center justify-center space-x-1"
          >
            <Save size={14} /> <span>Export JSON</span>
          </button>
          <label className="flex-1 bg-white border text-gray-700 p-2 rounded text-sm hover:bg-gray-50 flex items-center justify-center space-x-1 cursor-pointer">
            <Upload size={14} /> <span>Import</span>
            <input type="file" accept=".json,.geojson" className="hidden" onChange={handleImport} />
          </label>
          <button 
            onClick={() => { setSelectedId(null); setSelectionType('settings'); }}
            className="bg-white border text-gray-700 p-2 rounded text-sm hover:bg-gray-50 flex items-center justify-center"
            title="Settings"
          >
            <Settings size={14} />
          </button>
          <button 
            onClick={() => { setSelectedId(null); setSelectionType('help'); }}
            className="bg-white border text-gray-700 p-2 rounded text-sm hover:bg-gray-50 flex items-center justify-center"
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